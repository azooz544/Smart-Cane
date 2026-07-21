import os
import importlib
import numpy as np

# Ensure headless+mock mode before importing gemini
os.environ['SMARTCANE_HEADLESS'] = '1'
os.environ['MOCK_AI'] = '1'

import gemini
importlib.reload(gemini)


class TTSWriter:
    def __init__(self, outdir="tts_outputs", lang=None):
        self.outdir = outdir
        os.makedirs(self.outdir, exist_ok=True)
        self.count = 0
        self.verify_playback = os.getenv("VERIFY_PLAYBACK", "0") in ("1", "true", "True")
        # Allow language override; default from env TTS_LANG or 'en'
        self.lang = lang or os.getenv("TTS_LANG", "en")

    def write(self, sentence, prefix="test"):
        self.count += 1
        filename = os.path.join(self.outdir, f"{prefix}_{self.count:02d}.mp3")
        try:
            from gtts import gTTS
            fp = None
            tts = gTTS(text=sentence, lang=self.lang)
            tts.save(filename)
            print(f"WROTE: {filename}")
        except Exception as e:
            print(f"[WARN] Could not write TTS file: {e}")
            return

        if self.verify_playback:
            try:
                import pygame

                try:
                    pygame.mixer.init()
                except Exception:
                    # mixer may already be initialized or fail on some systems
                    pass

                pygame.mixer.music.load(filename)
                pygame.mixer.music.play()
                # wait for playback to finish (with a safety timeout)
                start = __import__("time").time()
                while pygame.mixer.music.get_busy():
                    time.sleep(0.1)
                    if __import__("time").time() - start > 10.0:
                        print("[WARN] Playback timed out")
                        break
            except Exception as e:
                print(f"[WARN] Playback verification failed: {e}")


def stream_printer(sentence):
    print("STREAM:", sentence)
    # also save TTS audio for the streamed sentence
    try:
        tts_writer.write(sentence, prefix="stream")
    except Exception as e:
        print(f"[WARN] tts_writer failed: {e}")


def run_tests():
    print('SMARTCANE_HEADLESS=', gemini.SMARTCANE_HEADLESS)
    print('MOCK_AI=', gemini.MOCK_AI)
    global tts_writer
    tts_writer = TTSWriter()

    # 1) Obstacle detected
    frame = np.full((480, 640, 3), 200, dtype=np.uint8)
    print('\n== Obstacle test ==')
    out = gemini.describe_frame(None, frame, reason='obstacle_detected', distance_cm=45.0, on_sentence=stream_printer)
    print('Result:', out)

    # 2) Button/help request
    print('\n== Help request test ==')
    out = gemini.describe_frame(None, frame, reason='user_help_key', distance_cm=None, on_sentence=stream_printer)
    print('Result:', out)

    # 3) Live mode (clear)
    print('\n== Live mode test ==')
    out = gemini.describe_frame(None, frame, reason='live_mode', distance_cm=None, last_summary='', on_sentence=stream_printer)
    print('Result:', out)

    # 4) Custom question
    print('\n== Custom question test ==')
    out = gemini.describe_frame(None, frame, reason='user_voice_question', distance_cm=None, custom_question='What is this object?', on_sentence=stream_printer)
    print('Result:', out)


if __name__ == '__main__':
    run_tests()
