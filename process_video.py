import os
import cv2
import time
import importlib

# Run in headless+mock mode by default for safe testing
os.environ.setdefault('SMARTCANE_HEADLESS', '1')
os.environ.setdefault('MOCK_AI', '1')

import gemini
importlib.reload(gemini)

from test_harness import TTSWriter


def process(video_path=None, frame_interval=30, out_prefix='proc'):
    video_path = video_path or os.getenv('VIDEO_SOURCE', 'aaa.mp4')
    if not os.path.exists(video_path):
        print('Video not found:', video_path)
        return

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print('Could not open video:', video_path)
        return

    tts = TTSWriter()
    frame_idx = 0
    saved = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break
        frame_idx += 1
        # sample every N frames
        if frame_idx % frame_interval != 0:
            continue

        # run local YOLO detection first
        dets = gemini.classify_frame_yolo(frame, conf_thresh=float(os.getenv('YOLO_CONF_THRESH', '0.4')), max_results=5)
        if dets:
            dets.sort(key=lambda x: x[1], reverse=True)
            label, conf, cx, cy = dets[0]
            name, action = gemini.map_label_to_action(label)
            side = 'center'
            if cx < 0.4:
                side = 'left'
            elif cx > 0.6:
                side = 'right'
            guidance = f"{name} on your {side}. {action}."
            print(f"[{frame_idx}] GUIDANCE: {guidance}")
            tts.write(guidance, prefix=out_prefix)
        else:
            # fallback to AI/mock description
            text = gemini.describe_frame(None, frame, reason='live_mode', distance_cm=None, last_summary='')
            print(f"[{frame_idx}] AI fallback: {text}")
            tts.write(text, prefix=out_prefix)

        # save annotated frame for inspection
        try:
            out_path = f"{out_prefix}_{frame_idx}.jpg"
            cv2.imwrite(out_path, frame)
            saved += 1
        except Exception as e:
            print('Could not save frame:', e)

    cap.release()
    print('Done. Wrote', saved, 'frames and TTS files in', tts.outdir)


if __name__ == '__main__':
    import sys
    p = sys.argv[1] if len(sys.argv) > 1 else None
    process(p)
