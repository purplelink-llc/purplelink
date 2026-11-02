#!/usr/bin/env python3
"""Write the in-browser converter pages (/tools/heic-to-jpg/ and siblings) from the data in PAGES.

Every page shares the converter shell in site/tools/convert/ and has its own text. The JSON-LD (HowTo steps, FAQ) is
built from the same data as the visible text, so the two cannot drift; site-tests/test_converters.py checks that.
The topbar, footer and head boilerplate are copied from /tools/metadata-cleaner/, then the usual build steps restamp
them. Design: docs/designs/browser-file-converters.md.

  python3 scripts/gen_converter_pages.py      # write the pages
  python3 scripts/apply_layout.py && python3 scripts/fingerprint_assets.py   # then, as for any page
"""
from __future__ import annotations

import html
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
TEMPLATE = SITE / "tools" / "metadata-cleaner" / "index.html"
BASE = "https://purplelink.llc"

NO_UPLOAD = "Are my files uploaded?"


def faq_uploaded(what: str, extra: str) -> tuple[str, str]:
    return (NO_UPLOAD,
            f"No. The page reads each {what} with your browser and converts it in a background worker in this tab. "
            "There is no server step. The meter under the drop zone counts the bytes the page and its worker send "
            f"while they work, so you can check this yourself. {extra}")


