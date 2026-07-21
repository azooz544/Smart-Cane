import base64
import io
import os
import queue
# Multilingual mapping for short spoken guidance (language -> {label_key: (spoken_name, short_action)})
LABEL_ACTIONS = {
    "en": {
        "person": ("Person", "Person ahead — slow or step aside"),
        "pole": ("Pole", "Pole ahead — veer around"),
        "chair": ("Chair", "Obstacle — step left or right"),
        "car": ("Car", "Vehicle ahead — stop and wait"),
        "bicycle": ("Bicycle", "Bike ahead — pause and give space"),
        "dog": ("Dog", "Dog ahead — slow down"),
        "stairs": ("Stairs", "Stairs ahead — stop and prepare to descend"),
        "curb": ("Curb", "Curb ahead — watch your step"),
        "wheelchair": ("Wheelchair", "Wheelchair nearby — give space"),
        "motorcycle": ("Motorcycle", "Motorbike ahead — stop and wait"),
    },
    "ar": {
        "person": ("شخص", "شخص أمامك — تباطأ أو تحرك جانباً"),
        "pole": ("عمود", "عمود أمامك — انحرف لتجاوزه"),
        "chair": ("كرسي", "عائق — تحرك يساراً أو يميناً"),
        "car": ("سيارة", "مركبة أمامك — توقف وانتظر"),
        "bicycle": ("دراجة", "دراجة أمامك — توقف وأعطِ مساحة"),
        "dog": ("كلب", "كلب أمامك — تمهل"),
        "stairs": ("سلالم", "سلالم أمامك — توقف واستعد للنزول"),
        "curb": ("رصيف", "رصيف أمامك — راقب خطوتك"),
        "wheelchair": ("كرسي متحرك", "كرسي متحرك قريب — اترك مسافة"),
        "motorcycle": ("دراجة نارية", "دراجة نارية أمامك — توقف وانتبه"),
    },
    "tr": {
        "person": ("Kişi", "Önde bir kişi — yavaşlayın veya kenara geçin"),
        "pole": ("Direk", "Direk önde — çevresinden dolanın"),
        "chair": ("Sandalye", "Engel — sola veya sağa adım atın"),
        "car": ("Araba", "Araç önde — durun ve bekleyin"),
        "bicycle": ("Bisiklet", "Bisiklet önde — duraklayın ve boşluk verin"),
        "dog": ("Köpek", "Köpek önde — yavaşlayın"),
        "stairs": ("Merdiven", "Merdivenler önde — durun ve inmeye hazırlanın"),
        "curb": ("Kaldırım", "Kaldırım önde — dikkatli adım"),
        "wheelchair": ("Tekerlekli sandalye", "Tekerlekli sandalye yakın — yer verin"),
        "motorcycle": ("Motosiklet", "Motosiklet önde — durun ve bekleyin"),
    },
}

import re
import threading
import time
try:
    import tkinter as tk
    from threading import Thread
    TK_AVAILABLE = True
except Exception:
    TK_AVAILABLE = False
import json
import random

import cv2
import numpy as np
import openai
import pygame
import sounddevice as sd
import speech_recognition as sr
from gtts import gTTS
from scipy.io import wavfile
from prompt_system import get_prompt_manager

# =========================
# Config
# =========================
MODEL = "gpt-4o-mini"
WINDOW_NAME = "Smart Cane (S=Live, Tap V=Mic Toggle, H=Help, Q=Quit)"
# VIDEO_SOURCE can be a path or a camera index. Set via env `VIDEO_SOURCE`.
# Default to camera 0 when not provided or when the file is missing.
VIDEO_SOURCE = os.getenv("VIDEO_SOURCE", "0")

# Headless / debug mode: when set, disable audio/video and AI network calls
SMARTCANE_HEADLESS = os.getenv("SMARTCANE_HEADLESS", "0") in ("1", "true", "True")
# When headless, default to using the mock AI unless explicitly overridden
MOCK_AI = os.getenv("MOCK_AI", "1" if SMARTCANE_HEADLESS else "0") in ("1", "true", "True")

OBSTACLE_THRESHOLD_CM = 120.0

