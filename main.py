"""
Smart Cane AI Assistant — Main Entry Point.

Orchestrates the camera loop, hardware sensors, AI inference,
and speech feedback into a cohesive real-time navigation system
for visually impaired users.
"""

import logging
import queue
import threading
import time

import cv2

from src.config import (
    CAMERA_INDEX,
    LIVE_INTERVAL_SEC,
    OBSTACLE_THRESHOLD_CM,
    WINDOW_NAME,
)
from src.ai import build_client, describe_frame
from src.hardware import UltrasonicSensor, ButtonTrigger
from src.speech import Speaker, listen_for_question
from src.ui import draw_overlay

# =========================
# Logging Setup
# =========================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


# =========================
# Application State
# =========================
class AppState:
    """Mutable application state shared across threads."""

    def __init__(self):
        self.busy = False
        self.status = "Ready."
        self.last_trigger = 0.0
        self.was_near = False
        self.distance_cm: float | None = None
        self.is_live_mode = False
        self.is_listening = False


# =========================
# Core Logic
# =========================
def enqueue_trigger(
    request_q: queue.Queue,
    state: AppState,
    frame,
    reason: str,
    distance_cm: float | None,
    custom_question: str | None = None,
) -> None:
    """Attempt to queue a frame for AI analysis (non-blocking)."""
    if state.busy and not custom_question:
        return
    if request_q.full():
        return

    state.last_trigger = time.time()
    request_q.put((frame.copy(), reason, distance_cm, custom_question))


def ai_worker(
    client,
    request_q: queue.Queue,
    state: AppState,
    speaker: Speaker,
    stop_event: threading.Event,
) -> None:
    """Background thread: process queued frames through the AI model."""
    while not stop_event.is_set():
        try:
            frame, reason, distance_cm, custom_question = request_q.get(timeout=0.2)
        except queue.Empty:
            continue

        state.busy = True
        state.status = f"Analyzing ({reason})..."

        text = describe_frame(client, frame, reason, distance_cm, custom_question)
        speaker.say(text)

        state.status = text[:90]
        state.busy = False


def voice_question_handler(
    frame,
    distance_cm: float | None,
    request_q: queue.Queue,
    state: AppState,
    speaker: Speaker,
) -> None:
    """Record a voice question and queue it for AI analysis."""
    state.is_listening = True
    state.status = "Listening (5 sec)..."

    try:
        question = listen_for_question()
        if question:
            enqueue_trigger(
                request_q, state, frame, "user_voice_question", distance_cm, custom_question=question
            )
        else:
            speaker.say("Sorry, I could not understand what you said.")
    finally:
        state.is_listening = False


# =========================
# Main Loop
# =========================
def main() -> None:
    """Initialize components and run the main camera + event loop."""
    logger.info("Starting Smart Cane AI Assistant...")

    # Initialize components
    client = build_client()
    speaker = Speaker()
    ultrasonic = UltrasonicSensor()
    button = ButtonTrigger()

    # Open camera
    cap = cv2.VideoCapture(CAMERA_INDEX)
    if not cap.isOpened():
        raise RuntimeError("Could not open camera.")

    request_q: queue.Queue = queue.Queue(maxsize=1)
    stop_event = threading.Event()
    state = AppState()

    # Start AI worker thread
    worker = threading.Thread(
        target=ai_worker,
        args=(client, request_q, state, speaker, stop_event),
        daemon=True,
        name="AIWorkerThread",
    )
    worker.start()

    logger.info("System ready. Press S=Live, V=Voice, H=Help, Q=Quit.")

    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                logger.error("Camera read failed.")
                break

            # Poll hardware sensors
            distance_cm = ultrasonic.read_cm()
            state.distance_cm = distance_cm

            now = time.time()

            # Live mode: periodic auto-analysis
            if state.is_live_mode and not state.busy and not state.is_listening:
                if now - state.last_trigger >= LIVE_INTERVAL_SEC:
                    enqueue_trigger(request_q, state, frame, "live_mode", distance_cm)

            # Obstacle detection via ultrasonic sensor
            near = distance_cm is not None and distance_cm <= OBSTACLE_THRESHOLD_CM
            if near and not state.was_near and not state.is_listening:
                enqueue_trigger(request_q, state, frame, "obstacle_detected", distance_cm)
            state.was_near = near

            # Physical button press
            if button.rising_edge():
                enqueue_trigger(request_q, state, frame, "button_request", distance_cm)

            # Draw UI overlay
            draw_overlay(frame, state.is_live_mode, state.is_listening, state.status, distance_cm)

            # Display frame
            cv2.imshow(WINDOW_NAME, frame)
            key = cv2.waitKey(1) & 0xFF

            # Keyboard controls
            if key in (ord("s"), ord("S")):
                state.is_live_mode = not state.is_live_mode
                speaker.say("Live mode activated" if state.is_live_mode else "Live mode deactivated")

            elif key in (ord("v"), ord("V")):
                if not state.is_listening:
                    threading.Thread(
                        target=voice_question_handler,
                        args=(frame.copy(), distance_cm, request_q, state, speaker),
                        daemon=True,
                        name="VoiceThread",
                    ).start()

            elif key in (ord("h"), ord("H")):
                enqueue_trigger(request_q, state, frame, "user_help_key", distance_cm)

            elif key in (ord("q"), ord("Q")):
                logger.info("Quit requested by user.")
                break

    finally:
        stop_event.set()
        cap.release()
        cv2.destroyAllWindows()
        speaker.stop()
        logger.info("Smart Cane shut down cleanly.")


if __name__ == "__main__":
    main()
