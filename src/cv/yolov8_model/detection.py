import cv2
import numpy as np
import threading
import tempfile
import pygame
import os
from gtts import gTTS
from ultralytics import YOLO
import torch

# Initialize Pygame mixer
pygame.mixer.init()

# Check for GPU availability
device = "cuda" if torch.cuda.is_available() else "cpu"
print(f"Using device: {device}")

# Load YOLOv8 model
model = YOLO(os.path.join(os.path.dirname(os.path.abspath(__file__)), "yolov8n.pt")).to(device)

# Speech lock to prevent overlapping speech
speech_lock = threading.Lock()
last_spoken_objects = None  # Stores last detected objects as a tuple

def text_to_speech(text):
    """Converts text to speech and plays it, ensuring only one speech instance runs at a time."""
    global speech_lock

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
    """Performs real-time object detection using YOLOv8 and provides voice feedback."""
    global last_spoken_objects

    cap = cv2.VideoCapture(0)  # Open default webcam
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # Reduce buffer delay

    frame_count = 0  # Frame skipping counter

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            print("Failed to read from webcam. Exiting...")
            break

        frame_count += 1
        if frame_count % 3 != 0:  # Process every 3rd frame for efficiency
            continue

        resized_frame = cv2.resize(frame, (640, 480))

        results = model(resized_frame, stream=True)  # Run YOLO inference

        detected_objects = set()

        for r in results:
            for box in r.boxes:
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                conf = float(box.conf[0])
                cls = int(box.cls[0])
                label = model.names[cls]

                if conf > 0.5:
                    detected_objects.add(label)
                    cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                    cv2.putText(frame, f"{label} ({conf:.2f})", (x1, y1 - 10),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

        # Convert set to sorted tuple to prevent unnecessary speech
        detected_objects_tuple = tuple(sorted(detected_objects))

        if detected_objects_tuple and detected_objects_tuple != last_spoken_objects:
            last_spoken_objects = detected_objects_tuple  # Update spoken objects
            speech_message = ", ".join([f"A {obj} is detected" for obj in detected_objects_tuple])
            speech_thread = threading.Thread(target=text_to_speech, args=(speech_message,))
            speech_thread.start()

        cv2.imshow("YOLOv8 Object Detection", frame)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    object_detection()