# --- Live-mode pacing ---
LIVE_MIN_INTERVAL_SEC = 3.5        # hard floor: never call the AI faster than this in live mode
LIVE_HEARTBEAT_SEC = 45.0          # force a check-in even with no visible change (safety net)
SCENE_CHANGE_THRESHOLD = 15.0      # avg pixel diff (0-255 scale) needed to count as "something changed"
                                    # tune this up/down depending on your camera's noise level

# --- De-duplication of speech ---
TEXT_SIMILARITY_SKIP = 0.72        # if new text overlaps this much with the last spoken line, stay quiet

REQUEST_RETRIES = 3


# =========================
# Auth / Client
# =========================
def build_client():
    # Route requests to GitHub Models servers using the GITHUB_TOKEN
    api_key = os.getenv("GITHUB_TOKEN")
    if not api_key:
        raise RuntimeError(
            "Set the GITHUB_TOKEN environment variable before running this script."
        )

    # Fixed base URL for GitHub Models inference endpoint
    return openai.OpenAI(base_url="https://models.inference.ai.azure.com", api_key=api_key)


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


class Vibrator:
    """Optional haptic driver for left/right vibration motors.
    Falls back to printing if GPIO isn't available.
    """
    def __init__(self, left_pin=5, right_pin=6):
        self.left = None
        self.right = None
        self.enabled = False
        try:
            from gpiozero import LED

            self.left = LED(left_pin)
            self.right = LED(right_pin)
            self.enabled = True
        except Exception:
            self.enabled = False

    def pulse(self, side, duration=0.15):
        if not self.enabled:
            print(f"[HAPTIC] pulse {side} ({duration}s)")
            return
        try:
            if side == "left":
                self.left.on(); time.sleep(duration); self.left.off()
            elif side == "right":
                self.right.on(); time.sleep(duration); self.right.off()
            else:
                # both
                self.left.on(); self.right.on(); time.sleep(duration); self.left.off(); self.right.off()
        except Exception as e:
            print(f"[HAPTIC] error: {e}")


# =========================
# Scene-change detector (cheap local vision, no API call)
# =========================
class SceneChangeDetector:
    """Keeps a small reference frame and scores how much the scene changed.
    Used to decide WHEN it's worth calling the (slow, costly) vision model,
    instead of asking it on a fixed timer regardless of content."""

    def __init__(self, resize_to=(64, 48)):
        self.resize_to = resize_to
        self.reference = None

    def _prep(self, frame):
        small = cv2.resize(frame, self.resize_to)
        return cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)

    def score(self, frame):
        gray = self._prep(frame)
        if self.reference is None:
            return 999.0  # nothing to compare yet -> force a first trigger
        diff = cv2.absdiff(gray, self.reference)
        return float(np.mean(diff))

    def update_reference(self, frame):
        self.reference = self._prep(frame)


# =========================
# Text similarity (cheap local dedup, no API call)
# =========================
def text_similarity(a: str, b: str) -> float:
    wa = set(re.findall(r"[a-zA-Z']+", a.lower()))
    wb = set(re.findall(r"[a-zA-Z']+", b.lower()))
    if not wa or not wb:
        return 0.0
    inter = len(wa & wb)
    union = len(wa | wb)
    return inter / union if union else 0.0


NO_NEWS_PHRASES = ("clear", "still clear", "same", "nothing new", "no change", "all clear")


def is_no_news(text: str) -> bool:
    t = text.strip().lower().strip(".")
    return t.startswith("clear") or t in NO_NEWS_PHRASES


# =========================
# Local YOLO obstacle classifier (optional)
# =========================
YOLO_MODEL = None
YOLO_LABELS = None
# Configurable global confidence threshold for local detection (default tightened)
YOLO_CONF_THRESH = float(os.getenv("YOLO_CONF_THRESH", "0.45"))
# Per-label confidence thresholds (label lowercased -> min conf)
YOLO_LABEL_THRESHOLDS = {
    "person": 0.4,
    "stairs": 0.6,
    "stair": 0.6,
    "curb": 0.55,
    "pole": 0.35,
    "car": 0.45,
    "bicycle": 0.45,
    "motorcycle": 0.45,
    "dog": 0.35,
}


# =========================
# Runtime config file support
# =========================
CONFIG_PATH = os.getenv("SMARTCANE_CONFIG", "config.json")

