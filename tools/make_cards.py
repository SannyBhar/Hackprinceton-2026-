"""Generate printable ArUco corner markers, robot marker, and coding cards.

    pip install -r backend/requirements-vision.txt
    python tools/make_cards.py --out printables

Card layout (matches OpenCvCardRecognizer): marker square on the left (unit 1),
gap 0.25, handwriting box 1.5 wide on the right for FORWARD/BACKWARD.
"""
import argparse
from pathlib import Path

import cv2
import numpy as np

DICT = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_100)
CARDS = [("START", range(10, 14)), ("FORWARD", range(20, 32)), ("BACKWARD", range(40, 48)),
         ("LEFT", range(60, 66)), ("RIGHT", range(70, 76)), ("STOP", range(80, 84))]
ARROWS = {"FORWARD": "^", "BACKWARD": "v", "LEFT": "<-", "RIGHT": "->", "START": ">", "STOP": "[]"}


def marker(mid: int, px: int) -> np.ndarray:
    return cv2.aruco.generateImageMarker(DICT, mid, px)


def card(op: str, mid: int, unit: int = 300) -> np.ndarray:
    w, h = int(unit * 3.0), int(unit * 1.6)
    img = np.full((h, w), 255, np.uint8)
    m0 = int(unit * 0.15)
    img[m0:m0 + unit, m0:m0 + unit] = marker(mid, unit)
    if op in ("FORWARD", "BACKWARD"):
        x0 = m0 + int(unit * 1.25)
        cv2.rectangle(img, (x0, m0), (x0 + int(unit * 1.5), m0 + unit), 0, 6)
    cv2.putText(img, f"{op} {ARROWS[op]}", (m0, h - int(unit * 0.12)), cv2.FONT_HERSHEY_SIMPLEX, 1.6, 0, 4)
    cv2.rectangle(img, (0, 0), (w - 1, h - 1), 160, 2)
    return img


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="printables")
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(exist_ok=True)
    for mid, name in [(0, "TL"), (1, "TR"), (2, "BR"), (3, "BL"), (4, "ROBOT")]:
        img = cv2.copyMakeBorder(marker(mid, 600), 60, 60, 60, 60, cv2.BORDER_CONSTANT, value=255)
        cv2.imwrite(str(out / f"marker_{mid}_{name}.png"), img)
    for op, ids in CARDS:
        for mid in ids:
            cv2.imwrite(str(out / f"card_{op}_{mid}.png"), card(op, mid))
    print(f"wrote markers and cards to {out}/")


if __name__ == "__main__":
    main()
