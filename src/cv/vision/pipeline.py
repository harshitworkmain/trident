"""Per-frame computer vision for the ROV camera, built from the models already in src/cv:

* YOLOv8n (src/cv/yolov8_model/yolov8n.pt): objects with confidence >= CONF; people are kept
  (in a rescue they are the point, unlike the original desktop demo which dropped them).
* Haar cascade + LBPH (src/cv/face_recognition/trainer.yml, names.json): faces, matched against
  the enrolled people (e.g. the rescue team); LBPH distance < LBPH_MATCH_MAX counts as a match.
* Distance: pinhole model D = W_real * f / w_pixels with per-class real widths. f defaults to the
  original calibration (700 px at 640 px width) and should be re-calibrated per camera (--focal-px);
  values are rough (+-30 % at best) and labelled approximate in the dashboard.

Needs opencv-contrib-python (cv2.face) and ultralytics; never imported by the API process.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

import cv2
import numpy as np

CV_DIR = Path(__file__).resolve().parents[1]
YOLO_WEIGHTS = CV_DIR / 'yolov8_model' / 'yolov8n.pt'
LBPH_MODEL = CV_DIR / 'face_recognition' / 'trainer.yml'
NAMES = CV_DIR / 'face_recognition' / 'names.json'
CONF = 0.4
LBPH_MATCH_MAX = 50.0              # LBPH distance: lower is closer; the original demo's threshold
FRAME_W = 640

# Typical real widths (m) for the pinhole estimate; people by shoulder width, faces by face width.
REAL_WIDTH_M = {'person': 0.45, 'face': 0.16, 'boat': 2.5, 'car': 1.8, 'truck': 2.5, 'bus': 2.55,
                'motorcycle': 0.8, 'bicycle': 0.6, 'dog': 0.3, 'cat': 0.2, 'cow': 0.7, 'horse': 0.6,
                'bottle': 0.07, 'chair': 0.5, 'backpack': 0.3, 'handbag': 0.3, 'suitcase': 0.45,
                'umbrella': 0.9, 'bench': 1.4, 'surfboard': 0.5}
COLORS = {'person': (61, 163, 232), 'face': (232, 163, 61), 'other': (161, 184, 63)}   # BGR


def estimate_distance(label: str, pixel_width: float, focal_px: float) -> Optional[float]:
    w = REAL_WIDTH_M.get(label)
    if w is None or pixel_width <= 0:
        return None
    return round(float(w * focal_px / pixel_width), 2)


@dataclass
class VisionPipeline:
    focal_px: float = 700.0
    yolo: object = None
    recognizer: object = None
    cascade: object = None
    names: Dict[str, str] = None

    @classmethod
    def load(cls, focal_px: float = 700.0, device: str = 'cpu') -> 'VisionPipeline':
        from ultralytics import YOLO
        yolo = YOLO(str(YOLO_WEIGHTS))
        yolo.to(device)
        recognizer = None
        if LBPH_MODEL.exists() and hasattr(cv2, 'face'):
            recognizer = cv2.face.LBPHFaceRecognizer_create()
            recognizer.read(str(LBPH_MODEL))
        cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
        names = json.loads(NAMES.read_text(encoding='utf-8')) if NAMES.exists() else {}
        return cls(focal_px, yolo, recognizer, cascade, names)

    def process(self, frame: np.ndarray) -> tuple:
        """(annotated BGR frame, detections dict) for one camera frame."""
        if frame.shape[1] != FRAME_W:
            frame = cv2.resize(frame, (FRAME_W, int(frame.shape[0] * FRAME_W / frame.shape[1])))
        out = frame.copy()
        objects: List[dict] = []
        for r in self.yolo(frame, conf=CONF, verbose=False):
            for box in r.boxes:
                x1, y1, x2, y2 = (int(v) for v in box.xyxy[0])
                label = self.yolo.names[int(box.cls[0])]
                dist = estimate_distance(label, x2 - x1, self.focal_px)
                objects.append({'label': label, 'confidence': round(float(box.conf[0]), 3), 'distance_m': dist,
                                'box': [x1, y1, x2, y2]})
                self._draw(out, (x1, y1, x2, y2), f"{label} {float(box.conf[0]):.0%}"
                           + (f" ~{dist:.1f} m" if dist is not None else ''), COLORS.get(label, COLORS['other']))
        faces = []
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        # scale step 1.1 (the desktop demo used 1.3): more face sizes are tried, so fewer faces are missed
        for (x, y, w, h) in self.cascade.detectMultiScale(gray, 1.1, 5, minSize=(40, 40)):
            name, match = 'Unknown', None
            if self.recognizer is not None:
                face_id, lbph_distance = self.recognizer.predict(gray[y:y + h, x:x + w])
                if lbph_distance < LBPH_MATCH_MAX:
                    name = self.names.get(str(face_id), f'ID {face_id}')
                    match = round(max(0.0, 1 - lbph_distance / 100), 2)
            x, y, w, h = int(x), int(y), int(w), int(h)
            dist = estimate_distance('face', w, self.focal_px)
            faces.append({'name': name, 'match': match, 'distance_m': dist, 'box': [int(x), int(y), int(x + w), int(y + h)]})
            self._draw(out, (x, y, x + w, y + h), f'{name} ~{dist:.1f} m' if dist else name, COLORS['face'])
        persons = sum(o['label'] == 'person' for o in objects)
        cv2.putText(out, f'persons {persons}  faces {len(faces)}', (8, out.shape[0] - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (236, 232, 225), 1, cv2.LINE_AA)
        return out, {'objects': objects, 'faces': faces, 'persons': persons, 'model': 'yolov8n + lbph',
                     'frame_w': int(out.shape[1]), 'frame_h': int(out.shape[0])}

    @staticmethod
    def _draw(img, box, text, color):
        x1, y1, x2, y2 = box
        cv2.rectangle(img, (x1, y1), (x2, y2), color, 2)
        (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
        y = max(y1, th + 6)
        cv2.rectangle(img, (x1, y - th - 6), (x1 + tw + 6, y), color, -1)
        cv2.putText(img, text, (x1 + 3, y - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (13, 14, 16), 1, cv2.LINE_AA)
