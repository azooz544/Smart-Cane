# Smart Cane AI Assistant

An AI-powered navigation assistant for visually impaired users, built as part of a mechatronics engineering project. The system combines real-time computer vision, generative AI scene understanding, and voice interaction to help users perceive obstacles and navigate their environment safely — all delivered through natural spoken feedback.

---

## Project Overview

The Smart Cane AI Assistant transforms a standard camera feed into an intelligent, speaking guide for the visually impaired. A live video stream is continuously analyzed by a multimodal AI model (GPT-4o-mini via GitHub Models), which identifies obstacles, describes the surrounding scene, and recommends safe movement — all communicated back to the user through synthesized speech.

The system is designed to be **interactive rather than passive**: instead of continuously narrating everything in view, it responds to explicit triggers — a live-mode toggle, a manual help request, a spoken question, a hardware button press, or a nearby obstacle detected by an ultrasonic sensor. This keeps the audio feedback relevant, reduces cognitive load on the user, and conserves API usage.

---

## Key Features

- **Real-Time Scene Analysis** — Captures live video frames using OpenCV and sends them to a generative AI vision model for interpretation.
- **Obstacle & Hazard Detection** — The AI identifies objects and hazards directly in front of the camera and suggests a safe path forward.
- **Interactive Voice Q&A Mode** — Users can ask free-form questions about their surroundings ("What's in front of me?", "Is there a chair nearby?") using live microphone input.
- **Natural Text-to-Speech Feedback** — Responses are converted to high-quality, natural-sounding speech and played back instantly.
- **Live Monitoring Mode** — An optional continuous-analysis mode that periodically re-describes the environment at a fixed interval.
- **Hardware Sensor Integration** — Supports an ultrasonic distance sensor to automatically trigger analysis when an obstacle is detected within range, and a physical push-button for manual triggering.
- **Non-Blocking, Multi-threaded Architecture** — Camera capture, AI inference, and audio playback all run on separate threads so the video feed never freezes while the AI "thinks."
- **Automatic Retry Logic** — Network requests to the AI model automatically retry with exponential backoff to handle transient connectivity issues.

---

## Tech Stack

| Category | Technology |
|---|---|
| **Computer Vision** | [OpenCV](https://opencv.org/) (`opencv-python`) |
| **Generative AI (Vision + Language)** | GitHub Models API (`gpt-4o-mini`), accessed via the `openai` Python SDK |
| **Speech Recognition** | `speech_recognition`, `sounddevice`, `scipy.io.wavfile` |
| **Text-to-Speech** | `gTTS` (Google Text-to-Speech) + `pygame` (audio playback) |
| **Hardware I/O (Sensors & Buttons)** | `gpiozero` (ultrasonic sensor, push button) |
| **Concurrency** | Python `threading` and `queue` for non-blocking real-time operation |
| **Language** | Python 3.10+ |

---

## Prerequisites

Before running this project, make sure you have the following:

1. **Python 3.10 or higher** installed.
2. **A working webcam** connected to your machine.
3. **A microphone** (required for Voice Question mode).
4. **A GitHub Personal Access Token** with access to GitHub Models, exposed via an environment variable named `GITHUB_TOKEN`.

   > This project authenticates with the GitHub Models inference endpoint (`https://models.inference.ai.azure.com`) using this token. **Never hardcode this token in source code** — always supply it through the environment variable below.

5. *(Optional, for full hardware integration)* A Raspberry Pi or compatible board with:
   - An **HC-SR04 ultrasonic sensor** wired to the configured trigger/echo GPIO pins.
   - A **push button** wired to the configured GPIO pin.

   On non-Raspberry Pi systems (e.g. Windows/macOS development machines), the hardware modules will gracefully disable themselves and the application will continue to run using software-only triggers (`S`, `V`, `H`, `Q`).

---

## Installation Steps

### 1. Clone the repository

```bash
git clone https://github.com/<your-username>/<your-repo-name>.git
cd <your-repo-name>
```

### 2. Create and activate a virtual environment (recommended)

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

> On Raspberry Pi, `gpiozero` will interface with real GPIO hardware. On other platforms, it is safe to leave installed — sensor and button classes will simply disable themselves if the hardware/library is unavailable.

### 4. Set your GitHub Models API token

**Windows (PowerShell):**
```powershell
$env:GITHUB_TOKEN="your_github_pat_here"
```

**macOS / Linux (bash/zsh):**
```bash
export GITHUB_TOKEN="your_github_pat_here"
```

> This environment variable must be set in every new terminal session before running the script, unless you configure it as a persistent system environment variable.

### 5. Run the application

```bash
python gemini.py
```

---

## Usage

Once the application starts, a live camera window will open. Control the assistant using the following keys:

| Key | Action |
|---|---|
| **S** | Toggle **Live Mode** on/off. When active, the AI automatically analyzes the scene at a fixed interval (every 10 seconds) and speaks a description without requiring manual input. |
| **V** | Activate **Voice Question Mode**. The system listens through the microphone for 5 seconds, transcribes your spoken question using speech recognition, and asks the AI to answer it based on the current camera view. |
| **H** | Trigger an immediate, one-time **Help/Description** request — the AI analyzes the current frame right away and speaks back a description of the scene and any hazards. |
| **Q** | **Quit** the application and safely release the camera and audio resources. |

### Automatic Triggers

In addition to manual key presses, the assistant will automatically request an AI analysis when:
- The **ultrasonic sensor** detects an obstacle within the configured threshold distance (default: 120 cm), or
- The **physical push button** is pressed (on supported hardware).

### On-Screen Status

The live video window displays:
- **LIVE: ON / OFF** — current state of Live Mode.
- **MIC: LISTENING...** — shown while a voice question is being recorded.
- The **last AI response** (truncated) as status text.
- The **current ultrasonic distance reading** (if a sensor is connected).

---

## Project Structure

```
Smart Cane/
├── gemini.py             # Main application entry point
├── interactive_cane.py   # Alternate/experimental interactive architecture
├── smart_talk_ai.py       # Standalone text-based AI chat prototype
├── yolov8n.pt             # (Optional) YOLOv8 nano weights for local object detection experiments
├── .gitignore
└── README.md
```

---

## Security Notes

- API keys and tokens must **never** be committed to source control. This project reads all credentials exclusively from environment variables.
- If a token is ever accidentally exposed (e.g. committed, shared, or logged), revoke it immediately from your GitHub account settings and issue a new one.

---

## Disclaimer

This project is an engineering prototype intended for research, learning, and demonstration purposes. It is **not** a certified medical or mobility device and should not be relied upon as a sole means of navigation or hazard avoidance for visually impaired individuals.
