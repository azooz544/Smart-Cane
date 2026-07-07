"""
Text-to-Speech (TTS) worker.

Runs speech synthesis on a background thread to avoid blocking
the main camera loop. Uses gTTS (online) with pygame for playback.
"""

import io
import logging
import queue
import threading
import time

import pygame
from gtts import gTTS

from src.config import TTS_LANGUAGE

logger = logging.getLogger(__name__)


class Speaker:
    """Non-blocking text-to-speech engine running on a dedicated thread."""

    def __init__(self, language: str = TTS_LANGUAGE, max_queue_size: int = 8):
        self._queue = queue.Queue(maxsize=max_queue_size)
        self._stop_event = threading.Event()
        self._language = language

        pygame.mixer.init()

        self._thread = threading.Thread(target=self._run, daemon=True, name="SpeakerThread")
        self._thread.start()
        logger.info("Speaker initialized (lang=%s).", language)

    def say(self, text: str) -> None:
        """
        Queue text for speech synthesis.

        If the queue is full, the message is silently dropped
        to prevent blocking the caller.
        """
        text = (text or "").strip()
        if not text:
            return

        logger.info("[AI SAYS]: %s", text)

        try:
            self._queue.put_nowait(text)
        except queue.Full:
            logger.warning("Speech queue full — dropping message.")

    def _run(self) -> None:
        """Background loop: dequeue text, synthesize, and play audio."""
        while not self._stop_event.is_set():
            try:
                text = self._queue.get(timeout=0.2)
            except queue.Empty:
                continue

            try:
                tts = gTTS(text=text, lang=self._language)
                fp = io.BytesIO()
                tts.write_to_fp(fp)
                fp.seek(0)

                pygame.mixer.music.load(fp)
                pygame.mixer.music.play()

                while pygame.mixer.music.get_busy() and not self._stop_event.is_set():
                    time.sleep(0.1)
            except Exception as e:
                logger.error("Audio playback failed: %s", e)

    def stop(self) -> None:
        """Signal the background thread to stop and release resources."""
        self._stop_event.set()
        self._thread.join(timeout=2.0)
        try:
            pygame.mixer.quit()
        except Exception:
            pass
        logger.info("Speaker stopped.")
