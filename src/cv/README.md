# Computer Vision (ROV camera)

TRIDENT's computer-vision subsystem watches the ROV camera feed during a rescue mission. For every
processed frame it:

- detects objects with **YOLOv8n** (people are kept: in a rescue they are what we are looking for),
- finds faces with a **Haar cascade** and matches them against enrolled responders with **LBPH**,
- estimates distance to each detection with a **pinhole camera model**,
- draws the boxes and labels onto the frame and sends the annotated JPEG plus the detections to the
  TRIDENT API, where the mission dashboard shows a live stream, a persons badge and a detection list.

## Place in the architecture

```
ROV camera (MJPEG/RTSP) or webcam/file
        |
        v
vision worker  (src/cv/vision, runs on the station laptop or next to the ROV)
        |  POST /api/v1/rov/vision/frame   header X-ROV-Vision-Key, body {jpeg_b64, detections}
        v
API relay      (src/backend/app/services/vision.py)
        |  keeps only the latest frame per ROV unit in memory
        |  GET /api/v1/rov/{id}/vision/stream?ticket=...   MJPEG to the browser
        |  `rov` WebSocket topic, event: vision            detections
        v
Mission dashboard (live annotated stream + detections)
```

The heavy dependencies (torch, ultralytics, opencv-contrib) live only in the worker; the API process
never imports them. Browsers open the stream with a single-use ticket (`POST /rov/{id}/vision/ticket`,
valid 60 s) so access tokens never appear in URLs. The full endpoint contract is in
`docs/PLATFORM_DESIGN.md`, section "ROV camera / computer vision".

## Layout

```
src/cv/
  vision/                    integrated ROV vision worker (this is what TRIDENT runs)
    pipeline.py              YOLOv8n + Haar/LBPH + distance, one frame at a time
    __main__.py              camera loop, rate limiting, upload to the API
  yolov8_model/
    yolov8n.pt               YOLOv8 nano weights (used by the worker)
    main.py, detection.py    legacy desktop demos (see the last section)
  face_recognition/
    src/face_taker.py        capture enrolment images from a webcam
    src/face_trainer.py      train the LBPH model
    src/face_recognizer.py   legacy standalone recognition demo
    src/settings/settings.py camera index, Haar parameters, sample count, file names
    images/                  enrolment images, Users-{id}-{n}.jpg
    names.json               {"id": "name"} map (used by the worker)
    trainer.yml              trained LBPH model (used by the worker)
```

## Requirements

Install from the repository root:

```bash
pip install -r requirements.txt
```

The root `requirements.txt` already contains what the worker needs (`ultralytics`,
`opencv-contrib-python`, `httpx` via the API requirements). The `requirements.txt` files inside
`yolov8_model/` and `face_recognition/` are leftovers from the standalone scripts and only duplicate
part of this; use the root file.

You need `opencv-contrib-python`, not plain `opencv-python`: the face recognizer (`cv2.face`) exists
only in the contrib build. Do not install both packages in one environment; they overwrite each
other's `cv2` module. If `cv2.face` is missing, the worker still runs but every face is labelled
"Unknown".

## Running the vision worker

1. Get a vision key for the ROV unit, as an admin: `POST /api/v1/rov/{id}/vision-key` (or the Admin
   page, ROV units). The key is shown once; keep it.
2. Start the API, then from the repository root:

```bash
# laptop webcam (index 0)
python -m src.cv.vision --key tdk_...

# ROV camera stream (MJPEG or RTSP URL)
python -m src.cv.vision --key tdk_... --source http://192.168.4.1:81/stream

# recorded video file
python -m src.cv.vision --key tdk_... --source dive.mp4

# demo scene without a camera (ultralytics sample photos plus enrolled faces)
python -m src.cv.vision --key tdk_... --source demo
```

| Option | Default | Meaning |
|---|---|---|
| `--api` | `http://localhost:8000` | TRIDENT API base URL |
| `--key` | required | ROV vision key |
| `--source` | `0` | webcam index, camera URL (MJPEG/RTSP), video file, or `demo` |
| `--fps` | `4` | frames processed per second (CPU budget) |
| `--focal-px` | `700` | camera focal length in pixels at 640 px frame width (see calibration) |
| `--quality` | `70` | JPEG quality of the uploaded frames |

Frames are resized to 640 px width before processing. If the camera drops, the worker reopens it
every 2 s; if the key is rejected it logs "vision key rejected" and backs off. Every 10 s it prints
how many frames were sent and the current person and face counts. The dashboard marks the feed
offline when no frame has arrived for 5 s.

## Detections

YOLOv8n reports all 80 COCO classes with confidence >= 0.4; nothing is filtered out. Faces are
reported separately with the enrolled name (or "Unknown") and a match score. Distance is only
computed for classes with a known typical real width:

