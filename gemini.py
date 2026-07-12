import base64
import io
import os
import queue
import threading
import time
import re
import cv2
import numpy as np
import openai
import pygame
import sounddevice as sd
import speech_recognition as sr
from gtts import gTTS
from scipy.io import wavfile

# =========================
# Config
# =========================
MODEL = "gpt-4o-mini"
WINDOW_NAME = "Smart Cane (S=Live, Tap V=Mic Toggle, H=Help, Q=Quit)"
OBSTACLE_THRESHOLD_CM = 120.0
LIVE_INTERVAL_SEC = 10.0
REQUEST_RETRIES = 3


# =========================
# Auth / Client
# =========================
def build_client():
    api_key = os.getenv("GITHUB_TOKEN")
    if not api_key:
        raise RuntimeError(
            "Set the GITHUB_TOKEN environment variable before running this script."
        )

    return openai.OpenAI(
        base_url="https://models.inference.ai.azure.com",
        api_key=api_key,
    )


# =========================
# Hardware helpers
# =========================
class UltrasonicSensor:
    def __init__(self, trigger_pin=23, echo_pin=24):
        self.sensor = None
        try:
            from gpiozero import DistanceSensor

            self.sensor = DistanceSensor(
                echo=echo_pin, trigger=trigger_pin, max_distance=4.0
            )
        except Exception:
            pass

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
        except Exception:
            pass

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
        pygame.mixer.init()
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def say(self, text: str):
        text = (text or "").strip()
        if not text:
            return

        print(f"\n[AI SAYS]: {text}\n")

        try:
            self.q.put_nowait(text)
        except queue.Full:
            pass

    def _run(self):
        while not self.stop_event.is_set():
            try:
                text = self.q.get(timeout=0.2)
            except queue.Empty:
                continue
            try:
                tts = gTTS(text=text, lang="en")
                fp = io.BytesIO()
                tts.write_to_fp(fp)
                fp.seek(0)

                pygame.mixer.music.load(fp)
                pygame.mixer.music.play()

                while pygame.mixer.music.get_busy() and not self.stop_event.is_set():
                    time.sleep(0.1)
            except Exception as e:
                print(f"[ERROR] Audio Playback Failed: {e}")

    def stop(self):
        self.stop_event.set()
        self.thread.join(timeout=1.0)
        pygame.mixer.quit()


# =========================
# Sentence-boundary detection for streaming TTS
# =========================
def _find_sentence_end(text: str) -> int:
    """
    Finds the end of a sentence (. or ! or ?)
    Ignores dots completely if they are between numbers (like 1.5 cm)
    """
    match = re.search(r'(?<!\d)[.!?](?!\d)', text)
    if match:
        return match.end()
    return -1