DEFAULT_CONFIG = {
    "yolo_conf_thresh": YOLO_CONF_THRESH,
    "label_thresholds": YOLO_LABEL_THRESHOLDS,
    "enable_haptic": False,
    "tts_lang": os.getenv("TTS_LANG", "en"),
    "speech_mode": os.getenv("SPEECH_MODE", "quiet"),
}

# Global used by the optional Tk tuning GUI. Initialized from YOLO_CONF_THRESH.
global_yolo_conf = YOLO_CONF_THRESH
SPEECH_MODE = os.getenv("SPEECH_MODE", "quiet")


def update_conf_threshold(val):
    """دالة لتهيئة التغيير القادم من السلايدر"""
    global global_yolo_conf
    try:
        global_yolo_conf = float(val)
    except Exception:
        pass


def start_tuning_gui():
    """بناء نافذة التحكم البسيطة"""
    if not TK_AVAILABLE:
        print("[INFO] Tkinter not available; GUI tuner disabled.")
        return

    root = tk.Tk()
    root.title("ضبط حساسية العصا الذكية")
    root.geometry("400x150")

    tk.Label(root, text="حساسية التعرف على الأشياء (YOLO Threshold)", font=("Arial", 12)).pack(pady=10)

    slider = tk.Scale(root, from_=0.1, to=1.0, resolution=0.05,
                      orient="horizontal", length=300, command=update_conf_threshold)
    # initialize slider with current global value
    try:
        slider.set(global_yolo_conf)
    except Exception:
        pass
    slider.pack()

    root.mainloop()

def load_config(path=CONFIG_PATH):
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            # merge defaults
            merged = DEFAULT_CONFIG.copy()
            merged.update(cfg)
            # ensure label thresholds merged
            merged_labels = DEFAULT_CONFIG["label_thresholds"].copy()
            merged_labels.update(cfg.get("label_thresholds", {}))
            merged["label_thresholds"] = merged_labels
            return merged
    except Exception as e:
        print(f"[WARN] Could not load config {path}: {e}")
    return DEFAULT_CONFIG.copy()


def save_config(cfg, path=CONFIG_PATH):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
        print(f"[INFO] Saved config to {path}")
    except Exception as e:
        print(f"[WARN] Failed to save config: {e}")

def try_load_yolo(model_path="yolov8n.pt"):
    global YOLO_MODEL, YOLO_LABELS
    if YOLO_MODEL is not None:
        return YOLO_MODEL
    if not os.path.exists(model_path):
        print(f"[INFO] YOLO model not found at {model_path}; skipping local detection.")
        return None
    try:
        from ultralytics import YOLO

        YOLO_MODEL = YOLO(model_path)
        # names attribute may be on model or on its .model
        try:
            YOLO_LABELS = YOLO_MODEL.names
        except Exception:
            YOLO_LABELS = None
        print("[INFO] Loaded YOLO model for local object detection.")
        return YOLO_MODEL
    except Exception as e:
        print(f"[WARN] Could not load ultralytics YOLO model: {e}")
        YOLO_MODEL = None
        return None


def classify_frame_yolo(frame, conf_thresh=None, max_results=3):
    """Return a list of (label, conf, bbox_center_x, bbox_center_y) detections.
    bbox_center are normalized 0..1.
    """
    if conf_thresh is None:
        conf_thresh = YOLO_CONF_THRESH
    model = try_load_yolo()
    if model is None:
        return []
    try:
        # pass conf parameter to the model so it can pre-filter detections
        results = model(frame, imgsz=640, conf=conf_thresh)
        if not results:
            return []
        r = results[0]
        out = []
        # r.boxes is a Boxes object; iterate safely
        boxes = getattr(r, "boxes", None)
        names = getattr(r, "names", YOLO_LABELS) or {}
        if boxes is None:
            return []
        for b in boxes[:max_results]:
            try:
                conf = float(b.conf[0]) if hasattr(b, 'conf') else float(b.conf)
                cls = int(b.cls[0]) if hasattr(b, 'cls') else int(b.cls)
                label = names.get(cls, str(cls))
                xyxy = b.xyxy[0].cpu().numpy() if hasattr(b, 'xyxy') else None
                if xyxy is not None:
                    x1, y1, x2, y2 = xyxy
                    cx = (x1 + x2) / 2.0 / frame.shape[1]
                    cy = (y1 + y2) / 2.0 / frame.shape[0]
                else:
                    cx = 0.5; cy = 0.5
                # apply per-label threshold if available, otherwise use conf_thresh
                label_thresh = YOLO_LABEL_THRESHOLDS.get(label.lower(), conf_thresh)
                if conf >= conf_thresh and conf >= label_thresh:
                    out.append((label, conf, cx, cy))
            except Exception:
                continue
        return out
    except Exception as e:
        print(f"[WARN] YOLO inference failed: {e}")
        return []