PAGES = [
    {
        "slug": "heic-to-jpg",
        "name": "HEIC to JPG",
        "title": "HEIC to JPG Converter That Runs in Your Browser | Purplelink",
        "og_title": "HEIC to JPG, converted in your browser",
        "description": "Convert iPhone HEIC photos to JPG or PNG in your browser. The photos are decoded on your device and "
                       "never uploaded. Free, no sign-up, batches as a zip.",
        "hero": "Convert HEIC photos from an iPhone or iPad to JPG, or to PNG. Each photo is decoded on your device, in "
                "this browser tab. Add one photo or a few hundred, then download them one by one "
                "or as a zip.",
        "accept": ".heic,.heif,image/heic,image/heif",
        "drop": "Drop HEIC photos here",
        "hint": "HEIC and HEIF, up to 100 MB each. You can also paste a photo with Ctrl or Cmd V.",
        "outputs": [("jpg", "JPG"), ("png", "PNG")],
        "jpeg_options": True,
        "wasm": True,
        "features": ["Convert HEIC and HEIF photos to JPG or PNG",
                     "Rotation stored in the photo is applied",
                     "Batches of up to 200 photos, downloadable as one zip",
                     "Decoded in the browser with libheif (WebAssembly); photos are never uploaded"],
        "how": [
            "HEIC is the format iPhones and iPads have used for photos since iOS 11. It stores a photo in about half the "
            "space of a JPG, but Windows without an add-on, many web forms and older software cannot open it.",
            "This page reads each photo with libheif, the open-source HEIF library, compiled to WebAssembly so it runs "
            "inside your browser. A background worker decodes the photo, turns it the way the camera recorded, draws it "
            "on an off-screen canvas, and the browser writes the result as a JPG or PNG.",
            "The decoder is a 1.5 MB file served from this site, fetched only when you add your first photo. "
            "It sends nothing back.",
            "On a Mac, Preview converts single photos too: open the photo, choose File, Export, and pick JPEG. This page "
            "is quicker for a batch, and it works on Windows and Chromebooks, where a HEIC file often does not open at all.",
        ],
        "steps": [
            ("Pick the format", "Choose JPG for photos you will share or upload, or PNG if you need every pixel kept exactly."),
            ("Add the photos", "Drop the HEIC files on the box, or click it to choose them."),
            ("Wait for each row", "Each photo is converted in turn. The row shows its progress, then the new size."),
            ("Download", "Download each photo from its row, or use Download all as .zip for the whole batch."),
        ],
        "limits": [
            "Up to 100 MB a file and 200 files at a time.",
            "The JPG or PNG has no EXIF data: the camera, the date taken and the location are not copied over.",
            "Only the main picture is converted. Live Photo motion, depth maps and HDR brightness data are left out.",
            "Colors are written as sRGB. Very saturated colors from an iPhone's wider Display P3 range can look a little flatter.",
            "On an iPhone or iPad, the browser can draw at most about 16.7 megapixels, so 24 and 48 MP photos need a computer.",
            "Needs Chrome or Edge 69, Firefox 105 or Safari 16.4, or later.",
        ],
        "faq": [
            faq_uploaded("photo", "The only things the page downloads are its own scripts and the decoder."),
            ("Should I choose JPG or PNG?",
             "JPG for photos. It is the smaller file and opens everywhere, and at the default quality of 92 it looks the same "
             "as the original to most eyes. PNG keeps every pixel exactly, but a photo saved as PNG is several times larger."),
            ("Does it keep the date taken and the location?",
             "No. The converted file is written fresh by the browser, so the EXIF block with the camera, date and GPS position "
             "is not carried over. That is useful when you share photos, and a loss if you sort a library by date. Preview "
             "on a Mac keeps the EXIF data when it exports."),
            ("Why are my photos HEIC in the first place?",
             "iPhones save photos as HEIC when Settings, Camera, Formats is set to High Efficiency, which is the default. "
             "Most Compatible saves new photos as JPG instead. Settings, Photos, Transfer to Mac or PC, Automatic converts "
             "photos to JPG when you copy them to a computer over a cable."),
            ("Why did a photo fail?",
             "The page checks the first bytes of each file, so a JPG renamed to .heic is named for what it is. A HEIC that "
             "fails to decode is usually damaged or cut short in transfer. A photo larger than the browser can draw gets a "
             "message that says so."),
            ("Can I use it on my iPhone?",
             "Yes, for photos up to about 16.7 megapixels, which is the most iOS lets a web page draw. Recent iPhones take "
             "24 or 48 MP photos by default, and those need a computer."),
            ("Is it free?",
             "Yes. There is no account, no watermark and no limit beyond the file sizes above."),
        ],
        "related": [("/tools/webp-to-png/", "WebP to PNG"), ("/tools/png-to-icns/", "PNG to ICNS"),
                    ("/tools/metadata-cleaner/", "Metadata Cleaner"), ("/tools/pdf-tools/", "PDF Tools")],
    },
    {
        "slug": "webp-to-png",
        "name": "WebP to PNG",
        "title": "WebP to PNG Converter, in Your Browser | Purplelink",
        "og_title": "WebP to PNG, converted in your browser",
        "description": "Convert WebP images to PNG or JPG in your browser. Nothing is uploaded, PNG keeps transparency, and "
                       "batches download as one zip. Free, no sign-up.",
        "hero": "Convert WebP images to PNG, or to JPG. Your browser decodes and re-encodes each image on your device. "
                "PNG keeps transparency; JPG fills it with a color you choose.",
        "accept": ".webp,image/webp",
        "drop": "Drop WebP images here",
        "hint": "WebP, up to 100 MB each. You can also paste an image with Ctrl or Cmd V.",
        "outputs": [("png", "PNG"), ("jpg", "JPG")],
        "jpeg_options": True,
        "features": ["Convert WebP images to PNG or JPG",
                     "Transparency kept in PNG; filled with a chosen color in JPG",
                     "Batches of up to 200 images, downloadable as one zip",
                     "Converted by the browser itself; images are never uploaded"],
        "how": [
            "Many sites serve their images as WebP because the files are smaller. Saving one from a browser gives a .webp "
            "file that older versions of Word and PowerPoint, some upload forms and pdfLaTeX do not take. pdfLaTeX's "
            "\\includegraphics reads PNG, JPG and PDF.",
            "Your browser already reads WebP. This page asks it to decode each file in a background worker, draws the "
            "pixels on an off-screen canvas and writes them out as PNG or JPG. No library is downloaded for it.",
            "PNG is lossless, so it keeps exactly what the WebP shows, including transparent areas. It cannot bring back "
            "detail that a lossy WebP already threw away.",
        ],
        "steps": [
            ("Pick the format", "Choose PNG to keep transparency and every pixel, or JPG for a smaller file. For JPG, pick the color that fills transparent areas."),
            ("Add the images", "Drop the WebP files on the box, click it to choose them, or paste an image you copied."),
            ("Wait for each row", "Each image is converted in turn and the row shows the new size."),
            ("Download", "Download each image from its row, or use Download all as .zip."),
        ],
        "limits": [
            "Up to 100 MB a file and 200 files at a time.",
            "An animated WebP becomes a still image of its first frame.",
            "Metadata in the WebP (EXIF, XMP) is not copied over.",
            "Colors are converted to sRGB by the browser.",
            "Needs Chrome or Edge 69, Firefox 105 or Safari 16.4, or later.",
        ],
        "faq": [
            faq_uploaded("image", "No library is downloaded at all; the browser's own WebP decoder does the work."),
            ("Should I choose PNG or JPG?",
             "PNG for screenshots, diagrams, logos and anything with transparent areas or sharp edges. JPG for photos, "
             "where it gives a much smaller file. JPG has no transparency, so transparent areas are filled with the color "
             "you pick, white by default."),
            ("Why is the PNG larger than the WebP?",
             "WebP compresses better than PNG, and a lossy WebP stores an approximation of the picture. PNG stores every "
             "pixel exactly, so the same picture takes more space. Choose JPG if the size matters more than exact pixels."),
            ("What happens to an animated WebP?",
             "The browser hands over the first frame, and that frame is converted. The page says so on the row."),
            ("Can I use the PNG in a LaTeX paper?",
             "Yes. pdfLaTeX and XeLaTeX read PNG and JPG with \\includegraphics from the graphicx package. Use PNG for "
             "plots and diagrams so lines stay crisp."),
            ("Is it free?",
             "Yes. There is no account, no watermark and no limit beyond the file sizes above."),
        ],
        "related": [("/tools/heic-to-jpg/", "HEIC to JPG"), ("/tools/png-to-icns/", "PNG to ICNS"),
                    ("/tools/metadata-cleaner/", "Metadata Cleaner"), ("/tools/latex-to-pdf/", "LaTeX to PDF")],
    },
    {
        "slug": "png-to-icns",
        "name": "PNG to ICNS",
        "title": "PNG to ICNS Converter for Mac Icons | Purplelink",
        "og_title": "PNG to ICNS for Mac icons, in your browser",
        "description": "Turn a PNG into a macOS .icns icon with every size from 16 to 1024 pixels, in your browser. "
                       "Optional .iconset folder for iconutil. Nothing is uploaded.",
        "hero": "Turn a PNG, JPG or WebP into a macOS .icns file with the ten icon entries Finder and the Dock use, from "
                "16 to 1024 pixels. The file is built in your browser. Start from a square picture of "
                "1024 by 1024 pixels for a sharp icon.",
        "accept": ".png,.jpg,.jpeg,.webp,image/png,image/jpeg,image/webp",
        "drop": "Drop a PNG here",
        "hint": "PNG, JPG or WebP, ideally square and 1024 pixels wide. You can also paste an image.",
        "outputs": [("icns", "ICNS")],
        "jpeg_options": False,
        "iconset": True,
        "features": ["Make a macOS .icns file from a PNG, JPG or WebP",
                     "All ten icon entries, 16 to 1024 pixels, at 1x and 2x",
                     "Optional .iconset folder named for iconutil",
                     "Built in the browser; images are never uploaded"],
        "how": [
            "An .icns file is a container: a short header, then one PNG for each icon size and pixel density. Finder "
            "picks the one that fits, from 16 pixels in a list view to 1024 pixels on a Retina screen.",
            "This page draws each size from your picture, halving it step by step so the small sizes stay clean, and "
            "writes the container byte by byte. It then reads the file back and checks every entry before it offers "
            "the download.",
            "Tick Include an .iconset folder to also get the PNGs named the way Apple's iconutil expects, from "
            "icon_16x16.png to icon_512x512@2x.png. Running iconutil -c icns on that folder builds the same kind of file "
            "on your own Mac.",
        ],
        "steps": [
            ("Start from a square picture", "Use a PNG of 1024 by 1024 pixels with a transparent background. Smaller pictures work but look soft at the large sizes."),
            ("Add it", "Drop the picture on the box, or click it to choose it."),
            ("Download the .icns", "Download the file from its row. Tick Include an .iconset folder first if you want the separate PNGs too."),
            ("Use it", "In Finder, select a folder or app, choose File, Get Info, and drag the .icns file onto the small icon at the top left of the window."),
        ],
        "limits": [
            "A picture that is not square is centered, with transparent space around it.",
            "Every size is drawn from the same picture. Icon designers often redraw 16 and 32 pixels by hand so they read at that size.",
            "SVG is not accepted. Export a 1024 pixel PNG from your drawing app first.",
            "macOS 10.8 and later read all ten entry types.",
            "Needs Chrome or Edge 69, Firefox 105 or Safari 16.4, or later.",
        ],
        "faq": [
            faq_uploaded("picture", "No library is downloaded; the browser draws the sizes and this page writes the file."),
            ("Which sizes are in the file?",
             "16, 32, 128, 256 and 512 pixels at 1x, and the same five at 2x (32, 64, 256, 512 and 1024 pixels), the "
             "same ten pictures an .iconset folder holds. They are stored as the entries icp4, icp5, ic07, ic08 and ic09, "
             "then ic11, ic12, ic13, ic14 and ic10. Each is a PNG with transparency."),
            ("Can I use it in an Xcode project?",
             "Xcode builds the app icon from the PNGs in an asset catalog. Tick Include an .iconset folder and drag those "
             "PNGs into the AppIcon set. The .icns file itself is what an app built without Xcode, or a script, points to "
             "with CFBundleIconFile in Info.plist."),
            ("How do I change a folder's icon?",
             "Select the folder in Finder and choose File, Get Info. Drag the .icns file onto the small icon at the top "
             "left of the Info window. To undo it, click that small icon and press Delete."),
            ("Why does my icon look blurry?",
             "Most often the source picture was smaller than 1024 pixels, so the larger sizes were enlarged. The page warns "
             "when that happens. Very thin lines can also fade at 16 and 32 pixels, which is why designers simplify the small "
             "sizes."),
            ("Is it free?",
             "Yes. There is no account and no watermark."),
        ],
        "related": [("/tools/heic-to-jpg/", "HEIC to JPG"), ("/tools/webp-to-png/", "WebP to PNG"),
                    ("/tools/metadata-cleaner/", "Metadata Cleaner")],
    },
]