| Class | Real width (m) | Class | Real width (m) |
|---|---|---|---|
| person (shoulders) | 0.45 | dog | 0.30 |
| face | 0.16 | cat | 0.20 |
| boat | 2.5 | cow | 0.70 |
| car | 1.8 | horse | 0.60 |
| truck | 2.5 | bottle | 0.07 |
| bus | 2.55 | chair | 0.50 |
| motorcycle | 0.8 | backpack | 0.30 |
| bicycle | 0.6 | handbag | 0.30 |
| umbrella | 0.9 | suitcase | 0.45 |
| bench | 1.4 | surfboard | 0.50 |

Other classes are drawn and reported with `distance_m: null`. To add a class, extend `REAL_WIDTH_M`
in `vision/pipeline.py`.

Each frame's `detections` payload has `objects` (label, confidence, distance_m, box), `faces` (name,
match, distance_m, box), `persons` (count of YOLO person boxes), `model`, `frame_w` and `frame_h`.

## Camera calibration for distance

Distance uses the pinhole model `D = W_real * f / w_pixels`, where `f` is the focal length in pixels
at 640 px frame width. The default `f = 700` comes from the original desktop calibration of a laptop
webcam; on any other camera the numbers can be far off. Even with a calibrated camera, expect about
+-30 % because real object widths vary and boxes are not tight. The dashboard labels distances as
approximate.

Quick calibration with an object of known width:

1. Place an object of known width `W` (for example an A4 sheet, 0.21 m wide) facing the camera at a
   measured distance `D` (for example 1.5 m).
2. Measure its width in pixels `w` in a 640 px wide frame (take a screenshot of the stream, or read
   the box width from a YOLO detection of a known object).
3. Compute `f = w * D / W` and pass it with `--focal-px`.

Repeat at two or three distances and average. Underwater the effective focal length is longer than
in air (about 1.33x behind a flat port), so calibrate in the water where the ROV operates. Full
checkerboard calibration (`cv2.calibrateCamera`, which also corrects lens distortion) is future work.

## Enrolling faces

The worker matches faces against `face_recognition/trainer.yml` and `face_recognition/names.json`.
Both are produced by the enrolment scripts:

```bash
cd src/cv/face_recognition
python src/face_taker.py      # enter a name; captures 120 face images to images/Users-{id}-{n}.jpg
python src/face_trainer.py    # trains on everything in images/, writes trainer.yml
```

Run them from `src/cv/face_recognition`: their file paths (images/, names.json, trainer.yml and the
Haar cascade) are relative to that folder. `face_taker.py` assigns the next free numeric id and adds
it to `names.json`; press ESC to stop early. Use good lighting and turn the head slowly so the images
cover several angles. Restart the worker after retraining so it loads the new model.

Privacy: enrol only rescue team members and other responders, and only with their consent. Do not
enrol victims or bystanders. Enrolment images are personal data; remove a person's
`Users-{id}-*.jpg` images and their `names.json` entry, then retrain, when they leave the team or
withdraw consent.

## Performance

On a laptop CPU, YOLOv8n plus face detection and recognition take about 0.3 to 0.5 s per frame, so the
worker targets 4 frames per second by default and sleeps when it is ahead. Lower `--fps` on slower
machines. The worker loads YOLO on the CPU; the API relays the stream to dashboards at up to 8 fps.

## Limitations

- LBPH is a classical recognizer: it is sensitive to lighting, pose and image scale and has a high
  false-match rate compared with modern face embeddings. A match is accepted when the LBPH distance
  is below 50; treat names as hints, not identification.
- The Haar cascade only finds roughly frontal faces and needs some context around the face; tight
  face crops and small or turned faces are missed.
- Pinhole distances are approximate (see calibration) and assume the object is seen square-on.
- YOLOv8n is the smallest YOLO model, trained on COCO in air; recall drops in murky water, at night
  and for partially submerged people.

## Legacy desktop demos

The original standalone scripts still run on a desktop with a webcam, outside TRIDENT. They need
extra packages that are not in the root requirements: `pip install pygame gTTS` (gTTS also needs
internet access for speech).

- `yolov8_model/detection.py`: YOLOv8n object detection on the webcam, every 3rd frame, announcing
  detected objects by voice. Press `q` to quit.
- `yolov8_model/main.py`: YOLOv8n plus LBPH face recognition with spoken names and rough distances
  (at most one announcement every 10 s). It ignores YOLO person boxes and, if `trainer.yml` is
  missing, runs `face_taker.py` and `face_trainer.py` first. Press `q` to quit.
- `face_recognition/src/face_recognizer.py`: face recognition only, showing name and confidence.
  Run it from `src/cv/face_recognition`; press ESC to quit.

The vision worker replaces these for TRIDENT; keep them for quick local checks and demonstrations.
