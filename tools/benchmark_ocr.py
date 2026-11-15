"""Benchmark user-supplied labeled real card crops; no fabricated accuracy claims.

Input JSON: [{"path":"crop.png","expected":2}, ...]. Paths relative to manifest.
"""
import argparse,json,time
from pathlib import Path
from app.vision.ocr import LocalHandwritingOcr


def main():
    import cv2
    p=argparse.ArgumentParser();p.add_argument('manifest');a=p.parse_args()
    manifest=Path(a.manifest);ocr=LocalHandwritingOcr();results=[]
    for case in json.loads(manifest.read_text()):
        crop=cv2.imread(str(manifest.parent/case['path']),cv2.IMREAD_GRAYSCALE)
        start=time.monotonic();value,confidence=ocr(crop)
        results.append({**case,'candidate':value,'correct':value==case['expected'],
                        'seconds':time.monotonic()-start,'rawText':ocr.last_text,'error':ocr.error})
    print(json.dumps({'samples':len(results),'correct':sum(r['correct'] for r in results),'results':results},indent=2))


if __name__=='__main__':main()