DROP_ICON = ('<svg class="cv-drop-icon" viewBox="0 0 48 48" width="48" height="48" aria-hidden="true" focusable="false">'
             '<rect x="6" y="9" width="36" height="30" rx="3" fill="none" stroke="currentColor" stroke-width="2.4"/>'
             '<path d="M24 31V18m-6 6 6-6 6 6" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" '
             'stroke-linejoin="round"/></svg>')


def e(s: str) -> str:
    return html.escape(s, quote=True)


def halves(p: dict) -> tuple[str, str]:
    a, b = p["name"].split(" to ")
    return a, b


def jsonld(p: dict) -> str:
    url = f"{BASE}/tools/{p['slug']}/"
    src, dst = halves(p)
    graph = [
        {"@type": "WebApplication", "name": f"{p['name']} Converter", "url": url, "description": p["description"],
         "applicationCategory": "MultimediaApplication", "operatingSystem": "Any",
         "browserRequirements": "Requires JavaScript" + (" and WebAssembly" if p.get("wasm") else ""),
         "offers": {"@type": "Offer", "price": "0", "priceCurrency": "USD"},
         "publisher": {"@id": f"{BASE}/#organization"}, "featureList": p["features"]},
        {"@type": "HowTo", "name": f"How to convert {src} to {dst}",
         "tool": [{"@type": "HowToTool", "name": "A current web browser"}],
         "step": [{"@type": "HowToStep", "position": i + 1, "name": n, "text": t} for i, (n, t) in enumerate(p["steps"])]},
        {"@type": "FAQPage", "mainEntity": [{"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}}
                                           for q, a in p["faq"]]},
        {"@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Home", "item": f"{BASE}/"},
            {"@type": "ListItem", "position": 2, "name": "Tools", "item": f"{BASE}/tools/"},
            {"@type": "ListItem", "position": 3, "name": p["name"], "item": url}]},
    ]
    body = json.dumps({"@context": "https://schema.org", "@graph": graph}, indent=2, ensure_ascii=False)
    return body.replace("</", "<\\/")


