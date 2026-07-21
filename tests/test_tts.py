import os
import time

os.environ.setdefault("SMARTCANE_HEADLESS", "1")
os.environ.setdefault("MOCK_AI", "1")

from gemini import Speaker


def test_speaker_headless_no_crash():
    """Ensure Speaker can be created and used in headless mode without raising."""
    s = Speaker()
    try:
        s.say("Unit test speech: hello")
        # allow worker to pick up the item
        time.sleep(0.2)
    finally:
        s.stop()

