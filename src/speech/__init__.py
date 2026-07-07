"""Speech synthesis and voice recognition module."""

from src.speech.speaker import Speaker
from src.speech.listener import listen_for_question

__all__ = ["Speaker", "listen_for_question"]
