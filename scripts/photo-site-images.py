#!/usr/bin/env python3
"""Build the watermarked slideshow images for purplelink.llc/photography.

Reads the ten originals from the Nikon library and writes, per photograph, a
2200px hero WebP and a 360px thumbnail WebP into site/assets/photography/.
The watermark is burned into the pixels (a diagonal tile of the name and site
plus a corner mark), so saving the file does not remove it. The originals are
never modified.

  python3 scripts/photo-site-images.py [--out DIR]
"""
import argparse, json
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter

Image.MAX_IMAGE_PIXELS = None
SRC = Path("/Volumes/Extreme SSD/Nikon Photos")
FONT = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
TILE_TEXT = "BENJAMIN AMPEL  ·  PURPLELINK.LLC"

# slug, source stem, caption, alt, focal point (x%, y%) for object-position
PHOTOS = [
    ("skogafoss", "DSC_1326", "Skógafoss, Iceland",
     "Skógafoss waterfall falling from a green cliff, with a rainbow in the spray at its base", (62, 40)),
    ("itsukushima", "DSC_4368", "Itsukushima Shrine, Miyajima, Japan",
     "The red torii gate of Itsukushima Shrine standing in the sea at dusk beneath heavy clouds", (55, 55)),
    ("matterhorn", "DSC_8669", "Matterhorn from Riffelsee, Switzerland",
     "The Matterhorn reflected in the still water of Riffelsee under a deep blue sky", (60, 40)),
    ("big-ben", "DSC_6629-Edit", "Big Ben at sunset, London",
     "Big Ben and the Houses of Parliament under an orange and violet sunset sky", (72, 45)),
    ("jokulsarlon", "DSC_1601", "Jökulsárlón glacier lagoon, Iceland",
     "Blue and white icebergs floating on Jökulsárlón lagoon with a glacier beyond", (50, 55)),
    ("saguaro-sunset", "DSC_7583", "Sonoran Desert at sunset, Arizona",
     "A dark desert mountain silhouetted against an orange and gold sunset above saguaro cactus", (50, 50)),
    ("gorner", "DSC_8714", "Gorner Glacier, Zermatt, Switzerland",
     "The Gorner Glacier winding between snow-covered peaks above Zermatt", (55, 50)),
    ("waipio", "DSC_4380", "Waipio Valley, Hawaii",
     "Green cliffs of Waipio Valley dropping to a black sand beach and surf", (50, 50)),
    ("hozu-gorge", "DSC_3638", "Hozu Gorge in mist, Arashiyama, Japan",
     "Mist rising from forested slopes above the Hozu River near Arashiyama", (50, 55)),
    ("copenhagen", "DSC_7559-Pano-Edit", "Copenhagen rooftops, Denmark",
     "Copenhagen's red rooftops and a green copper spire under a broken, cloudy sky", (75, 50)),
]


def tile_layer(size, font_px, rot=-24):
    """A transparent layer with the watermark text repeated on a diagonal grid."""
    w, h = size
    diag = int((w * w + h * h) ** 0.5) + 200
    font = ImageFont.truetype(FONT, font_px)
    txt = Image.new("RGBA", (diag, diag), (0, 0, 0, 0))
    d = ImageDraw.Draw(txt)
    tw = d.textlength(TILE_TEXT, font=font)
    stepx, stepy = int(tw + font_px * 3.2), int(font_px * 8.8)
    row = 0
    for y in range(-stepy, diag + stepy, stepy):
        off = (stepx // 2) if row % 2 else 0
        for x in range(-stepx + off, diag + stepx, stepx):
            d.text((x + 2, y + 2), TILE_TEXT, font=font, fill=(0, 0, 0, 120))   # shadow keeps it legible on snow and sky
            d.text((x, y), TILE_TEXT, font=font, fill=(255, 255, 255, 140))
        row += 1
    txt = txt.rotate(rot, resample=Image.BICUBIC, expand=False)
    l, t = (diag - w) // 2, (diag - h) // 2
    return txt.crop((l, t, l + w, t + h))


def corner_mark(img, font_px):
    w, h = img.size
    font = ImageFont.truetype(FONT, font_px)
    small = ImageFont.truetype(FONT, int(font_px * 0.62))
    l1, l2 = "© Benjamin Ampel", "purplelink.llc/photography"
    d = ImageDraw.Draw(img)
    w1, w2 = d.textlength(l1, font=font), d.textlength(l2, font=small)
    pad = int(font_px * 0.7)
    bw, bh = int(max(w1, w2) + pad * 2), int(font_px * 2.5 + pad)
    x0, y0 = w - bw - int(w * 0.02), h - bh - int(h * 0.03)
    plate = Image.new("RGBA", img.size, (0, 0, 0, 0))
    pd = ImageDraw.Draw(plate)
    pd.rounded_rectangle((x0, y0, x0 + bw, y0 + bh), radius=int(font_px * 0.5), fill=(20, 10, 34, 165))
    img.alpha_composite(plate)
    d = ImageDraw.Draw(img)
    d.text((x0 + pad, y0 + pad * 0.6), l1, font=font, fill=(255, 255, 255, 245))
    d.text((x0 + pad, y0 + pad * 0.6 + font_px * 1.3), l2, font=small, fill=(220, 200, 255, 235))


def build(slug, stem, out, hero_w=2200):
    im = Image.open(SRC / f"{stem}.jpeg")
    im.draft("RGB", (hero_w * 2, hero_w * 2))
    im = im.convert("RGB")
    h = round(im.height * hero_w / im.width)
    im = im.resize((hero_w, h), Image.LANCZOS).convert("RGBA")
    im.alpha_composite(tile_layer(im.size, max(28, round(hero_w * 0.021))))
    corner_mark(im, max(28, round(hero_w * 0.0155)))
    hero = im.convert("RGB")
    hero.save(out / f"{slug}-2200.webp", "WEBP", quality=80, method=6)
    th = hero.copy(); th.thumbnail((420, 420), Image.LANCZOS)
    th.save(out / f"{slug}-thumb.webp", "WEBP", quality=74, method=6)
    return hero.size


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--out", default="site/assets/photography")
    a = ap.parse_args(); out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    meta = []
    for slug, stem, cap, alt, focus in PHOTOS:
        w, h = build(slug, stem, out)
        meta.append({"slug": slug, "caption": cap, "alt": alt, "focus": focus, "w": w, "h": h})
        print(f"{slug}: {w}x{h}", flush=True)
    (out / "manifest.json").write_text(json.dumps(meta, indent=1, ensure_ascii=False))
