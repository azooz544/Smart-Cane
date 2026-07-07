import os
import time
import queue
import threading

import cv2
import pyttsx3
from google import genai
from google.genai import types
from google.oauth2 import service_account

# =========================
# Config
# =========================
MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
WINDOW_NAME = "Smart Cane (H=Help, Q=Quit)"
OBSTACLE_THRESHOLD_CM = 120.0
TRIGGER_COOLDOWN_SEC = 3.0
REQUEST_RETRIES = 3


# =========================
# Auth / Client
# =========================
def build_client():
    # Fast path: Gemini Developer API key (no Vertex setup needed)
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if api_key:
        print("[INFO] Using Gemini API key auth.")
        return genai.Client(api_key=api_key)

    # Vertex path: service account
    key_candidates = [
        os.getenv("GOOGLE_APPLICATION_CREDENTIALS", ""),
        "integral-legend-501221-v9-d021cfc393eb.json",
        "integral-legend-501221-v9-cc84c59f24e4.json",
    ]
    key_file = next((k for k in key_candidates if k and os.path.exists(k)), None)
    if not key_file:
        raise FileNotFoundError(
            "No credentials found. Set GEMINI_API_KEY or provide service-account JSON."
        )

    creds = service_account.Credentials.from_service_account_file(
        key_file,
        scopes=["https://www.googleapis.com/auth/cloud-platform"],
    )
    project = os.getenv("GOOGLE_CLOUD_PROJECT") or creds.project_id
    location = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")

    if not project:
        raise RuntimeError("Could not determine GOOGLE_CLOUD_PROJECT.")

    print(f"[INFO] Using Vertex auth. project={project}, location={location}")
    return genai.Client(
        vertexai=True,
        project=project,
        location=location,
        credentials=creds,
    )


# =========================
# Optional hardware helpers
# =========================
class UltrasonicSensor:
    def __init__(self, trigger_pin=23, echo_pin=24):
        self.sensor = None
        try:
            from gpiozero import DistanceSensor

            self.sensor = DistanceSensor(
                echo=echo_pin,
                trigger=trigger_pin,
                max_distance=4.0,  # meters
            )
            print("[INFO] Ultrasonic sensor enabled.")
        except Exception as e:
            print(f"[WARN] Ultrasonic disabled ({e}).")

    def read_cm(self):
        if self.sensor is None:
            return None
        try:
            return round(self.sensor.distance * 100.0, 1)
        except Exception:
            return None


class ButtonTrigger:
    def __init__(self, pin=17):
        self.button = None
        self._prev = False
        try:
            from gpiozero import Button

            self.button = Button(pin, pull_up=True, bounce_time=0.05)
            print("[INFO] Hardware button enabled.")
        except Exception as e:
            print(f"[WARN] Button trigger disabled ({e}).")

    def rising_edge(self):
        if self.button is None:
            return False
        cur = self.button.is_pressed
        edge = cur and not self._prev
        self._prev = cur
        return edge


# =========================
# Speech worker
# =========================
class Speaker:
    def __init__(self):
        self.q = queue.Queue(maxsize=8)
        self.stop_event = threading.Event()
        self.last_text = ""
        self.last_time = 0.0
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def say(self, text: str):
        text = (text or "").strip()
        if not text:
            return

        now = time.time()
        if text == self.last_text and now - self.last_time < 6:
            return  # dedupe repeated speech

        self.last_text = text
        self.last_time = now
        try:
            self.q.put_nowait(text)
        except queue.Full:
            pass

    def _run(self):
        try:
            import pythoncom

            pythoncom.CoInitialize()
        except Exception:
            pass

        engine = pyttsx3.init()
        engine.setProperty("rate", 170)

        while not self.stop_event.is_set():
            try:
                text = self.q.get(timeout=0.2)
            except queue.Empty:
                continue
            try:
                engine.say(text)
                engine.runAndWait()
            except Exception as e:
                print(f"[WARN] TTS error: {e}")

    def stop(self):
        self.stop_event.set()
        self.thread.join(timeout=1.0)


# =========================
# AI description
# =========================
def describe_frame(client, frame, reason, distance_cm):
    ok, jpg = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 75])
    if not ok:
        return "I couldn't capture the scene."

    prompt = (
        "You are a navigation assistant for a blind user. "
        "Give one short sentence (max 12 words). "
        "Focus on immediate hazards and safest next movement. "
        f"Trigger={reason}. Ultrasonic distance={distance_cm if distance_cm is not None else 'unknown'} cm."
    )

    contents = [
        types.Part.from_bytes(data=jpg.tobytes(), mime_type="image/jpeg"),
        prompt,
    ]

    last_err = None
    for attempt in range(REQUEST_RETRIES):
        try:
            response = client.models.generate_content(model=MODEL, contents=contents)
            text = (response.text or "").strip()
            return text or "I am not sure what is ahead."
        except Exception as e:
            last_err = e
            time.sleep(0.8 * (2**attempt))

    return f"Network issue. {last_err}"


# =========================
# Main app
# =========================
def main():
    client = build_client()
    speaker = Speaker()
    ultrasonic = UltrasonicSensor()
    button = ButtonTrigger()

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        raise RuntimeError("Could not open camera.")

    request_q = queue.Queue(maxsize=1)
    stop_event = threading.Event()

    state = {
        "busy": False,
        "status": "Ready (H=help, button, or obstacle trigger).",
        "last_trigger": 0.0,
        "last_spoken": "",
        "was_near": False,
        "distance_cm": None,
    }

    def enqueue_trigger(frame, reason, distance_cm):
        now = time.time()
        if state["busy"]:
            return
        if now - state["last_trigger"] < TRIGGER_COOLDOWN_SEC:
            return
        if request_q.full():
            return

        state["last_trigger"] = now
        request_q.put((frame.copy(), reason, distance_cm))

    def ai_worker():
        while not stop_event.is_set():
            try:
                frame, reason, distance_cm = request_q.get(timeout=0.2)
            except queue.Empty:
                continue

            state["busy"] = True
            state["status"] = f"Analyzing ({reason})..."
            text = describe_frame(client, frame, reason, distance_cm)

            # avoid repeating identical line too often
            if text != state["last_spoken"]:
                speaker.say(text)
                state["last_spoken"] = text

            state["status"] = text[:90]
            state["busy"] = False

    worker = threading.Thread(target=ai_worker, daemon=True)
    worker.start()

    print("Smart Cane Interactive started. Press H for help, Q to quit.")

    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break

            # Sensor polling
            distance_cm = ultrasonic.read_cm()
            state["distance_cm"] = distance_cm

            near = distance_cm is not None and distance_cm <= OBSTACLE_THRESHOLD_CM
            if near and not state["was_near"]:
                enqueue_trigger(frame, "obstacle_detected", distance_cm)
            state["was_near"] = near

            if button.rising_edge():
                enqueue_trigger(frame, "button_request", distance_cm)

            # UI overlay
            overlay = state["status"]
            cv2.putText(frame, overlay, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
            if distance_cm is not None:
                cv2.putText(
                    frame,
                    f"Distance: {distance_cm} cm",
                    (10, 55),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    (255, 200, 0),
                    2,
                )

            cv2.imshow(WINDOW_NAME, frame)
            key = cv2.waitKey(1) & 0xFF

            if key == ord("h"):
                enqueue_trigger(frame, "user_help_key", distance_cm)
            elif key == ord("q"):
                break

    finally:
        stop_event.set()
        cap.release()
        cv2.destroyAllWindows()
        speaker.stop()


if __name__ == "__main__":
    main()