# The multilingual `LABEL_ACTIONS` mapping is defined at the top of this file.
# Do not redefine it here; use `map_label_to_action()` to look up localized actions.

def map_label_to_action(label: str, lang: str = None):
    """
    Map a detected label string to a short (name, action) tuple in the requested language.
    - `lang`: language code like 'en', 'ar', 'tr'. If None, falls back to env `TTS_LANG` or 'en'.
    """
    if not label:
        return ("Obstacle", "Obstacle ahead — be cautious")
    lang = (lang or os.getenv("TTS_LANG", "en") or "en").lower()
    # prefer exact language, fallback to english
    lang_map = LABEL_ACTIONS.get(lang, LABEL_ACTIONS.get("en", {}))
    key = label.lower()
    for k in lang_map:
        if k in key:
            return lang_map[k]
    # fallback to English if not found and current lang wasn't English
    if lang != "en":
        en_map = LABEL_ACTIONS.get("en", {})
        for k in en_map:
            if k in key:
                return en_map[k]
    # ultimate default: return the raw label and a generic action (localized if possible)
    generic = {
        "en": "Obstacle ahead — be cautious",
        "ar": "عائق أمامك — احذر",
        "tr": "Önde engel — dikkatli olun",
    }
    return (label, generic.get(lang, generic["en"]))

# =========================
# Speech worker
# =========================
class Speaker:
    """TTS speaker that prefers an offline, low-latency `pyttsx3` backend when available.
    Falls back to `gTTS` + `pygame` playback (MP3) otherwise. Designed to be safe in
    headless/CI environments where audio devices are missing.
    """
    def __init__(self):
        self.q = queue.Queue(maxsize=8)
        self.stop_event = threading.Event()

        # Try to initialize pygame mixer; if it fails, we continue in dry-run mode.
        try:
            pygame.mixer.init()
            self.audio_available = True
        except Exception as e:
            print(f"[WARN] pygame.mixer.init() failed: {e}")
            self.audio_available = False

        # Language and fast-tts preference
        self.lang = os.getenv("TTS_LANG", "en")
        self.fast_tts = os.getenv("FAST_TTS", "1") in ("1", "true", "True")

        # Try to import pyttsx3 for offline, low-latency TTS
        try:
            import pyttsx3

            self._pyttsx3 = pyttsx3
        except Exception:
            self._pyttsx3 = None

        # Start the worker thread
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
        # Initialize pyttsx3 engine if requested and available
        engine = None
        if self.fast_tts and self._pyttsx3 is not None:
            try:
                engine = self._pyttsx3.init()
            except Exception as e:
                print(f"[WARN] pyttsx3 init failed: {e}")
                engine = None

        while not self.stop_event.is_set():
            try:
                text = self.q.get(timeout=0.2)
            except queue.Empty:
                continue

            # If both pyttsx3 and audio device are unavailable, dry-run print
            if engine is None and not getattr(self, "audio_available", False):
                print(f"[TTS-DRY-RUN]: {text}")
                continue

            # Prefer pyttsx3 for low-latency live speech when available
            if engine is not None:
                try:
                    engine.say(text)
                    engine.runAndWait()
                    continue
                except Exception as e:
                    print(f"[WARN] pyttsx3 speak failed, falling back: {e}")

            # Fallback: gTTS -> pygame playback (may have MP3 decoding latency)
            try:
                tts = gTTS(text=text, lang=self.lang)
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
        try:
            pygame.mixer.quit()
        except Exception:
            pass


# =========================
# Sentence-boundary detection for streaming TTS
# =========================
def _find_sentence_end(text: str) -> int:
    """
    Finds the end of a sentence (. or ! or ?)
    Ignores dots that are between numbers (like 1.5 cm)
    """
    match = re.search(r"(?<!\d)[.!?](?!\d)", text)
    if match:
        return match.end()
    return -1


