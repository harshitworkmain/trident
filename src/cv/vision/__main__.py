"""Run the ROV vision worker: camera -> YOLOv8n + LBPH + distance -> TRIDENT mission dashboard.

    python -m src.cv.vision --key tdk_...                        # laptop webcam (index 0)
    python -m src.cv.vision --key tdk_... --source http://192.168.4.1:81/stream   # ROV camera (MJPEG/RTSP)
    python -m src.cv.vision --key tdk_... --source demo          # demo scene (no camera attached)

Get the key as an admin: POST /api/v1/rov/{id}/vision-key (Admin page, ROV units).
"""

from __future__ import annotations

import argparse
import base64
import time
from pathlib import Path
from typing import Iterator

import cv2
import httpx
import numpy as np

from .pipeline import CV_DIR, VisionPipeline


def demo_frames() -> Iterator[np.ndarray]:
    """A slow pan across real photos (ultralytics sample scenes + an enrolled face), for demos
    and tests without a camera. The dashboard labels the feed with its source."""
    import ultralytics
    assets = Path(ultralytics.__file__).parent / 'assets'
    scenes = [cv2.imread(str(p)) for p in sorted(assets.glob('*.jpg'))]
    # two enrolled people side by side; their photos are tight face crops, so pad them at native size
    # (the Haar detector needs context around a face; resizing would also move LBPH off its training scale)
    picks = [sorted((CV_DIR / 'face_recognition' / 'images').glob(f'Users-{u}-*.jpg'))[:1] for u in (1, 3)]
    tiles = [cv2.copyMakeBorder(cv2.imread(str(p[0]), cv2.IMREAD_GRAYSCALE), 50, 50, 50, 50, cv2.BORDER_REPLICATE)
             for p in picks if p]
    if tiles:
        canvas = np.full((480, 640, 3), 40, np.uint8)
        x = 16
        for t in tiles:
            h, w = t.shape
            canvas[(480 - h) // 2:(480 - h) // 2 + h, x:x + w] = cv2.cvtColor(t, cv2.COLOR_GRAY2BGR)
            x += w + 16
        scenes.append(canvas)
    n_photos = len(scenes) - (1 if tiles else 0)
    i = 0
    while True:
        k = (i // 40) % len(scenes)
        img = scenes[k]
        if k < n_photos:                     # pan across the photos like a moving camera
            h, w = img.shape[:2]
            crop_w = int(w * 0.85)
            x = int((w - crop_w) * (0.5 + 0.5 * np.sin(i / 12)))
            img = img[:, x:x + crop_w]
        yield img
        i += 1


def frames(source: str) -> Iterator[np.ndarray]:
    if source == 'demo':
        yield from demo_frames()
        return
    cap = cv2.VideoCapture(int(source), cv2.CAP_DSHOW) if source.isdigit() else cv2.VideoCapture(source)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    while True:
        ok, frame = cap.read()
        if not ok:
            cap.release()
            time.sleep(2)                                   # camera dropped: reopen
            cap = cv2.VideoCapture(int(source), cv2.CAP_DSHOW) if source.isdigit() else cv2.VideoCapture(source)
            continue
        yield frame


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--api', default='http://localhost:8000')
    ap.add_argument('--key', required=True, help='ROV vision key (POST /api/v1/rov/{id}/vision-key)')
    ap.add_argument('--source', default='0', help="webcam index, camera URL, video file, or 'demo'")
    ap.add_argument('--fps', type=float, default=4.0, help='frames processed per second (CPU budget)')
    ap.add_argument('--focal-px', type=float, default=700.0, help='camera focal length in pixels at 640 px width')
    ap.add_argument('--quality', type=int, default=70)
    a = ap.parse_args()
    pipe = VisionPipeline.load(a.focal_px)
    print('vision models loaded; streaming', a.source, 'to', a.api)
    period, last_log, sent = 1.0 / a.fps, time.monotonic(), 0
    with httpx.Client(base_url=a.api, headers={'X-ROV-Vision-Key': a.key}, timeout=5) as c:
        for frame in frames(a.source):
            t0 = time.monotonic()
            annotated, det = pipe.process(frame)
            ok, jpg = cv2.imencode('.jpg', annotated, [cv2.IMWRITE_JPEG_QUALITY, a.quality])
            try:
                r = c.post('/api/v1/rov/vision/frame', json={'jpeg_b64': base64.b64encode(jpg.tobytes()).decode(),
                                                             'detections': det})
                if r.status_code == 401:
                    print('vision key rejected; check --key'); time.sleep(10)
                sent += r.status_code == 200
            except httpx.HTTPError as e:
                print(f'vision: {type(e).__name__}; retrying'); time.sleep(2)
            if time.monotonic() - last_log > 10:
                print(f'vision: {sent} frames sent, persons {det["persons"]}, faces {len(det["faces"])}')
                last_log = time.monotonic()
            time.sleep(max(0.0, period - (time.monotonic() - t0)))


if __name__ == '__main__':
    main()
