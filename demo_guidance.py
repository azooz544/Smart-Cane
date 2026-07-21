import os
import importlib
import cv2
import numpy as np

# Headless mock
os.environ['SMARTCANE_HEADLESS'] = '1'
import gemini
importlib.reload(gemini)

from test_harness import TTSWriter


def make_sample_image(path='sample_scene.jpg'):
    # Create a simple sample image with boxes representing objects
    img = np.full((480, 640, 3), 200, dtype=np.uint8)
    # draw a 'person' rectangle center-left
    cv2.rectangle(img, (80, 120), (200, 420), (50, 50, 200), -1)
    cv2.putText(img, 'person', (82, 118), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255,255,255), 2)
    # draw a 'pole' on the right
    cv2.rectangle(img, (480, 100), (520, 420), (100, 100, 100), -1)
    cv2.putText(img, 'pole', (482, 98), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255,255,255), 2)
    cv2.imwrite(path, img)
    return path


def run_demo(image_path=None):
    if image_path is None:
        image_path = 'sample_scene.jpg'
        if not os.path.exists(image_path):
            make_sample_image(image_path)

    frame = cv2.imread(image_path)
    if frame is None:
        print('Could not read image', image_path)
        return

    # Try local detection
    dets = gemini.classify_frame_yolo(frame, conf_thresh=float(os.getenv('YOLO_CONF_THRESH', '0.3')) , max_results=5)

    tts = TTSWriter()

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
        print('GUIDANCE:', guidance)
        tts.write(guidance, prefix='demo')
    else:
        # Fall back to mocked AI summary
        text = gemini.describe_frame(None, frame, reason='obstacle_detected', distance_cm=None, custom_question=None, on_sentence=None)
        print('AI fallback guidance:', text)
        tts.write(text, prefix='demo')

    # Save annotated image using gemini's model if available
    try:
        model = gemini.try_load_yolo()
        if model is not None:
            res = model(frame)
            out = frame.copy()
            r = res[0]
            boxes = getattr(r, 'boxes', None)
            names = getattr(r, 'names', {}) or {}
            if boxes is not None:
                for b in boxes:
                    xyxy = b.xyxy[0].cpu().numpy()
                    x1,y1,x2,y2 = xyxy.astype(int)
                    cls = int(b.cls[0]) if hasattr(b,'cls') else int(b.cls)
                    label = names.get(cls, str(cls))
                    cv2.rectangle(out, (x1,y1), (x2,y2), (0,255,0), 2)
                    cv2.putText(out, label, (x1, max(10,y1-5)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255,255,255),2)
                cv2.imwrite('demo_annotated.jpg', out)
                print('Wrote demo_annotated.jpg')
    except Exception as e:
        print('Could not annotate image:', e)


if __name__ == '__main__':
    run_demo()