def options_html(p: dict) -> str:
    rows = []
    if len(p["outputs"]) > 1:
        radios = "".join(
            f'<label><input type="radio" name="cv-output" value="{v}"{" checked" if i == 0 else ""}> {lab}</label>'
            for i, (v, lab) in enumerate(p["outputs"]))
        rows.append(f'<div class="cv-field"><span id="cv-out-label">Save as</span>'
                    f'<span class="cv-choice" role="radiogroup" aria-labelledby="cv-out-label">{radios}</span></div>')
    if p.get("jpeg_options"):
        rows.append('<label class="cv-field" data-for-output="jpg">JPEG quality <input type="range" id="cv-quality" '
                    'min="50" max="100" step="1" value="92"> '
                    '<output id="cv-quality-out" for="cv-quality">92</output></label>')
        rows.append('<label class="cv-field" data-for-output="jpg">Fill transparent areas with '
                    '<input type="color" id="cv-bg" value="#ffffff"></label>')
    if p.get("iconset"):
        rows.append('<label class="cv-field"><input type="checkbox" id="cv-iconset"> Include an .iconset folder of PNGs</label>')
    if not rows:
        return ""
    return ('        <fieldset class="cv-opts">\n          <legend>Options</legend>\n          '
            + "\n          ".join(rows) + "\n        </fieldset>\n")


