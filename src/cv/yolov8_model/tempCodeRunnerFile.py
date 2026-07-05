import cv2
import numpy as np
import threading
import tempfile
import pygame
import os
import json
import time
from gtts import gTTS
from ultralytics import YOLO
import torch

# Initialize Pygame mixer
pygame.mixer.init()
names_file_path = r"D:/Empower/real-time-face-recognition/names.json"
# Check for GPU availability
device = "cuda" if torch.cuda.is_available() else "cpu"
print(f"Using device: {device}")

# Load YOLOv8 model
model = YOLO(r"d:\Downloads\yolov8 model\yolov8n.pt").to(device)

# Load face recognition model
face_recognizer = cv2.face.LBPHFaceRecognizer_create()
face_model_path = r"D:/Empower/real-time-face-recognition/trainer.yml"  # Absolute path


if os.path.exists(face_model_path):
    face_recognizer.read(face_model_path)
    print("Face recognition model loaded.")
else:
    print("Face recognition model not found. Training the model...")
    os.system(r'python "D:/Empower/real-time-face-recognition/src/face_taker.py"')
    os.system(r'python "D:/Empower/real-time-face-recognition\src/face_trainer.py"')
    face_recognizer.read(face_model_path)

# Load known names
if os.path.exists(names_file_path):
    with open(names_file_path, "r") as f:
        names = json.load(f)
else:
    names = {}

# Prevent repetitive speech
speech_lock = threading.Lock()
last_speech_time = 0  # Last time speech was triggered
speech_interval = 10 # Minimum time between speeches (in seconds)

# Known Object Sizes (in cm) for Distance Estimation
KNOWN_WIDTHS = {
    "bottle": 7,
    "chair": 50,
}

FOCAL_LENGTH = 700  # Pre-calculated focal length (calibrate as needed)

def estimate_distance(known_width, pixel_width):
    """Estimates the distance based on the object's width in pixels."""
    if pixel_width > 0:
        return ((KNOWN_WIDTHS.get(known_width, 20) * FOCAL_LENGTH) / pixel_width)/100
    return None

def text_to_speech(text):
    """Speaks only once every 5 seconds."""
    global last_speech_time

    current_time = time.time()
    if current_time - last_speech_time < speech_interval:
        return  # Block speech if it's been less than 5 seconds

    last_speech_time = current_time  # Update last speech time

    with speech_lock:
        tts = gTTS(text=text, lang='en')
        file_path = tempfile.NamedTemporaryFile(suffix='.mp3', delete=False).name
        tts.save(file_path)

        pygame.mixer.music.load(file_path)
        pygame.mixer.music.play()

        while pygame.mixer.music.get_busy():
            pygame.time.Clock().tick(10)

        pygame.mixer.music.stop()
        pygame.mixer.music.unload()
        os.remove(file_path)

def object_detection():
    """Performs real-time object detection and face recognition using YOLOv8."""
    global last_speech_time

    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            print("Failed to read from webcam. Exiting...")
            break

        resized_frame = cv2.resize(frame, (640, 480))

        # YOLO Object Detection
        results = model(resized_frame, stream=True)  

        detected_objects = {}
        
        for r in results:
            for box in r.boxes:
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                conf = float(box.conf[0])
                cls = int(box.cls[0])
                label = model.names[cls]

                if label == "person":
                    continue  # Ignore YOLO's "person" detection

                if conf > 0.5:
                    object_width = x2 - x1  # Width in pixels
                    distance = estimate_distance(label, object_width)

                    detected_objects[label] = distance  # Store object & distance

                    cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                    cv2.putText(frame, f"{label} ({distance:.2f}m)", (x1, y1 - 10),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

        # Face Detection
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
        faces = face_cascade.detectMultiScale(gray, 1.3, 5)

        identified_name = None
        person_distance = None

        for (x, y, w, h) in faces:
            roi_gray = gray[y:y+h, x:x+w]
            face_id, confidence = face_recognizer.predict(roi_gray)

            if confidence < 50:
                identified_name = names.get(str(face_id), "Unknown")
            else:
                identified_name = "Unknown"

            person_distance = estimate_distance("person", w)

            display_text = f"{identified_name} ({person_distance:.2f}m)" if identified_name else "Unknown"
            cv2.rectangle(frame, (x, y), (x + w, y + h), (255, 0, 0), 2)
            cv2.putText(frame, display_text, (x, y - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 0, 0), 2)

            # Replace YOLO's "person" with the recognized person's name
            detected_objects[identified_name] = person_distance

        # Determine speech output (only once every 5 seconds)
        current_time = time.time()
        speech_message = None

        if current_time - last_speech_time >= speech_interval:  
            if identified_name and identified_name != "Unknown":
                speech_message = f"{identified_name} is here at {person_distance:.2f} meters"
            elif len(faces) > 0:

                speech_message = f"Unknown person detected at {person_distance:.2f} meters"
            elif detected_objects:
                object_messages = [f"A {obj} is detected at {dist:.2f} meters" for obj, dist in detected_objects.items()]
                speech_message = ", ".join(object_messages)

        if speech_message:
            threading.Thread(target=text_to_speech, args=(speech_message,)).start()

        cv2.imshow("YOLOv8 Object Detection & Face Recognition", frame)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    object_detection()
