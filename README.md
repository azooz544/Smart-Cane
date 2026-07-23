# 🦯 Smart Cane AI Assistant

> An AI-powered, real-time navigation assistant designed to help visually impaired users move through their surroundings safely — combining computer vision, generative AI, local object detection, and spoken feedback.

---

## 🌟 1. Project Title & Overview

**Smart Cane AI Assistant** turns a live camera feed into a smart, speaking companion. It continuously observes the environment, detects obstacles and people, and speaks concise, actionable guidance in the user's preferred language.

Whether the user is navigating a sidewalk, entering a room, or avoiding an unexpected object, the cane describes what it sees and recommends a safe next action — all in real time and natural speech.

### 🎯 Core Idea

Instead of a passive camera or traditional white cane, the Smart Cane acts as a **voice-first assistant**:

- 👁️ It sees through the camera.
- 🧠 It understands the scene using AI.
- 🗣️ It tells the user what is ahead, where it is, and what to do.

The assistant is intentionally **interactive rather than noisy**: it responds to user triggers, voice questions, sensor events, and live-mode scene changes.

---

## ✨ 2. Key Features

| Feature | Description |
|---|---|
| 🎥 **Real-Time Scene Understanding** | Captures live camera frames using OpenCV and analyzes them with GPT-4o-mini (via GitHub Models). |
| 🚧 **Obstacle & Hazard Detection** | Local YOLOv8 model (`yolov8n.pt`) identifies common obstacles such as people, poles, cars, stairs, and curbs — even offline. |
| 🎙️ **Voice Q&A Mode** | Users press a key or button to ask free-form spoken questions about their surroundings. |
| 🔊 **Multilingual Text-to-Speech** | Speaks guidance in English, Arabic, or Turkish via `pyttsx3` and fallback `gTTS` playback. |
| 🌐 **i18n Prompts** | All AI prompts, spoken labels, and action text are localized through `prompt_system.py`. |
| 📡 **Hardware Sensor Integration** | Optional HC-SR04 ultrasonic sensor, push button, and haptic vibration motors for hands-free triggering. |
| 🧠 **Smart Live Mode** | Periodically re-describes the scene only when something meaningful changes, reducing API calls and user cognitive load. |
| 🔧 **Runtime Tuning GUI** | Adjust YOLO confidence thresholds, speech mode, and haptic feedback on the fly. |
| ✅ **Headless Testing** | Run in `SMARTCANE_HEADLESS` + `MOCK_AI` mode without a camera or API key for CI and development. |

---

## ⚙️ 3. How It Works (System Architecture)

```
        ┌─────────────────┐
        │   Camera /      │
        │   Video Source  │
        └────────┬────────┘
                 │
                 ▼
        ┌──────────────────────┐
        │   OpenCV (cv2)       │
        │   Frame Capture      │
        └────────┬─────────────┘
                 │
        ┌────────▼────────┐
        │  YOLOv8 (local) │
        │  Object         │
        │  Detection      │
        └────────┬────────┘
                 │ detections
                 ▼
        ┌──────────────────────────┐     ┌─────────────────────────┐
        │   GPT-4o-mini (GitHub    │────▶│   Prompt System (i18n)  │
        │   Models) / Gemini       │     │   en / ar / tr prompts  │
        └────────┬─────────────────┘     └─────────────────────────┘
                 │
                 ▼
        ┌───────────────────────┐
        │  Text-to-Speech       │
        │  pyttsx3 / gTTS       │
        └────────┬──────────────┘
                 │
                 ▼
        ┌───────────────────────┐
        │  Speaker / Headphones │
        └───────────────────────┘
```

### Data Flow

1. **Capture** — OpenCV reads frames from the webcam or a video file.
2. **Local Detection** — YOLOv8 performs fast, offline object classification on each frame.
3. **Decision Layer** — The system decides whether to speak based on:
   - Ultrasonic sensor distance,
   - Scene-change score,
   - User keypress or voice input,
   - Last spoken summary (to avoid repetition).
4. **AI Interpretation** — For complex scenes or voice questions, the frame and prompt are sent to GPT-4o-mini or Gemini.
5. **Localization** — `prompt_system.py` selects the correct language template and maps detected labels to localized actions.
6. **Speech Output** — Guidance is converted to speech and played back to the user.
7. **Haptic Feedback** — Optional vibration motors pulse left or right to reinforce directional guidance.

---

## 📋 4. Prerequisites & Requirements

### Software