# =========================
# Prompt building - different style depending on the situation
# =========================
def build_prompt(reason, distance_cm, last_summary, custom_question=None):
    pm = get_prompt_manager()
    return pm.get_prompt(reason, distance=distance_cm, last_summary=last_summary, custom_question=custom_question, lang=os.getenv("TTS_LANG", "en"))


# =========================
# AI description (GitHub Models) - streamed
# =========================
def describe_frame(client, frame, reason, distance_cm, last_summary=None,
                    custom_question=None, on_sentence=None):
    ok, buffer = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 75])
    if not ok:
        return "I couldn't capture the scene."

    img_b64 = base64.b64encode(buffer).decode("utf-8")
    # If running in mock/headless mode, return a simulated response and
    # optionally stream sentences via on_sentence without making network calls.
    prompt = build_prompt(reason, distance_cm, last_summary, custom_question)
    if MOCK_AI:
        if custom_question:
            simulated = f"Answer: simulated response to '{custom_question}'."
        elif reason == "obstacle_detected":
            simulated = "Obstacle ahead. Stop."
        elif reason in ("button_request", "user_help_key"):
            simulated = "Open area ahead, one person to your left. Move right."
        else:
            simulated = "Clear."

        if on_sentence:
            # naive sentence split, stream sentence(s)
            for s in re.split(r'(?<=[.!?])\s+', simulated):
                s = s.strip()
                if s:
                    on_sentence(s)
        return simulated


def make_speech_decision(client, frame, reason, distance_cm, last_summary=None, dets=None, scene_score=None, speech_mode='quiet', lang: str = None):
    """Ask the prompt manager to decide whether to speak.
    Returns (should_speak: bool, text: str).
    """
    pm = get_prompt_manager()
    key = 'speak_decision'
    if speech_mode in ('quiet', 'verbose', 'urgent'):
        key = f'speak_decision_{speech_mode}'
    prompt = pm.get_prompt(key, distance=distance_cm, last_summary=last_summary)

    # If mocking, use an improved heuristic that mirrors real-model behavior
    if MOCK_AI:
        # Basic decision based on detections and scene score
        has_det = bool(dets)
        score = float(scene_score) if scene_score is not None else 0.0
        # thresholds
        change_thresh = SCENE_CHANGE_THRESHOLD
        if speech_mode == 'quiet':
            speak_cond = has_det and (score > change_thresh or (distance_cm is not None and distance_cm < OBSTACLE_THRESHOLD_CM))
        elif speech_mode == 'verbose':
            speak_cond = has_det or (score > max(8.0, change_thresh * 0.5))
        else:  # urgent
            speak_cond = has_det or (distance_cm is not None and distance_cm < OBSTACLE_THRESHOLD_CM) or (score > max(6.0, change_thresh * 0.4))

        if not speak_cond:
            return False, ''

        # build a varied short utterance using detection info when available
        label = 'obstacle'
        cx = 0.5
        if has_det:
            try:
                label = dets[0][0]
                cx = dets[0][2]
            except Exception:
                pass

        side = 'center'
        if cx < 0.4:
            side = 'left'
        elif cx > 0.6:
            side = 'right'

        # choose action from map_label_to_action (respect language)
        name, action = map_label_to_action(label, lang=lang)

        variants = []
        if speech_mode == 'urgent':
            variants = [f"{name} {side}, {action}", f"{name} ahead on your {side}. {action}"]
        elif speech_mode == 'verbose':
            variants = [f"{name} on your {side}, about {distance_cm or 'a few'} cm; {action}", f"{name} to the {side}, {action}"]
        else:
            variants = [f"{name} on your {side}. {action}", f"{name} {side}. {action}"]

        utter = random.choice(variants)
        return True, utter

    # For real model: ask the model using the prompt as a custom question
    text = describe_frame(client, frame, reason, distance_cm, last_summary=last_summary, custom_question=prompt)
    if not text:
        return False, ''
    t = text.strip()
    if t.upper().startswith('SILENT') or t.lower().startswith('clear'):
        return False, ''
    if t.upper().startswith('SPEAK:'):
        return True, t.split(':', 1)[1].strip()
    # default: speak the returned text
    return True, t

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
                max_tokens=60,
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

                if on_sentence:
                    idx = _find_sentence_end(text_buffer)
                    while idx != -1:
                        sentence = text_buffer[: idx + 1].strip()
                        text_buffer = text_buffer[idx + 1:]
                        if sentence:
                            on_sentence(sentence)
                        idx = _find_sentence_end(text_buffer)

            if on_sentence:
                trailing = text_buffer.strip()
                if trailing:
                    on_sentence(trailing)

            return full_text.strip() or "Clear."

        except Exception as e:
            print(f"[WARN] Network retry {attempt + 1}: {e}")

            if started_streaming:
                trailing = text_buffer.strip()
                if trailing and on_sentence:
                    on_sentence(trailing)
                return full_text.strip() or "Network issue."

            time.sleep(0.8 * (2 ** attempt))

    return "Network issue."


