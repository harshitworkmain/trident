# Computer Vision Subsystem — Setup & Run Reference

> Quick reference for all runnable CV scripts (YOLOv8 object detection, Haar Cascade face detection, and LBPH face recognition), mapped to their model/functionality.

---

## Prerequisites

### 1. Install Python Dependencies

Run the following command from the root of the `trident` repository:

```bash
# Install GPU or CPU PyTorch (included in trident dependencies)
# Install remaining CV-specific packages:
pip install opencv-contrib-python ultralytics pygame gTTS numpy pillow pyyaml
```

> **Note:** Make sure you install `opencv-contrib-python` rather than standard `opencv-python`, as the face recognition module (`cv2.face`) is only present in the contrib package.

---

## Scripts Overview

All scripts are located under `src/cv/`:

| Script | Location | Model | Functionality | Exit Key |
|--------|----------|-------|---------------|----------|
| `detection.py` | `yolov8_model/` | YOLOv8n | Obstacle/Object Detection + TTS | `q` |
| `main.py` | `yolov8_model/` | YOLOv8n + LBPH | Object Detection + Face Recognition + TTS + Distance Estimation | `q` |
| `face_taker.py` | `face_recognition/` | Haar Cascade | Capture face training images | `ESC` |
| `face_trainer.py` | `face_recognition/` | LBPH | Train face recognition model | Auto-exits |
| `face_recognizer.py` | `face_recognition/` | LBPH + Haar Cascade | Standalone face recognition | `ESC` |

---

## 1. YOLO Obstacle Detection (with Voice Feedback)

**Model:** YOLOv8 Nano (`yolov8n.pt`)  
**Functionality:** Real-time object detection via webcam with text-to-speech announcements for detected objects.

```bash
cd src/cv/yolov8_model
python3 detection.py
```

- Detects 80 COCO object classes (person, chair, bottle, car, etc.)
- Announces detected objects via Google TTS
- Processes every 3rd frame for efficiency
- Press **`q`** to quit

---

## 2. YOLO + Face Recognition (Combined — Main Script)

**Model:** YOLOv8 Nano + LBPH Face Recognizer  
**Functionality:** Real-time object detection AND face recognition with distance estimation and voice feedback.

```bash
cd src/cv/yolov8_model
python3 main.py
```

- Detects objects via YOLOv8 with distance estimation
- Recognizes known faces using the trained LBPH model
- Announces identified people by name and distance
- Announces unknown persons and detected objects
- Speech throttled to every 10 seconds to avoid repetition
- Press **`q`** to quit

> **Note:** If `trainer.yml` is not found in `src/cv/face_recognition/`, this script will automatically trigger `face_taker.py` and `face_trainer.py` to create the model.

---

## 3. Face Data Capture

**Model:** Haar Cascade (frontal face detector)  
**Functionality:** Captures 120 face images from the webcam for training the recognition model.

```bash
cd src/cv/face_recognition
python3 src/face_taker.py
```

- Prompts for user name
- Captures 120 images of the user's face
- Saves images to `images/` folder as `Users-{id}-{n}.jpg`
- Updates `names.json` with the name-ID mapping
- Press **`ESC`** to exit early

---

## 4. Face Model Training

**Model:** LBPH (Local Binary Patterns Histograms)  
**Functionality:** Trains the face recognition model from captured images.

```bash
cd src/cv/face_recognition
python3 src/face_trainer.py
```

- Processes all images in the `images/` directory
- Generates `trainer.yml` (the trained model file)
- Auto-exits when training is complete

---

## 5. Standalone Face Recognition

**Model:** LBPH Face Recognizer + Haar Cascade  
**Functionality:** Real-time face recognition only (no object detection).

```bash
cd src/cv/face_recognition
python3 src/face_recognizer.py
```

- Opens webcam and recognizes trained faces
- Displays name and confidence level on screen
- Press **`ESC`** to exit

---

## Full Pipeline (New User Registration → Recognition)

To register a new face and start full detection:

```bash
# Step 1: Capture face data
cd src/cv/face_recognition
python3 src/face_taker.py

# Step 2: Train the model
python3 src/face_trainer.py

# Step 3: Run combined detection + recognition
cd ../yolov8_model
python3 main.py
```

---

## Project Structure

```
src/cv/
├── yolov8_model/
│   ├── main.py              # Combined YOLO + Face Recognition
│   ├── detection.py          # YOLO Object Detection only
│   ├── yolov8n.pt            # YOLOv8 Nano weights
│   ├── deploy.prototxt       # SSD deploy config (unused)
│   └── requirements.txt      # Python dependencies
│
└── face_recognition/
    ├── src/
    │   ├── face_taker.py     # Capture face images
    │   ├── face_trainer.py   # Train LBPH model
    │   ├── face_recognizer.py # Standalone face recognition
    │   └── settings/
    │       └── settings.py   # Configuration (camera, detection params)
    ├── images/               # Captured face training images
    ├── names.json            # Name-ID mappings
    ├── trainer.yml           # Trained LBPH model (~46MB)
    ├── haarcascade_frontalface_default.xml  # Haar cascade XML
    └── requirements.txt      # Python dependencies
```

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| `ModuleNotFoundError: No module named 'ultralytics'` | Run `pip install ultralytics` |
| `ModuleNotFoundError: No module named 'cv2'` | Run `pip install opencv-contrib-python` |
| `ModuleNotFoundError: No module named 'pygame'` | Run `pip install pygame` |
| `ModuleNotFoundError: No module named 'gtts'` | Run `pip install gtts` |
| `Trainer file not found` | Run `face_taker.py` then `face_trainer.py` first |
| Webcam not opening | Check camera index in `settings.py` (default: `0`) |
