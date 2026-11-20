"""Put each official photo next to the matching render: shots/compare_<suffix>.png.

  python compare_sheet.py <suffix>      (reads shots/ref_*<suffix>.png)
"""
import os
import sys

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
SHOTS = os.path.join(HERE, "..", "shots")
REF = os.path.join(HERE, "..", "..", "..", "pic", "ref")
PAIRS = (("mosaico-isometric.png", "ref_iso"), ("mosaico-front-labelled.png", "ref_front"),
         ("mosaico-back-labelled.png", "ref_back"))


def fit(im, size):
    im = im.convert("RGB")
    im.thumbnail((size, size))
    canvas = Image.new("RGB", (size, size), (0, 0, 0))
    canvas.paste(im, ((size - im.width) // 2, (size - im.height) // 2))
    return canvas


def main(suffix, size=520):
    sheet = Image.new("RGB", (size * 3, size * 2), (0, 0, 0))
    for i, (photo, shot) in enumerate(PAIRS):
        ref = Image.open(os.path.join(REF, photo))
        if ref.mode == "RGBA":                       # official PNGs are transparent: put them on white
            bg = Image.new("RGB", ref.size, (255, 255, 255))
            bg.paste(ref, mask=ref.split()[3])
            ref = bg
        ren = Image.open(os.path.join(SHOTS, shot + suffix + ".png"))
        s = min(ren.size)
        ren = ren.crop(((ren.width - s) // 2, (ren.height - s) // 2, (ren.width + s) // 2, (ren.height + s) // 2))
        ren = ren.crop((int(s * 0.14), int(s * 0.14), int(s * 0.86), int(s * 0.86)))
        sheet.paste(fit(ref, size), (i * size, 0))
        sheet.paste(fit(ren, size), (i * size, size))
    out = os.path.join(SHOTS, "compare" + suffix + ".png")
    sheet.save(out)
    print(out)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "")