def main_html(p: dict) -> str:
    src, dst = halves(p)
    how = "\n".join(f"        <p>{e(x)}</p>" for x in p["how"])
    steps = "\n".join(f"          <li><strong>{e(n)}.</strong> {e(t)}</li>" for n, t in p["steps"])
    limits = "\n".join(f"          <li>{e(x)}</li>" for x in p["limits"])
    faq = "\n".join(f'        <details><summary>{e(q)}</summary><div class="faq-body">{e(a)}</div></details>' for q, a in p["faq"])
    related = "\n".join(f'          <li><a href="{u}">{e(t)}</a></li>' for u, t in p["related"] + [("/tools/", "All tools")])
    return f"""    <main id="main-content">
      <a class="back-link" href="/tools/">← All tools</a>
      <div class="tools-hero">
        <p class="eyebrow">Free web tool</p>
        <h1>{e(p["name"])}</h1>
        <p>{e(p["hero"])} <strong>Nothing is uploaded.</strong></p>
      </div>

      <div class="tool-app cv-app" data-convert="{p["slug"]}">
        <input id="cv-file" class="sr-only cv-file" type="file" multiple accept="{p["accept"]}">
        <label class="cv-drop" id="cv-drop" for="cv-file">
          {DROP_ICON}
          <span class="cv-drop-label"><strong>{e(p["drop"])}</strong></span>
          <span class="btn btn-primary cv-small cv-drop-button">Choose files</span>
          <span class="cv-hint">{e(p["hint"])}</span>
        </label>
{options_html(p)}        <p class="cv-net" id="cv-net"><span class="cv-net-dot" aria-hidden="true"></span><span id="cv-net-text">Bytes of your files sent anywhere: 0</span></p>
        <p class="cv-status" id="cv-status" role="status" aria-live="polite"></p>
        <ul class="cv-list" id="cv-list" aria-label="Files"></ul>
        <div class="cv-bar" id="cv-bar" hidden>
          <button type="button" class="btn btn-primary" id="cv-all" hidden>Download all as .zip</button>
          <button type="button" class="btn btn-ghost" id="cv-clear">Clear</button>
        </div>
        <p class="tool-privacy">Files are read and converted in this tab, in a background worker. The only requests the page makes are for its own scripts. Your files are never sent anywhere.</p>
      </div>

      <section class="tool-prose cv-how" aria-labelledby="cv-how-h">
        <h2 id="cv-how-h">How it works</h2>
{how}
      </section>

      <section class="tool-howto">
        <h2>How to convert {e(src)} to {e(dst)}</h2>
        <ol>
{steps}
        </ol>
      </section>

      <section class="tool-prose" aria-labelledby="cv-limits-h">
        <h2 id="cv-limits-h">Limits</h2>
        <ul class="cv-limits">
{limits}
        </ul>
      </section>

      <section class="tool-faq">
        <h2>Questions</h2>
{faq}
      </section>

      <nav class="tool-related" aria-label="Related tools">
        <h2>More free tools</h2>
        <ul>
{related}
        </ul>
      </nav>

      <p class="tool-support">If this saves you time, you can <a href="https://buymeacoffee.com/bampel" target="_blank" rel="noopener">leave a tip</a>. It helps keep these tools free and online.</p>
    </main>
"""