- **Python** `3.10` or higher
- **OpenCV** compatible camera (built-in or USB webcam)
- **Microphone** — required for Voice Question mode
- A **GitHub Personal Access Token** with GitHub Models access, exposed as `GITHUB_TOKEN`

### Optional Hardware

On a Raspberry Pi or similar board:

- **HC-SR04 ultrasonic distance sensor** (trigger on GPIO 23, echo on GPIO 24 by default)
- **Push button** (GPIO 17 by default)
- **Vibration motors** for haptic left/right feedback (GPIO 5 / GPIO 6 by default)

On non-Raspberry Pi systems, the hardware modules gracefully disable themselves and the application runs in software-only mode.

---

## 🚀 5. Step-by-Step Installation & Setup

### 1. Clone the Repository

```bash
git clone https://github.com/azooz544/Smart-Cane.git
cd Smart-Cane
```

### 2. Create a Virtual Environment (Recommended)

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

Some systems may need native audio libraries:

```bash
# Ubuntu / Debian
sudo apt-get update
sudo apt-get install -y portaudio19-dev
```

### 4. (Optional) Download YOLO Weights

For offline object detection, place the pretrained weights in the project root:

```bash
# Example using Ultralytics CLI (requires ultralytics to be installed)
yolo download model=yolov8n
```

The file should be named `yolov8n.pt`.

### 5. Set Your API Token

```bash
# macOS / Linux / WSL
export GITHUB_TOKEN="ghp_your_github_pat_here"

# Windows PowerShell
$env:GITHUB_TOKEN="ghp_your_github_pat_here"
```

> ⚠️ **Never commit your token.** It is read from the environment at runtime.

To use the alternate Google Gemini entry point (`interactive_cane.py` or `smart_talk_ai.py`), set a Google service-account JSON path or `GEMINI_API_KEY` instead.

---

## 🎮 6. Usage Instructions

### Run the Main Application

```bash
python gemini.py
```

A camera window will open. Use the following keyboard controls:

| Key | Action |
|---|---|
| **S** | Toggle **Live Mode** on/off. When active, the assistant periodically re-describes the scene when meaningful changes occur. |
| **V** | Toggle **Voice Question Mode**. Tap once to start recording, tap again to submit the question. |
| **H** | Trigger an immediate **Help/Description** request for the current frame. |
| **[** / **]** | Decrease / increase the YOLO detection confidence threshold. |
| **P** | Toggle **haptic feedback** (requires vibration hardware). |
| **M** | Cycle speech mode: `quiet` → `verbose` → `urgent`. |
| **E** | Open the **prompt editor GUI** to customize AI prompts on the fly. |
| **Q** | Quit the application. |

### Automatic Triggers

The assistant automatically analyzes the scene when:

- The **ultrasonic sensor** detects an obstacle within `120 cm`.
- The **physical push button** is pressed (on supported hardware).
- Live mode detects a significant scene change after the cooldown period.

### On-Screen Feedback

The camera window displays:

- `LIVE: ON / OFF` — current live mode state.
- `MIC: RECORDING` — while a voice question is being captured.
- The last AI response and current sensor distance.
- Runtime settings: YOLO threshold, haptic status, and speech mode.

### Alternative Entry Points

```bash
# Google Gemini-based interactive cane (pyttsx3 TTS)
python interactive_cane.py

# Text-only chat with Gemini
python smart_talk_ai.py

# Batch-process a video file offline
python process_video.py path/to/video.mp4

# Test local YOLO detection
python yolo_test.py

# Run headless unit tests
pytest -q
```

### Running Without Hardware

For development, CI, or testing without a camera, set:

```bash
export SMARTCANE_HEADLESS=1
export MOCK_AI=1
python gemini.py
```

This disables the camera, microphone, API calls, and hardware I/O so the application can run anywhere.

---

## 🧪 Testing

The repository includes a lightweight test suite:

```bash
pytest -q
```

Tests include:

- Label-to-action localization (`tests/test_label_actions.py`)
- Prompt manager save/load and i18n fallback (`tests/test_prompt_system.py`)
- TTS speaker initialization in headless mode (`tests/test_tts.py`)

---

## 🔒 Security Notes

- API keys and service-account credentials are read from **environment variables**.
- Never commit `.env` files, JSON keys, or tokens to source control.
- The `.gitignore` excludes model weights (`*.pt`), logs, and credential files.

---

## ⚠️ Disclaimer

This project is an engineering prototype for research, learning, and demonstration. It is **not** a certified medical or mobility device and should not be relied upon as the sole means of navigation or hazard avoidance for visually impaired individuals.
