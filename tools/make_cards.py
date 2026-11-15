"""Generate 2-inch unit-block SVGs and a print-at-actual-size HTML sheet.

    backend/.venv/bin/python tools/make_cards.py --out printables

No handwritten-distance boxes or arena markers are generated. Keep white gaps between blocks.
"""
import argparse
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
from app.vision.markers import BLOCK_INCHES, CARD_OPS, DICTIONARY_NAME


def svg_marker(mid):
    import cv2
    pixels=cv2.aruco.generateImageMarker(cv2.aruco.getPredefinedDictionary(getattr(cv2.aruco,DICTIONARY_NAME)),mid,6)
    cells=''.join(f'<rect x="{x}" y="{y}" width="1" height="1" fill="white"/>'
                  for y in range(6) for x in range(6) if pixels[y,x])
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 6 6" width="{BLOCK_INCHES}in" '
            f'height="{BLOCK_INCHES}in" shape-rendering="crispEdges">'
            '<rect width="6" height="6" fill="black"/>'+cells+'</svg>\n')


def generate(out):
    out.mkdir(parents=True,exist_ok=True)
    figures=[]
    for mid,op in CARD_OPS.items():
        name=f'card_{op}_{mid}.svg'
        supplied=ROOT/'assets'/'markers'/f'4x4_1000-{mid}.svg'
        if supplied.is_file():shutil.copyfile(supplied,out/name)
        else:(out/name).write_text(svg_marker(mid))
        figures.append(f'<figure><img src="{name}" alt="{op} marker {mid}"><figcaption>{op} · ID {mid}</figcaption></figure>')
    html='''<!doctype html><html><head><meta charset="utf-8"><title>Grassroot unit blocks</title>
<style>@page{size:letter;margin:.5in}body{font:12px sans-serif}main{display:grid;grid-template-columns:2in 2in;gap:.25in .5in}figure{margin:0;width:2in}img{display:block;width:2in;height:2in}figcaption{padding-top:.08in}header{margin-bottom:.25in}</style>
</head><body><header>Print at 100% / actual size, without fit-to-page. Each marker square is 2 × 2 inches.
Labels are outside the block. Leave white space around each block when scanning. START/STOP are optional.</header><main>'''+''.join(figures)+'</main></body></html>\n'
    (out/'unit-blocks.html').write_text(html)
    return out/'unit-blocks.html'


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,default=Path('printables'))
    args=parser.parse_args()
    print(f'Wrote 2-inch SVGs and print sheet: {generate(args.out)}')


if __name__=='__main__':main()
