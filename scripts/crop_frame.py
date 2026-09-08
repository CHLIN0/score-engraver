"""Zoom into a region of a reference image (dossier frame, contact sheet, PDF page render) so the
engraver can READ notes, accidentals, rhythms and lyrics instead of guessing from a full-frame view.

    python crop_frame.py image.jpg --out crop.png [--box x0 y0 x1 y1] [--band top bottom] [--scale 2.5]
    python crop_frame.py image.jpg --out crops/ --grid 3          # cut the width into 3 overlapping tiles

--box crops a rectangle in source pixels; --band keeps full width between two rows; --grid N cuts the
staff band into N tiles with 10 % overlap (bars are easier to read one system-third at a time).
Upscaling (default 2.5×, Lanczos) makes small noteheads legible to a vision model.
"""

import argparse, pathlib
from PIL import Image


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("image")
    ap.add_argument("--out", required=True)
    ap.add_argument("--box", type=int, nargs=4)
    ap.add_argument("--band", type=int, nargs=2)
    ap.add_argument("--grid", type=int)
    ap.add_argument("--scale", type=float, default=2.5)
    a = ap.parse_args()
    im = Image.open(a.image).convert("RGB")
    W, H = im.size
    if a.box:
        x0, y0, x1, y1 = a.box
        im = im.crop((max(0, x0), max(0, y0), min(W, x1), min(H, y1)))
    elif a.band:
        im = im.crop((0, max(0, a.band[0]), W, min(H, a.band[1])))
    outs = []
    if a.grid and a.grid > 1:
        d = pathlib.Path(a.out)
        d.mkdir(parents=True, exist_ok=True)
        w = im.width
        step = w / a.grid
        for i in range(a.grid):
            x0 = int(max(0, i * step - 0.1 * step))
            x1 = int(min(w, (i + 1) * step + 0.1 * step))
            tile = im.crop((x0, 0, x1, im.height))
            tile = tile.resize(
                (int(tile.width * a.scale), int(tile.height * a.scale)), Image.LANCZOS
            )
            f = d / f"tile-{i + 1}.png"
            tile.save(f)
            outs.append(str(f))
    else:
        im = im.resize(
            (int(im.width * a.scale), int(im.height * a.scale)), Image.LANCZOS
        )
        pathlib.Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        im.save(a.out)
        outs.append(a.out)
    print("\n".join(outs))


if __name__ == "__main__":
    main()
