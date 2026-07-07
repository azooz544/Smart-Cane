"""
Voice recognition module for capturing user questions.

Records audio from the microphone, saves to a temporary file,
and transcribes using Google Speech Recognition.
"""

import logging
import tempfile
import os

import sounddevice as sd
import speech_recognition as sr
from scipy.io import wavfile

from src.config import VOICE_RECORD_SECONDS, VOICE_SAMPLE_RATE

logger = logging.getLogger(__name__)


def listen_for_question(language: str = "en-US") -> str | None:
    """
    Record audio from the microphone and transcribe it.

    Args:
        language: BCP-47 language code for speech recognition.

    Returns:
        Transcribed text string, or None if recognition failed.
    """
    logger.info("Microphone recording started (%d seconds)...", VOICE_RECORD_SECONDS)

    try:
        recording = sd.rec(
            int(VOICE_RECORD_SECONDS * VOICE_SAMPLE_RATE),
            samplerate=VOICE_SAMPLE_RATE,
            channels=1,
            dtype="int16",
        )
        sd.wait()
        logger.info("Recording complete. Processing voice...")

        # Write to a secure temporary file
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            temp_path = tmp.name
            wavfile.write(temp_path, VOICE_SAMPLE_RATE, recording)

        # Transcribe
        recognizer = sr.Recognizer()
        with sr.AudioFile(temp_path) as source:
            audio_data = recognizer.record(source)

        question_text = recognizer.recognize_google(audio_data, language=language)
        logger.info("User asked: %s", question_text)
        return question_text

    except sr.UnknownValueError:
        logger.warning("Could not understand the audio.")
        return None
    except Exception as e:
        logger.error("Microphone/recognition error: %s", e)
        return None
    finally:
        # Clean up temporary file
        try:
            if "temp_path" in locals() and os.path.exists(temp_path):
                os.remove(temp_path)
        except OSError:
            pass