def head_html(p: dict, tpl: str) -> str:
    url = f"{BASE}/tools/{p['slug']}/"
    card = f"{BASE}/assets/og/purplelink-card.png"
    existing = SITE / "tools" / p["slug"] / "index.html"
    if existing.is_file():  # keep the social card gen_og_cards.py rendered for this page
        m = re.search(r'<meta property="og:image" content="([^"]+)"', existing.read_text(encoding="utf-8"))
        if m:
            card = m.group(1)
    common = re.search(r'    <link rel="icon".*?<link rel="stylesheet" href="/motion\.css[^"]*">\n', tpl, re.S).group(0)
    common = re.sub(r"\?v=[0-9a-f]+", "", common)
    return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta name="robots" content="index, follow">
    <title>{e(p["title"])}</title>
    <meta name="description" content="{e(p["description"])}">
    <link rel="canonical" href="{url}">
    <meta property="og:type" content="website">
    <meta property="og:title" content="{e(p["og_title"])}">
    <meta property="og:description" content="{e(p["description"])}">
    <meta property="og:url" content="{url}">
    <meta property="og:image" content="{card}">
    <meta property="og:image:width" content="1200">
    <meta property="og:image:height" content="630">
    <meta name="twitter:card" content="summary_large_image">
    <meta name="twitter:title" content="{e(p["og_title"])}">
    <meta name="twitter:description" content="{e(p["description"])}">
    <meta name="twitter:image" content="{card}">
    <meta name="twitter:image:alt" content="{e(p["og_title"])}">
    <script type="application/ld+json">
{jsonld(p)}
    </script>
{common}    <script src="/site.js" defer></script>
    <script src="/motion.js" defer></script>
    <script src="/assets/vendor/jszip/jszip.min.js" defer></script>
    <link rel="stylesheet" href="/tools/convert/convert.css">
    <link rel="prefetch" as="script" data-convert-worker href="/tools/convert/convert-worker.js">
    <script src="/tools/convert/convert-core.js" defer></script>
    <script src="/tools/convert/convert-shell.js" defer></script>
  </head>
"""


def render(p: dict, tpl: str) -> str:
    body_start = tpl.index("  <body>")
    header = tpl[body_start:tpl.index("    <main")]
    footer = tpl[tpl.index("    <footer"):]
    return head_html(p, tpl) + header + main_html(p) + "\n\n\n" + footer


def main() -> int:
    tpl = TEMPLATE.read_text(encoding="utf-8")
    for p in PAGES:
        out = SITE / "tools" / p["slug"] / "index.html"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(render(p, tpl), encoding="utf-8")
        print(f"wrote {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
