"""Save one frame from each connected camera so we can see what the overhead camera sees.

Run from macOS Terminal.app (it will ask for camera permission the first time):
    backend/.venv/bin/python tools/camera_check.py
Frames are written to data/camera_check/cam<index>.jpg (data/ is gitignored).
"""
import time
from pathlib import Path

import cv2

OUT = Path(__file__).resolve().parents[1] / "data" / "camera_check"
OUT.mkdir(parents=True, exist_ok=True)

found = 0
for index in range(4):
    cap = cv2.VideoCapture(index, cv2.CAP_AVFOUNDATION)
    if not cap.isOpened():
        cap.release()
        continue
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
    ok, frame = False, None
    for _ in range(40):  # let auto-exposure settle
        ok, frame = cap.read()
        time.sleep(0.03)
    cap.release()
    if ok:
        path = OUT / f"cam{index}.jpg"
        cv2.imwrite(str(path), frame)
        h, w = frame.shape[:2]
        print(f"camera {index}: {w}x{h}, brightness {frame.mean():.0f} -> {path}")
        found += 1

if not found:
    print("No camera frames. If macOS asked for camera access, click Allow and run this again;\n"
          "otherwise enable Terminal in System Settings → Privacy & Security → Camera.")
