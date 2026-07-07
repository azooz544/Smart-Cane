"""
Central configuration for the Smart Cane AI Assistant.
All tunable parameters are defined here for easy adjustment.
"""

import os

# =========================
# AI Model Settings
# =========================
MODEL = "gpt-4o-mini"
API_BASE_URL = "https://models.inference.ai.azure.com"
MAX_RESPONSE_TOKENS = 120
REQUEST_RETRIES = 3

# =========================
# Camera Settings
# =========================
CAMERA_INDEX = 0
JPEG_QUALITY = 75

# =========================
# Hardware Sensor Settings
# =========================
ULTRASONIC_TRIGGER_PIN = 23
ULTRASONIC_ECHO_PIN = 24
ULTRASONIC_MAX_DISTANCE_M = 4.0
BUTTON_PIN = 17
OBSTACLE_THRESHOLD_CM = 120.0

# =========================
# Timing Settings
# =========================
LIVE_INTERVAL_SEC = 10.0
TRIGGER_COOLDOWN_SEC = 3.0

# =========================
# Audio Settings
# =========================
VOICE_RECORD_SECONDS = 5
VOICE_SAMPLE_RATE = 44100
TTS_LANGUAGE = "en"

# =========================
# UI Settings
# =========================
WINDOW_NAME = "Smart Cane (S=Live, V=Voice, H=Help, Q=Quit)"


def get_api_key() -> str:
    """Retrieve the GitHub Models API key from environment variables."""
    api_key = os.getenv("GITHUB_TOKEN")
    if not api_key:
        raise RuntimeError(
            "Set the GITHUB_TOKEN environment variable before running this script."
        )
    return api_key