# =========================
# Main app
# =========================
def main():
    # Build a real client only when not mocking AI responses
    client = None
    if not MOCK_AI:
        client = build_client()
    speaker = Speaker()
    # Start tuning GUI in a daemon thread if Tk is available
    try:
        if TK_AVAILABLE:
            gui_thread = Thread(target=start_tuning_gui, daemon=True)
            gui_thread.start()
    except Exception:
        pass
    # Load runtime config and apply to globals
    cfg = load_config()
    global YOLO_CONF_THRESH, YOLO_LABEL_THRESHOLDS
    YOLO_CONF_THRESH = float(cfg.get("yolo_conf_thresh", YOLO_CONF_THRESH))
    YOLO_LABEL_THRESHOLDS.update(cfg.get("label_thresholds", {}))
    global SPEECH_MODE
    SPEECH_MODE = cfg.get("speech_mode", SPEECH_MODE)
    ultrasonic = UltrasonicSensor()
    button = ButtonTrigger()
    scene_detector = SceneChangeDetector()

    # Allow numeric camera indices via env var (VIDEO_SOURCE="0")
    source = None
    try:
        # If VIDEO_SOURCE looks like an integer, use camera index
        if str(VIDEO_SOURCE).isdigit():
            source = int(VIDEO_SOURCE)
        else:
            source = VIDEO_SOURCE
    except Exception:
        source = VIDEO_SOURCE

    # If running headless, do not open a real VideoCapture; generate dummy frames.
    cap = None
    if not SMARTCANE_HEADLESS:
        cap = cv2.VideoCapture(source)
        if not cap.isOpened():
            # Try fallback to default camera index 0
            print(f"[WARN] Could not open video source '{VIDEO_SOURCE}', trying camera 0.")
            cap = cv2.VideoCapture(0)
            if not cap.isOpened():
                raise RuntimeError("Could not open camera / video source.")

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
        "last_summary": "",     # what we last told the model was said (context for the prompt)
        "_prev_spoken": "",     # what was actually last spoken out loud (for dedup)
    }

    # Haptic driver (optional) - can be toggled at runtime via config/UI
    ENABLE_HAPTIC = cfg.get("enable_haptic", os.getenv("ENABLE_HAPTIC", "0") in ("1", "true", "True"))
    vibrator = Vibrator() if ENABLE_HAPTIC else None

    def enqueue_trigger(frame, reason, distance_cm, custom_question=None):
        if state["busy"] and not custom_question:
            return
        if request_q.full():
            return
        state["last_trigger"] = time.time()
        request_q.put((frame.copy(), reason, distance_cm, custom_question))

    def ai_worker():
        while not stop_event.is_set():
            try:
                frame, reason, distance_cm, custom_question = request_q.get(timeout=0.2)
            except queue.Empty:
                continue

            state["busy"] = True
            state["status"] = f"Analyzing ({reason})...."

            if reason == "live_mode" and not custom_question:
                # Ask the model (or mock) whether to speak, using the speak_decision prompt.
                # Precompute detections and scene score to pass to the decision helper
                dets = classify_frame_yolo(frame, conf_thresh=YOLO_CONF_THRESH, max_results=3)
                scene_score = scene_detector.score(frame)
                should_speak, result_text = make_speech_decision(
                    client,
                    frame,
                    reason,
                    distance_cm,
                    last_summary=state["last_summary"],
                    dets=dets,
                    scene_score=scene_score,
                    speech_mode=SPEECH_MODE,
                    lang=speaker.lang,
                )

                if not should_speak:
                    # Update last_summary so we don't re-trigger repeatedly
                    state["last_summary"] = "Clear."
                    state["status"] = "Clear."
                    print(f"[LIVE] Decision: SILENT")
                else:
                    # result_text contains the short utterance the model suggests
                    state["status"] = result_text[:90]
                    # Deduplicate against last spoken
                    if text_similarity(result_text, state["_prev_spoken"]) >= TEXT_SIMILARITY_SKIP:
                        print(f"[LIVE] Too similar to last spoken line, staying quiet: {result_text}")
                        state["last_summary"] = result_text
                    else:
                        speaker.say(result_text)
                        state["_prev_spoken"] = result_text
                        state["last_summary"] = result_text
            else:
                # Obstacle / button / help / voice-question: always spoken immediately,
                # sentence by sentence, no filtering (these situations are always relevant).
                def _on_sentence(sentence):
                    speaker.say(sentence)
                    state["status"] = sentence[:90]

                text = describe_frame(
                    client, frame, reason, distance_cm,
                    last_summary=state["last_summary"],
                    custom_question=custom_question,
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

        if SMARTCANE_HEADLESS:
            speaker.say("Microphone disabled in headless mode.")
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
            # In headless mode, simulate no audio
            if SMARTCANE_HEADLESS:
                state["is_listening"] = False
                state["status"] = "Microphone disabled in headless mode."
                speaker.say("No microphone in headless mode.")
                return
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
        headless_iterations = int(os.getenv("HEADLESS_ITER", "6"))
        headless_count = 0
        while True:
            if SMARTCANE_HEADLESS:
                # generate a simple gray frame for testing
                frame = np.full((480, 640, 3), 120, dtype=np.uint8)
                ok = True
                headless_count += 1
                if headless_count > headless_iterations:
                    break
            else:
                ok, frame = cap.read()
                if not ok:
                    break

            distance_cm = ultrasonic.read_cm()
            state["distance_cm"] = distance_cm
            # Sync YOLO threshold from GUI slider if present
            try:
                YOLO_CONF_THRESH = float(global_yolo_conf)
            except Exception:
                pass
            now = time.time()

            # ---- Live mode: only call the AI when something actually changed ----
            if (
                state["is_live_mode"]
                and not state["busy"]
                and not state["is_listening"]
            ):
                elapsed = now - state["last_trigger"]
                change_score = scene_detector.score(frame)

                should_trigger = False
                if elapsed >= LIVE_HEARTBEAT_SEC:
                    should_trigger = True  # long-silence safety check-in
                elif change_score >= SCENE_CHANGE_THRESHOLD and elapsed >= LIVE_MIN_INTERVAL_SEC:
                    should_trigger = True

                if should_trigger:
                    enqueue_trigger(frame, "live_mode", distance_cm)
                    scene_detector.update_reference(frame)

            # ---- Obstacle: always immediate, edge-triggered (independent of live mode) ----
            near = distance_cm is not None and distance_cm <= OBSTACLE_THRESHOLD_CM
            if near and not state["was_near"] and not state["is_listening"]:
                # Try local YOLO classification first (offline)
                detections = classify_frame_yolo(frame)
                handled = False
                if detections:
                    # pick the highest confidence detection
                    detections.sort(key=lambda x: x[1], reverse=True)
                    label, conf, cx, cy = detections[0]
                    name, action = map_label_to_action(label, lang=speaker.lang)

                    # determine left/center/right from cx
                    side = "center"
                    if cx < 0.4:
                        side = "left"
                    elif cx > 0.6:
                        side = "right"

                    # Short spoken guidance
                    guidance = f"{name} on your {side}. {action}."
                    speaker.say(guidance)
                    state["_prev_spoken"] = guidance
                    # haptic cue
                    if vibrator is not None:
                        vibrator.pulse(side if side in ("left","right") else "both")
                    handled = True

                if not handled:
                    enqueue_trigger(frame, "obstacle_detected", distance_cm)

            state["was_near"] = near

            if button.rising_edge():
                enqueue_trigger(frame, "button_request", distance_cm)

            # ---- Overlay ----
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

            # Overlay current runtime config: YOLO threshold and haptic status
            cv2.putText(
                frame,
                f"YOLO Thr (GUI): {float(global_yolo_conf):.2f}   Active: {YOLO_CONF_THRESH:.2f} ([ ] to change)",
                (10, 150),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (200, 200, 0),
                1,
            )

            cv2.putText(
                frame,
                f"Haptic: {'ON' if ENABLE_HAPTIC else 'OFF'} (P to toggle)",
                (10, 180),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (200, 200, 0),
                1,
            )

            cv2.putText(
                frame,
                f"Speech mode: {SPEECH_MODE} (M to cycle)",
                (10, 210),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (200, 200, 0),
                1,
            )

            # Only show GUI when not running headless
            if not SMARTCANE_HEADLESS:
                cv2.imshow(WINDOW_NAME, frame)
                key = cv2.waitKey(60) & 0xFF
            else:
                # In headless mode, there's no interactive key handling
                key = None

            if key in (ord("s"), ord("S")):
                state["is_live_mode"] = not state["is_live_mode"]
                if state["is_live_mode"]:
                    # start fresh so the first frame after activation is always described
                    state["last_summary"] = ""
                    state["_prev_spoken"] = ""
                    scene_detector.reference = None
                    speaker.say("Live mode activated")
                else:
                    speaker.say("Live mode deactivated")
            elif key in (ord("v"), ord("V")):
                if voice_state["stream"] is None and not state["is_listening"]:
                    start_recording()
                elif voice_state["stream"] is not None:
                    stop_recording_and_process(frame.copy(), distance_cm)
            elif key in (ord("h"), ord("H")):
                enqueue_trigger(frame, "user_help_key", distance_cm)
            elif key == ord('['):
                # decrease YOLO global threshold
                YOLO_CONF_THRESH = max(0.01, YOLO_CONF_THRESH - 0.05)
                cfg["yolo_conf_thresh"] = YOLO_CONF_THRESH
                save_config(cfg)
                speaker.say(f"Detection threshold {YOLO_CONF_THRESH:.2f}")
            elif key == ord(']'):
                # increase YOLO global threshold
                YOLO_CONF_THRESH = min(0.99, YOLO_CONF_THRESH + 0.05)
                cfg["yolo_conf_thresh"] = YOLO_CONF_THRESH
                save_config(cfg)
                speaker.say(f"Detection threshold {YOLO_CONF_THRESH:.2f}")
            elif key in (ord('p'), ord('P')):
                # toggle haptic
                ENABLE_HAPTIC = not ENABLE_HAPTIC
                cfg["enable_haptic"] = ENABLE_HAPTIC
                save_config(cfg)
                if ENABLE_HAPTIC:
                    vibrator = Vibrator()
                    speaker.say("Haptics enabled")
                else:
                    vibrator = None
                    speaker.say("Haptics disabled")
            elif key in (ord("q"), ord("Q")):
                break
            elif key in (ord('e'), ord('E')):
                # Launch prompt editor GUI in a background thread
                try:
                    pm = get_prompt_manager()
                    Thread(target=pm.open_gui_editor, daemon=True).start()
                    speaker.say("Prompt editor opened")
                except Exception as e:
                    print(f"[WARN] Could not open prompt editor: {e}")
            elif key in (ord('m'), ord('M')):
                # cycle speech mode: quiet -> verbose -> urgent -> quiet
                try:
                    modes = ['quiet', 'verbose', 'urgent']
                    idx = modes.index(SPEECH_MODE) if SPEECH_MODE in modes else 0
                    SPEECH_MODE = modes[(idx + 1) % len(modes)]
                    cfg['speech_mode'] = SPEECH_MODE
                    save_config(cfg)
                    speaker.say(f"Speech mode {SPEECH_MODE}")
                except Exception as e:
                    print(f"[WARN] Could not change speech mode: {e}")

    finally:
        stop_event.set()
        # Clean up resources if they were created.
        try:
            if cap is not None:
                cap.release()
        except Exception:
            pass

        try:
            cv2.destroyAllWindows()
        except Exception:
            pass

        try:
            speaker.stop()
        except Exception:
            pass


if __name__ == "__main__":
    main()
