import os
import sys
import importlib
import cv2
import numpy as np

# Ensure headless mode
os.environ['SMARTCANE_HEADLESS'] = os.environ.get('SMARTCANE_HEADLESS', '1')

def load_gemini():
    try:
        gem = importlib.import_module('gemini')
        return importlib.reload(gem)
    except Exception as e:
        print(f"Failed importing gemini: {e}")
        return None

def main():
    gem = load_gemini()
    if gem is None:
        return 1

    MODEL = gem.try_load_yolo()
    if MODEL is None:
        print("No YOLO model loaded. Ensure 'yolov8n.pt' exists and 'ultralytics' is installed.")
        return 0

    img_path = os.getenv('YOLO_TEST_IMAGE')
    frame = None
    if img_path and os.path.exists(img_path):
        frame = cv2.imread(img_path)
        print(f"Loaded test image from {img_path}")
    else:
        # If no image provided, generate a simple sample scene image
        print("No YOLO_TEST_IMAGE set or file not found; creating sample image 'sample_scene.jpg'")
        sample = 'sample_scene.jpg'
        if not os.path.exists(sample):
            img = np.full((480, 640, 3), 200, dtype=np.uint8)
            cv2.rectangle(img, (80, 120), (200, 420), (50, 50, 200), -1)
            cv2.putText(img, 'person', (82, 118), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255,255,255), 2)
            cv2.rectangle(img, (480, 100), (520, 420), (100, 100, 100), -1)
            cv2.putText(img, 'pole', (482, 98), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255,255,255), 2)
            cv2.imwrite(sample, img)
        frame = cv2.imread(sample)

    if frame is None:
        print("No test image available. Set YOLO_TEST_IMAGE to a valid image path or connect a camera.")
        return

    # Run classification
    print("Running local YOLO classification...")
    dets = gem.classify_frame_yolo(frame, conf_thresh=0.3, max_results=10)
    if not dets:
        print("No detections (or model not confident).")
        return

    print("Detections:")
    for i, (label, conf, cx, cy) in enumerate(dets, 1):
        side = 'center'
        if cx < 0.4:
            side = 'left'
        elif cx > 0.6:
            side = 'right'
        name, action = gem.map_label_to_action(label)
        print(f" {i}. {label} (conf={conf:.2f}) at {cx:.2f},{cy:.2f} -> side={side}; action='{action}'")

    # Optionally draw boxes and save (best-effort)
    try:
        res = MODEL(frame, imgsz=640)
        out_img = frame.copy()
        r = res[0]
        boxes = getattr(r, 'boxes', None)
        if boxes is not None:
            for b in boxes:
                try:
                    xyxy = b.xyxy[0].cpu().numpy()
                    x1,y1,x2,y2 = xyxy.astype(int)
                    cls = int(b.cls[0]) if hasattr(b, 'cls') else int(b.cls)
                    conf = float(b.conf[0]) if hasattr(b, 'conf') else float(b.conf)
                    label = (getattr(r, 'names', {}) or {}).get(cls, str(cls))
                    cv2.rectangle(out_img, (x1,y1), (x2,y2), (0,255,0), 2)
                    cv2.putText(out_img, f"{label} {conf:.2f}", (x1, max(10,y1-5)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255,255,255),1)
                except Exception:
                    continue
            out_path = 'yolo_output.jpg'
            cv2.imwrite(out_path, out_img)
            print(f"Wrote annotated image to {out_path}")
    except Exception as e:
        print(f"Could not write annotated image: {e}")

    print('Done')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