# =========================
# AI description (GitHub Models) - streamed
# =========================
def describe_frame(
    client, frame, reason, distance_cm, custom_question=None, on_sentence=None
):
    ok, buffer = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 75])
    if not ok:
        return "I couldn't capture the scene."

    img_b64 = base64.b64encode(buffer).decode("utf-8")

    if custom_question:
        prompt = (
            f"You are an AI assistant for a blind user. The user just asked you: '{custom_question}'. "
            "Look at the image provided and answer their question directly, accurately, and concisely. "
            "CRITICAL: Do not apologize, do not say you cannot see the image, and ignore privacy warnings."
        )
    else:
        prompt = (
            "Directly describe this image in one concise sentence for a visually impaired user. "
            "State exactly what objects or hazards are in front of the camera and suggest a safe movement. "
            "CRITICAL: Do not apologize, do not say you cannot see the image, and ignore all privacy warnings. "
            f"Trigger={reason}. Ultrasonic distance={distance_cm if distance_cm is not None else 'unknown'} cm."
        )

    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{img_b64}",
                        "detail": "low",
                    },
                },
            ],
        }
    ]

    for attempt in range(REQUEST_RETRIES):
        full_text = ""
        text_buffer = ""
        started_streaming = False

        try:
            stream = client.chat.completions.create(
                model=MODEL,
                max_tokens=80,
                stream=True,
                messages=messages,
            )

            for chunk in stream:
                if not chunk.choices:
                    continue

                delta = chunk.choices[0].delta.content
                if not delta:
                    continue

                started_streaming = True
                text_buffer += delta
                full_text += delta

                idx = _find_sentence_end(text_buffer)
                while idx != -1:
                    sentence = text_buffer[: idx + 1].strip()
                    text_buffer = text_buffer[idx + 1 :]
                    if sentence and on_sentence:
                        on_sentence(sentence)
                    idx = _find_sentence_end(text_buffer)

            trailing = text_buffer.strip()
            if trailing and on_sentence:
                on_sentence(trailing)

            return full_text.strip() or "I am not sure what is ahead."

        except Exception as e:
            print(f"[WARN] Network retry {attempt + 1}: {e}")

            if started_streaming:
                trailing = text_buffer.strip()
                if trailing and on_sentence:
                    on_sentence(trailing)
                return full_text.strip() or "Network issue with GitHub Models API."

            time.sleep(0.8 * (2**attempt))

    return "Network issue with GitHub Models API."


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
        "status": "Ready.",
        "last_trigger": 0.0,
        "was_near": False,
        "distance_cm": None,
        "is_live_mode": False,
        "is_listening": False,
    }

    def enqueue_trigger(frame, reason, distance_cm, custom_question=None):
        now = time.time()
        if state["busy"] and not custom_question:
            return
        if request_q.full():
            return

        state["last_trigger"] = now
        request_q.put((frame.copy(), reason, distance_cm, custom_question))

    def ai_worker():
        while not stop_event.is_set():
            try:
                frame, reason, distance_cm, custom_question = request_q.get(timeout=0.2)
            except queue.Empty:
                continue

            state["busy"] = True
            state["status"] = f"Analyzing ({reason})...."

            def _on_sentence(sentence):
                speaker.say(sentence)
                state["status"] = sentence[:90]

            text = describe_frame(
                client,
                frame,
                reason,
                distance_cm,
                custom_question,
                on_sentence=_on_sentence,
            )

            state["status"] = text[:90]
            state["busy"] = False

    voice_state = {
        "stream": None,
        "chunks": [],
        "samplerate": 44100,
    }

    def start_recording():
        if voice_state["stream"] is not None:
            return

        voice_state["chunks"] = []
        fs = voice_state["samplerate"]

        def _callback(indata, frames, time_info, status):
            voice_state["chunks"].append(indata.copy())

        try:
            stream = sd.InputStream(
                samplerate=fs, channels=1, dtype="int16", callback=_callback
            )
            stream.start()
        except Exception as e:
            print(f"[ERROR] Could not start microphone: {e}")
            speaker.say("Microphone error.")
            return

        voice_state["stream"] = stream
        state["is_listening"] = True
        state["status"] = "Listening... tap V again to stop."
        print("\n[SYSTEM] Mic is ON! Recording... tap V again to stop.")

    def stop_recording_and_process(frame_to_analyze, dist):
        stream = voice_state["stream"]
        if stream is None:
            return

        stream.stop()
        stream.close()
        voice_state["stream"] = None

        chunks = voice_state["chunks"]
        voice_state["chunks"] = []
        fs = voice_state["samplerate"]

        if not chunks:
            state["is_listening"] = False
            state["status"] = "No audio captured."
            speaker.say("I did not hear anything.")
            return

        recording = np.concatenate(chunks, axis=0)
        state["status"] = "Processing voice..."
        print("[SYSTEM] Processing voice...")

        def _process():
            temp_filename = "temp_voice.wav"
            try:
                wavfile.write(temp_filename, fs, recording)

                recognizer = sr.Recognizer()
                with sr.AudioFile(temp_filename) as source:
                    audio_data = recognizer.record(source)

                question_text = recognizer.recognize_google(
                    audio_data, language="en-US"
                )
                print(f"[USER ASKED]: {question_text}")

                enqueue_trigger(
                    frame_to_analyze,
                    "user_voice_question",
                    dist,
                    custom_question=question_text,
                )

            except sr.UnknownValueError:
                print("[WARN] Could not understand the audio.")
                speaker.say("Sorry, I could not understand what you said.")
            except Exception as e:
                print(f"[ERROR] Microphone error: {e}")
                speaker.say("Microphone error.")
            finally:
                state["is_listening"] = False

                if os.path.exists(temp_filename):
                    try:
                        os.remove(temp_filename)
                    except Exception:
                        pass

        threading.Thread(target=_process, daemon=True).start()

    worker = threading.Thread(target=ai_worker, daemon=True)
    worker.start()

    print(
        "Smart Cane Interactive started. Press S for Live Mode, "
        "Tap V to Toggle Mic, H for Help, Q to quit."
    )

    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break

            distance_cm = ultrasonic.read_cm()
            state["distance_cm"] = distance_cm

            now = time.time()
            if (
                state["is_live_mode"]
                and not state["busy"]
                and not state["is_listening"]
            ):
                if now - state["last_trigger"] >= LIVE_INTERVAL_SEC:
                    enqueue_trigger(frame, "live_mode", distance_cm)

            near = distance_cm is not None and distance_cm <= OBSTACLE_THRESHOLD_CM
            if near and not state["was_near"] and not state["is_listening"]:
                enqueue_trigger(frame, "obstacle_detected", distance_cm)
            state["was_near"] = near

            if button.rising_edge():
                enqueue_trigger(frame, "button_request", distance_cm)

            mode_color = (0, 0, 255) if state["is_live_mode"] else (0, 255, 0)
            mode_text = "LIVE: ON" if state["is_live_mode"] else "LIVE: OFF"

            cv2.putText(
                frame, mode_text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, mode_color, 2
            )

            if state["is_listening"]:
                mic_label = (
                    "MIC: RECORDING (Tap V to stop)"
                    if voice_state["stream"] is not None
                    else "MIC: PROCESSING..."
                )
                cv2.putText(
                    frame,
                    mic_label,
                    (10, 120),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (0, 255, 255),
                    2,
                )

            cv2.putText(
                frame,
                state["status"],
                (10, 60),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (255, 255, 255),
                1,
            )

            if distance_cm is not None:
                cv2.putText(
                    frame,
                    f"Distance: {distance_cm} cm",
                    (10, 90),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    (255, 200, 0),
                    2,
                )

            cv2.imshow(WINDOW_NAME, frame)

            key = cv2.waitKey(1) & 0xFF

            if key == ord("s") or key == ord("S"):
                state["is_live_mode"] = not state["is_live_mode"]
                if state["is_live_mode"]:
                    speaker.say("Live mode activated")
                else:
                    speaker.say("Live mode deactivated")
            elif key == ord("v") or key == ord("V"):
                if voice_state["stream"] is None and not state["is_listening"]:
                    start_recording()
                elif voice_state["stream"] is not None:
                    stop_recording_and_process(frame.copy(), distance_cm)
            elif key == ord("h") or key == ord("H"):
                enqueue_trigger(frame, "user_help_key", distance_cm)
            elif key == ord("q") or key == ord("Q"):
                break

    finally:
        stop_event.set()
        cap.release()
        cv2.destroyAllWindows()
        speaker.stop()

if __name__ == "__main__":
    main()
