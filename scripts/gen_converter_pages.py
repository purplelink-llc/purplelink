#!/usr/bin/env python3
"""Write the in-browser converter pages (/tools/heic-to-jpg/ and siblings) from the data in PAGES.

Every page shares the converter shell in site/tools/convert/ and has its own text. The JSON-LD (HowTo steps, FAQ) is
built from the same data as the visible text, so the two cannot drift; site-tests/test_converters.py checks that.
The topbar, footer and head boilerplate are copied from /tools/metadata-cleaner/, then the usual build steps restamp
them. Design: docs/designs/browser-file-converters.md.

  python3 scripts/gen_converter_pages.py      # write the pages
  python3 scripts/apply_layout.py   # then, as for any page (the build adds the ?v= stamps)
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
# Options shared by the pages that write CSV (XLSX to CSV, JSON to CSV).
SAFE = ("check", "safe", "Keep text that starts with = + - @ from running as a formula in Excel", True)
BOM = ("check", "bom", "Add a byte-order mark, so Excel on Windows shows accented letters", False)
SEP = ("select", "delimiter", "Separator", [("comma", "Comma"), ("semicolon", "Semicolon"), ("tab", "Tab")])
# PDF to JPG and SVG to PNG draw on the page, not in the converter worker, so their privacy line says so.
PAGE_PRIVACY = ("Files are read and drawn in this tab. The only requests the page makes are for its own scripts and the "
                "files they need. Your files are never sent anywhere.")


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
        "opts": ["output", "quality", "background"],
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
        "related": [("/tools/webp-to-png/", "WebP to PNG"), ("/tools/jpg-to-pdf/", "JPG to PDF"),
                    ("/tools/png-to-icns/", "PNG to ICNS"), ("/tools/metadata-cleaner/", "Metadata Cleaner")],
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
        "opts": ["output", "quality", "background"],
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
        "related": [("/tools/png-to-jpg/", "PNG to JPG"), ("/tools/avif-to-jpg/", "AVIF to JPG"), ("/tools/heic-to-jpg/", "HEIC to JPG"),
                    ("/tools/png-to-icns/", "PNG to ICNS"), ("/tools/latex-to-pdf/", "LaTeX to PDF")],
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
        "opts": [("check", "iconset", "Include an .iconset folder of PNGs", False)],
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
        "related": [("/tools/png-to-ico/", "PNG to ICO"), ("/tools/heic-to-jpg/", "HEIC to JPG"),
                    ("/tools/webp-to-png/", "WebP to PNG")],
    },
    {
        "slug": "png-to-ico",
        "name": "PNG to ICO",
        "title": "PNG to ICO Converter for Favicons and Windows Icons | Purplelink",
        "og_title": "PNG to ICO, built in your browser",
        "description": "Turn a PNG into an .ico file for a favicon or a Windows icon, with sizes from 16 to 256 pixels. Built in "
                       "your browser; nothing is uploaded.",
        "hero": "Turn a PNG, JPG or WebP into an .ico file. Choose every size from 16 to 256 pixels for a Windows icon, or "
                "16, 32 and 48 for a website's favicon. The file is built on your device.",
        "accept": ".png,.jpg,.jpeg,.webp,image/png,image/jpeg,image/webp",
        "drop": "Drop a PNG here",
        "hint": "PNG, JPG or WebP, ideally square and 256 pixels wide or more. You can also paste an image.",
        "outputs": [("ico", "ICO")],
        "opts": [("radio", "sizes", "Sizes", [("all", "All sizes, 16 to 256"), ("favicon", "Favicon: 16, 32, 48")])],
        "features": ["Make an .ico file from a PNG, JPG or WebP",
                     "Seven sizes from 16 to 256 pixels, or the three a favicon needs",
                     "Transparency kept",
                     "Built in the browser; images are never uploaded"],
        "how": [
            "An .ico file holds several copies of one picture at different sizes. Windows picks the one that fits the "
            "place it is shown, from 16 pixels in a title bar to 256 pixels in a large Explorer view, and browsers pick "
            "the one that fits a tab.",
            "This page draws each size from your picture, halving it step by step so the small sizes stay clean, stores "
            "each one as a PNG with transparency, and writes the .ico directory byte by byte. It reads the file back and "
            "checks every entry before it offers the download.",
            "For a website, put the file at the root of the site as /favicon.ico. Browsers ask for that address on their "
            "own, so it works even without a link tag. Most sites also add a 180 pixel PNG for iPhones with "
            "<link rel=\"apple-touch-icon\">.",
        ],
        "steps": [
            ("Start from a square picture", "Use a PNG of 256 by 256 pixels or more, with a transparent background if the icon should have one."),
            ("Pick the sizes", "Choose All sizes for a Windows program or shortcut icon, or Favicon for a website."),
            ("Add the picture", "Drop it on the box, or click the box to choose it."),
            ("Download", "Download the .ico file from its row."),
        ],
        "limits": [
            "Each size is stored as a PNG inside the .ico. Windows Vista and later, macOS and every current browser read "
            "these; Windows XP and some older icon editors and resource compilers expect bitmap entries instead.",
            "A picture that is not square is centered, with transparent space around it.",
            "Every size is drawn from the same picture, so a detailed logo can blur at 16 pixels. A simpler mark for the "
            "small sizes reads better.",
            "SVG is not accepted. Export a PNG from your drawing app first.",
            "Needs Chrome or Edge 69, Firefox 105 or Safari 16.4, or later.",
        ],
        "faq": [
            faq_uploaded("picture", "No library is downloaded; the browser draws the sizes and this page writes the file."),
            ("Which sizes should a favicon have?",
             "16 and 32 pixels cover browser tabs and bookmarks, and 48 pixels covers Windows site shortcuts. That is the "
             "Favicon set. Larger sizes make the file bigger without being used in a tab."),
            ("How do I add the favicon to my site?",
             "Upload favicon.ico to the top folder of the site, so it loads at yoursite.com/favicon.ico. Browsers look "
             "there by default. To be explicit, add <link rel=\"icon\" href=\"/favicon.ico\" sizes=\"any\"> to the page head."),
            ("How do I use the icon for a Windows shortcut?",
             "Right-click the shortcut, choose Properties, then Change Icon, and browse to the .ico file. Keep the file "
             "where it is; the shortcut points to it."),
            ("Does it keep transparency?",
             "Yes. Every size is a 32-bit PNG with its alpha channel. A JPG source has no transparency, so its icon is "
             "opaque."),
            ("Is it free?",
             "Yes. There is no account and no watermark."),
        ],
        "related": [("/tools/png-to-icns/", "PNG to ICNS"), ("/tools/photo-to-logo/", "Photo to Logo"),
                    ("/tools/webp-to-png/", "WebP to PNG"), ("/tools/heic-to-jpg/", "HEIC to JPG")],
    },
    {
        "slug": "jpg-to-pdf",
        "category": "UtilitiesApplication",
        "name": "JPG to PDF",
        "title": "JPG to PDF Converter That Runs in Your Browser | Purplelink",
        "og_title": "JPG to PDF, made in your browser",
        "description": "Turn JPG and PNG pictures into PDF pages in your browser, one file each or joined into one PDF. "
                       "JPEGs are not recompressed, and nothing is uploaded.",
        "hero": "Turn JPG and PNG pictures into PDF pages, one PDF each or all joined into one file in the order you set. "
                "JPEG photos and scans go into the PDF without being compressed again, and the PDF is written on your "
                "device.",
        "accept": ".jpg,.jpeg,.png,image/jpeg,image/png",
        "drop": "Drop JPG or PNG files here",
        "hint": "JPG and PNG, up to 100 MB each. You can also paste a picture with Ctrl or Cmd V.",
        "outputs": [("pdf", "PDF")],
        "opts": [("radio", "page", "Page size", [("a4", "A4"), ("letter", "US Letter"), ("fit", "Same as the picture")],
                  None, {"letter": "en-US,en-CA"}),
                 ("check", "margin", "Leave a 12 mm margin", True, "page=a4,letter")],
        "libs": ["pdf"],
        "combine": True,
        "features": ["Turn JPG and PNG pictures into PDF pages",
                     "One PDF per picture, or all joined into one PDF in the order you set",
                     "A4, US Letter, or a page the size of the picture",
                     "JPEGs embedded without recompression; phone photos turned upright",
                     "Made in the browser; pictures are never uploaded"],
        "how": [
            "A PDF can hold a JPEG exactly as it is, so this page copies each JPEG's bytes into the PDF instead of "
            "decoding and compressing it again. The page looks as sharp as the photo, and the PDF is barely larger than "
            "the JPEG.",
            "Phones store many photos sideways with a note saying which way is up. The page reads that note and turns the "
            "picture on the page, so portrait photos come out upright.",
            "PNG pictures are drawn by the browser first and then stored losslessly, with any transparent areas kept.",
            "The PDF is written by pdf-lib, an open-source library served from this site and loaded when you add your "
            "first picture. Join several into one file with Download as one PDF; use Move up and Move down on the rows to "
            "set the page order first.",
        ],
        "steps": [
            ("Pick the page size", "A4 or US Letter for something you will print or send as a form, or Same as the picture for a page that is just the picture."),
            ("Add the pictures", "Drop the JPG or PNG files on the box, or click it to choose them."),
            ("Set the order", "Use Move up and Move down on the rows if you want one PDF with the pages in a particular order."),
            ("Download", "Download each PDF from its row, or use Download as one PDF to join them all."),
        ],
        "limits": [
            "Up to 100 MB a picture and 200 pictures at a time. PNG pictures are limited to 25 megapixels, because the PDF "
            "library holds their pixels in memory.",
            "The text in a scanned page is not made searchable. That needs OCR, which this page does not do.",
            "JPEGs in a rare encoding (CMYK without Adobe's marker, 12-bit or arithmetic-coded) are redrawn at quality 95 "
            "instead of copied, and the row says so.",
            "Same as the picture uses the resolution stored in the file, so a 300 dpi scan of an A4 sheet gives an A4 page. "
            "Without one, it counts 96 pixels to the inch.",
            "The PDF has no EXIF data: camera, date and location are not copied over.",
            "Needs Chrome or Edge 69, Firefox 105 or Safari 16.4, or later.",
        ],
        "faq": [
            faq_uploaded("picture", "The only things the page downloads are its own scripts and the PDF library."),
            ("Does it reduce the quality of my photos?",
             "No, for JPEGs. Their bytes go into the PDF unchanged, so the picture in the PDF is the photo itself. PNGs are "
             "stored losslessly. The only pictures that change are rare JPEG encodings, which are redrawn at quality 95 "
             "with a note on the row."),
            ("How do I put several pictures in one PDF?",
             "Add them all, wait for each row to finish, put them in order with Move up and Move down, then choose Download "
             "as one PDF. Each picture becomes one page."),
            ("Which page size should I choose?",
             "A4 or US Letter when the PDF will be printed or uploaded to a form that expects a standard page. The picture is "
             "scaled to fit inside the margin, and the page turns landscape for a landscape picture. Same as the picture "
             "gives a page with no border, which suits photos and slides."),
            ("Why was my phone photo sideways in other converters?",
             "Phones often save a photo in the sensor's orientation and add a tag that says how to turn it. Software that "
             "ignores the tag shows it sideways. This page reads the tag and turns the picture on the page."),
            ("Can I combine existing PDFs too?",
             "This page turns pictures into PDFs. To join PDFs you already have, or split one, use PDF Tools."),
            ("Is it free?",
             "Yes. There is no account, no watermark and no page limit beyond the sizes above."),
        ],
        "related": [("/tools/pdf-to-jpg/", "PDF to JPG"), ("/tools/pdf-tools/", "PDF Tools"), ("/tools/heic-to-jpg/", "HEIC to JPG"),
                    ("/tools/webp-to-png/", "WebP to PNG"), ("/tools/metadata-cleaner/", "Metadata Cleaner")],
    },
    {
        "slug": "avif-to-jpg",
        "name": "AVIF to JPG",
        "title": "AVIF to JPG Converter, in Your Browser | Purplelink",
        "og_title": "AVIF to JPG, converted in your browser",
        "description": "Convert AVIF images to JPG or PNG in your browser. Nothing is uploaded, PNG keeps transparency, and "
                       "batches download as one zip. Free, no sign-up.",
        "hero": "Convert AVIF images to JPG, or to PNG. Your browser decodes each image and writes the new file on your "
                "device. PNG keeps transparency; JPG fills it with a color you choose.",
        "accept": ".avif,image/avif",
        "drop": "Drop AVIF images here",
        "hint": "AVIF, up to 100 MB each. You can also paste an image with Ctrl or Cmd V.",
        "outputs": [("jpg", "JPG"), ("png", "PNG")],
        "opts": ["output", "quality", "background"],
        "features": ["Convert AVIF images to JPG or PNG",
                     "Transparency kept in PNG; filled with a chosen color in JPG",
                     "Batches of up to 200 images, downloadable as one zip",
                     "Converted by the browser itself; images are never uploaded"],
        "how": [
            "AVIF is a newer image format that many sites now serve because its files are small. Saving an image from "
            "such a site gives a .avif file, which older Windows and Office versions, many upload forms and LaTeX do not "
            "open.",
            "Current browsers read AVIF. This page asks yours to decode each file in a background worker, draws the "
            "pixels on an off-screen canvas and writes them out as JPG or PNG. No library is downloaded for it.",
            "JPG is the smaller file and opens everywhere. PNG keeps every decoded pixel and any transparent areas.",
        ],
        "steps": [
            ("Pick the format", "Choose JPG for photos, or PNG to keep transparency and every pixel. For JPG, pick the quality and the color that fills transparent areas."),
            ("Add the images", "Drop the AVIF files on the box, click it to choose them, or paste an image you copied."),
            ("Wait for each row", "Each image is converted in turn and the row shows the new size."),
            ("Download", "Download each image from its row, or use Download all as .zip."),
        ],
        "limits": [
            "Up to 100 MB a file and 200 files at a time.",
            "The browser does the decoding, so it has to read AVIF: Chrome and Edge 85, Firefox 93, or Safari 16.4 on "
            "macOS 13 or iOS 16 and later.",
            "An animated AVIF becomes a still image of its first frame.",
            "HDR and 10-bit AVIF images are written as ordinary 8-bit sRGB, so very bright highlights are flattened.",
            "Metadata in the AVIF (EXIF, XMP) is not copied over.",
        ],
        "faq": [
            faq_uploaded("image", "No library is downloaded at all; the browser's own AVIF decoder does the work."),
            ("Why won't my browser read the AVIF file?",
             "Safari reads AVIF only from macOS 13 Ventura and iOS 16 onward. On an older Mac, open this page in Chrome, "
             "Edge or Firefox instead. If a current browser also fails, the file is likely damaged or cut short."),
            ("Should I choose JPG or PNG?",
             "JPG for photos: a much smaller file that opens everywhere, and at the default quality of 92 it looks the same "
             "to most eyes. PNG for screenshots, logos and anything with transparent areas or sharp edges."),
            ("Why is the JPG larger than the AVIF?",
             "AVIF compresses better than JPG, so the same picture takes more space as a JPG. Lower the JPEG quality to 80 "
             "for a smaller file with little visible change."),
            ("Can I use the result in a LaTeX paper or a Word document?",
             "Yes. pdfLaTeX reads JPG and PNG with \\includegraphics, and every version of Word, PowerPoint and Google Docs "
             "takes both."),
            ("Is it free?",
             "Yes. There is no account, no watermark and no limit beyond the file sizes above."),
        ],
        "related": [("/tools/webp-to-png/", "WebP to PNG"), ("/tools/heic-to-jpg/", "HEIC to JPG"),
                    ("/tools/jpg-to-pdf/", "JPG to PDF"), ("/tools/metadata-cleaner/", "Metadata Cleaner")],
    },
    {
        "slug": "csv-to-xlsx",
        "category": "BusinessApplication",
        "name": "CSV to XLSX",
        "title": "CSV to XLSX Converter That Keeps Your Data Intact | Purplelink",
        "og_title": "CSV to XLSX, converted in your browser",
        "description": "Convert CSV files to Excel .xlsx in your browser without losing leading zeros, long IDs or text that "
                       "looks like a date. Nothing is uploaded.",
        "hero": "Convert CSV and TSV files to Excel .xlsx. Leading zeros, long ID numbers and values that look like dates "
                "stay exactly as they are in the CSV, which is what usually goes wrong when Excel opens a CSV itself. "
                "The workbook is built on your device.",
        "accept": ".csv,.tsv,.txt,.tab,text/csv,text/tab-separated-values,text/plain",
        "drop": "Drop CSV files here",
        "hint": "CSV, TSV or TXT, up to 50 MB each.",
        "outputs": [("xlsx", "XLSX")],
        "opts": [("select", "delimiter", "Separator", [("auto", "Detect"), ("comma", "Comma"), ("semicolon", "Semicolon"),
                                                        ("tab", "Tab"), ("pipe", "Pipe")]),
                 ("select", "encoding", "Text encoding", [("auto", "Detect"), ("utf-8", "UTF-8"),
                                                          ("windows-1252", "Windows-1252 (Western)"),
                                                          ("iso-8859-2", "ISO-8859-2 (Central European)"),
                                                          ("shift_jis", "Shift JIS (Japanese)"),
                                                          ("gb18030", "GB18030 (Chinese)"), ("utf-16le", "UTF-16")]),
                 ("check", "header", "First row is a header (bold and frozen)", True),
                 ("check", "text", "Keep every value as text", False)],
        "features": ["Convert CSV and TSV files to Excel .xlsx",
                     "Leading zeros, long IDs and date-like text kept as written",
                     "Separator and text encoding detected, or set by hand",
                     "Header row made bold and frozen",
                     "Built in the browser; files are never uploaded"],
        "how": [
            "When Excel opens a CSV directly, it guesses what each value is. It drops the leading zero from ZIP codes and "
            "IDs such as 02134, shows a 16-digit account number in scientific notation and rounds its last digits, and "
            "turns values like 3-4 or MARCH1 into dates. Researchers know the last one from gene names.",
            "This page builds the .xlsx itself and only stores a value as a number when it is written as a plain number "
            "that Excel can hold exactly. Everything else is stored as text, as written. Formulas are never created, so a "
            "value starting with an equals sign shows as text.",
            "It reads the text as UTF-8, or as Windows-1252 if the file is not valid UTF-8 (the usual export from older "
            "Excel on Windows). It finds the separator by looking for the character that splits the first lines into the "
            "same number of columns. The row says what it used, and both can be set by hand.",
            "The workbook is assembled with JSZip, served from this site, in a background worker in this tab.",
        ],
        "steps": [
            ("Add the CSV", "Drop the file on the box, or click it to choose it. Several files give one workbook each."),
            ("Check the row", "The row shows the number of rows and columns, the text encoding and the separator it used."),
            ("Fix the reading if needed", "If the columns look wrong, set the separator or the encoding, then add the file again."),
            ("Download", "Download the .xlsx from its row, or use Download all as .zip."),
        ],
        "limits": [
            "Up to 50 MB a file and 5 million cells, because the sheet is built in this tab's memory.",
            "Excel's own limits apply: 1,048,576 rows and 16,384 columns. Cells over 32,767 characters are cut there, with a "
            "note.",
            "Dates stay as text. To make a column real dates in Excel, select it and use Data, Text to Columns, and choose "
            "the date order.",
            "Whole numbers of 12 digits or more stay text, so IDs and card numbers are not shown as 1.23457E+11.",
            "In a semicolon-separated file, 3,14 is read as the number 3.14, as European Excel writes it. In other files a "
            "comma inside a number keeps it as text.",
            "One sheet per file. Several CSVs are not merged into one workbook.",
        ],
        "faq": [
            faq_uploaded("file", "The only things the page downloads are its own scripts and the zip library."),
            ("Why do my leading zeros survive here and not in Excel?",
             "Excel reads 02134 as the number 2134 when it opens a CSV. This page stores any value with a leading zero as "
             "text, so Excel shows 02134. The same goes for values with a leading plus sign, such as phone numbers."),
            ("Which values become numbers?",
             "Plain numbers such as 42, -3.5, 0.007 or 1.5e-3, up to 15 significant digits and under 12 digits for whole "
             "numbers. A number written as 1.10 is stored as 1.1, as Excel would show it. Tick Keep every value as text to "
             "store everything as text."),
            ("My columns are all in column A. What went wrong?",
             "The separator was read wrongly, which can happen with very short files. Set the separator by hand, for "
             "example Semicolon for files exported from European versions of Excel, and add the file again."),
            ("The accents look wrong. How do I fix it?",
             "The file is in a different text encoding than the one detected. Set Text encoding to the one the file was "
             "saved in, often Windows-1252 for older Windows exports, and add the file again."),
            ("Is it safe to open the result?",
             "Yes. Every cell is stored as a value, and no formula is written, so a CSV that contains text like "
             "=HYPERLINK(...) cannot run anything when the workbook opens."),
            ("Is it free?",
             "Yes. There is no account, no watermark and no limit beyond the sizes above."),
        ],
        "related": [("/tools/xlsx-to-csv/", "XLSX to CSV"), ("/tools/json-to-csv/", "JSON to CSV"),
                    ("/tools/jpg-to-pdf/", "JPG to PDF"), ("/tools/pdf-tools/", "PDF Tools"),
                    ("/tools/metadata-cleaner/", "Metadata Cleaner")],
    },

    {
        "slug": "pdf-to-jpg",
        "name": "PDF to JPG",
        "title": "PDF to JPG Converter That Runs in Your Browser | Purplelink",
        "og_title": "PDF to JPG, converted in your browser",
        "description": "Turn PDF pages into JPG or PNG images in your browser, at 72, 150 or 300 dpi. The PDF is read on "
                       "your device and never uploaded. Free, no sign-up.",
        "hero": "Turn the pages of a PDF into JPG or PNG images, at screen, standard or print resolution. Pick all the "
                "pages or a range. Each page is drawn on your device, in this browser tab.",
        "accept": ".pdf,application/pdf",
        "drop": "Drop PDF files here",
        "hint": "PDF, up to 100 MB each and 500 pages at a time.",
        "outputs": [("jpg", "JPG"), ("png", "PNG")],
        "opts": ["output", "quality",
                 ("radio", "dpi", "Resolution", [("150", "150 dpi"), ("300", "300 dpi, for print"), ("72", "72 dpi, for screens")]),
                 ("text", "pages", "Pages", "All", None, "Leave empty for every page, or enter pages like 1-3, 8.", True)],
        "libs": ["pdfjs", "pdfjs-worker"],
        "privacy": PAGE_PRIVACY,
        "features": ["Turn PDF pages into JPG or PNG images",
                     "72, 150 or 300 dpi, all pages or a range",
                     "Includes pdf.js's decoders for JBIG2 and JPEG 2000 scans",
                     "Many pages download as one zip",
                     "Drawn in the browser with pdf.js; PDFs are never uploaded"],
        "how": [
            "A PDF page is a set of drawing instructions: text in its fonts, lines, and the pictures inside it. To make "
            "a JPG, something has to carry out those instructions at a chosen resolution. This page uses pdf.js, the "
            "open-source PDF reader built into Firefox, served from this site and loaded when you add your first PDF.",
            "pdf.js reads the file in a background worker and draws each page on a canvas in this tab, with the fonts "
            "embedded in the PDF. The browser then writes the canvas as a JPG or PNG.",
            "Resolution is in dots per inch of the page. A US Letter page at 150 dpi is 1275 by 1650 pixels, enough for "
            "a screen or a slide; 300 dpi is 2550 by 3300, for printing or reading small print.",
            "On a Mac, Née, our file converter, does this from Finder: hold Option while dragging a PDF and drop it on "
            "the action for its pages. Née saves the pages as PNG.",
        ],
        "steps": [
            ("Pick the format and resolution", "JPG for a smaller file, PNG for sharp text and line art. 150 dpi suits screens and slides, 300 dpi printing."),
            ("Choose the pages", "Leave Pages empty for the whole PDF, or enter a range such as 1-3, 8."),
            ("Add the PDF", "Drop the PDF on the box, or click it to choose it."),
            ("Download", "A one-page result downloads as a picture; more pages download together as a zip."),
        ],
        "limits": [
            "Up to 100 MB a PDF, 200 PDFs at a time, and 500 pages a PDF per run. For a longer PDF, convert it in ranges.",
            "A page that would be larger than about 40 megapixels at the chosen resolution, such as a poster at 300 dpi, is "
            "drawn at a lower resolution, and the row says which. On a phone the cap is about 16.7 megapixels.",
            "A PDF locked with a password to open cannot be read. A PDF that only restricts printing or copying converts.",
            "Form fields show the values saved in the file. Links, comments in a side panel and attached files are not part of the picture.",
            "The images inside a PDF are drawn as part of the page, not saved one by one at their own resolution.",
            "Needs a current version of Chrome, Edge, Firefox or Safari.",
        ],
        "faq": [
            (NO_UPLOAD,
             "No. pdf.js reads the PDF in a background worker in this tab and the page draws it on a canvas. There is no "
             "server step. The meter under the drop zone counts the bytes the page sends while it works, so you can check "
             "this yourself. The page downloads only its own scripts, and the fonts and decoders pdf.js needs from this site."),
            ("Should I choose JPG or PNG?",
             "JPG for pages with photos, and when the file size matters. PNG for pages of text, charts and diagrams: it "
             "keeps the edges of letters sharp, though the file is larger."),
            ("Which resolution should I use?",
             "150 dpi for a screen, a slide or an upload form. 300 dpi to print the image or to zoom into small text. 72 "
             "dpi gives small previews. The pixel size of each page shows in its row."),
            ("How do I convert only some pages?",
             "Type them under Pages before you add the PDF: 3 for one page, 2-5 for a range, 1, 4, 9-12 for a mix, or 10- "
             "for page 10 to the end. Leave it empty for every page."),
            ("Will scanned PDFs look right?",
             "Yes, in most cases. Office scanners often store black-and-white pages as JBIG2 and some archives use JPEG "
             "2000; this page includes pdf.js's decoders for both. The text in a scan stays part of the picture."),
            ("Why did my PDF fail?",
             "The page checks that the file starts as a PDF. One that is damaged or cut short in a download cannot be "
             "opened, and one locked with a password needs that password removed first. If a single page fails to draw, "
             "the others are kept and the row names the missing page."),
            ("Is it free?",
             "Yes. There is no account, no watermark and no limit beyond the sizes above."),
        ],
        "related": [("/tools/jpg-to-pdf/", "JPG to PDF"), ("/tools/pdf-tools/", "PDF Tools"),
                    ("/tools/png-to-jpg/", "PNG to JPG"), ("/nee/", "Née, a Mac converter")],
    },
    {
        "slug": "svg-to-png",
        "name": "SVG to PNG",
        "title": "SVG to PNG Converter, in Your Browser | Purplelink",
        "og_title": "SVG to PNG, converted in your browser",
        "description": "Convert SVG drawings to PNG or JPG at 1x, 2x, 4x or any width, in your browser. Transparency is "
                       "kept, and nothing is uploaded. Free, no sign-up.",
        "hero": "Convert SVG drawings, figures and icons to PNG, or to JPG, at the size you need. The drawing is scaled as a "
                "vector, so a 4x PNG is sharp, not enlarged. Your browser draws each file on your device.",
        "accept": ".svg,.svgz,image/svg+xml",
        "drop": "Drop SVG files here",
        "hint": "SVG and SVGZ, up to 10 MB each. You can also paste a file with Ctrl or Cmd V.",
        "outputs": [("png", "PNG"), ("jpg", "JPG")],
        "opts": ["output", "quality", "background",
                 ("radio", "scale", "Size", [("2", "2x"), ("1", "1x"), ("4", "4x"), ("width", "Width in pixels")]),
                 ("number", "width", "Width", (1920, 16, 16384), "scale=width")],
        "privacy": PAGE_PRIVACY,
        "features": ["Convert SVG and SVGZ files to PNG or JPG",
                     "1x, 2x, 4x or an exact width, scaled as a vector",
                     "Transparency kept in PNG",
                     "Drawn by the browser itself; files are never uploaded"],
        "how": [
            "SVG describes a drawing as shapes rather than pixels, so it stays sharp at any size. Many places still want "
            "pixels: pdfLaTeX's \\includegraphics reads PNG, JPG and PDF but not SVG, and some slide tools, upload forms "
            "and older versions of Word do not take it either.",
            "This page reads the SVG's own size (its width and height in pixels, points, millimeters or inches, or its "
            "viewBox), sets the size you chose, and lets your browser draw it on a canvas. The PNG keeps transparent "
            "areas; a JPG fills them with the color you pick.",
            "A browser draws an SVG as a picture in a sealed mode: scripts in the file do not run, and nothing it links "
            "to is fetched. That is safer, and it is also why linked images and web fonts do not appear.",
        ],
        "steps": [
            ("Pick the format and size", "PNG to keep transparency, JPG for a solid background. 2x suits most screens and slides; set a width for an exact size."),
            ("Add the drawings", "Drop the SVG files on the box, click it to choose them, or paste a file you copied."),
            ("Wait for each row", "Each drawing is drawn in turn and the row shows its pixel size."),
            ("Download", "Download each picture from its row, or use Download all as .zip."),
        ],
        "limits": [
            "Up to 10 MB a file (unpacked, for SVGZ) and 200 files at a time.",
            "The result can be up to about 40 megapixels, such as 8000 by 5000 pixels; 16.7 megapixels on a phone.",
            "Images the SVG links to on the web and web fonts it asks for are not loaded. Text uses the fonts installed on "
            "this device, so convert text to outlines in your drawing app if the exact font matters.",
            "Animations and scripts are not run; the PNG shows the drawing as it first appears.",
            "Needs Chrome or Edge 69, Firefox 105 or Safari 16.4, or later.",
        ],
        "faq": [
            (NO_UPLOAD,
             "No. Your browser reads each SVG and draws it on a canvas in this tab. There is no server step. The meter "
             "under the drop zone counts the bytes the page sends while it works, so you can check this yourself."),
            ("What size will the PNG be?",
             "The SVG's own size times the factor you pick. An icon that is 24 by 24 at 1x is 48 by 48 at 2x and 96 by 96 "
             "at 4x. Width in pixels sets the width exactly and keeps the proportions. An SVG with no size at all is drawn "
             "at 300 by 150, the size browsers use, and the row says so."),
            ("Is the PNG sharp at 4x?",
             "Yes. The size is set on the SVG before it is drawn, so the shapes are drawn at the new size rather than "
             "drawn small and then enlarged."),
            ("How do I use an SVG figure in LaTeX?",
             "pdfLaTeX cannot include an SVG. Convert it to PNG at 4x, or at the width in pixels your column needs at 300 "
             "dpi (about 1000 pixels for a single column), and include the PNG. For a figure that stays vector, export a PDF "
             "from the drawing app instead."),
            ("Why is the text in a different font?",
             "An SVG drawn as a picture can only use fonts installed on this device or embedded in the file. If it names a "
             "web font, the browser substitutes another. Converting the text to outlines in the drawing app avoids that."),
            ("Is it free?",
             "Yes. There is no account, no watermark and no limit beyond the sizes above."),
        ],
        "related": [("/tools/png-to-icns/", "PNG to ICNS"), ("/tools/png-to-ico/", "PNG to ICO"),
                    ("/tools/png-to-jpg/", "PNG to JPG"), ("/tools/equation-renderer/", "Equation Renderer")],
    },
    {
        "slug": "png-to-jpg",
        "name": "PNG to JPG",
        "title": "PNG to JPG Converter That Runs in Your Browser | Purplelink",
        "og_title": "PNG to JPG, converted in your browser",
        "description": "Convert PNG, GIF and BMP images to JPG in your browser, with the quality and background you choose. "
                       "Nothing is uploaded. Free, no sign-up, batches as a zip.",
        "hero": "Convert PNG images to JPG, usually a much smaller file. GIF and BMP work too. Pick the quality and the color "
                "that fills transparent areas. Your browser converts each image on your device.",
        "accept": ".png,.gif,.bmp,image/png,image/gif,image/bmp",
        "drop": "Drop PNG images here",
        "hint": "PNG, GIF and BMP, up to 100 MB each. You can also paste an image with Ctrl or Cmd V.",
        "outputs": [("jpg", "JPG")],
        "opts": ["quality", "background"],
        "features": ["Convert PNG, GIF and BMP images to JPG",
                     "Choose the JPEG quality and the fill for transparent areas",
                     "Batches of up to 200 images, downloadable as one zip",
                     "Converted by the browser itself; images are never uploaded"],
        "how": [
            "PNG stores every pixel exactly, which is right for screenshots and diagrams but makes photos large. JPG "
            "stores photos in a fraction of the space by dropping detail the eye barely sees, which is why upload forms "
            "with a size limit often ask for it.",
            "Your browser already reads PNG, GIF and BMP. This page asks it to decode each file in a background worker, "
            "draws it on an off-screen canvas over the fill color you pick, and writes a JPG at the quality you set.",
            "JPG has no transparency, so transparent areas become the fill color, white unless you change it. Text and "
            "sharp lines can show faint ripples in a JPG; keep those images as PNG, or use quality 95 or more.",
            "On a Mac, Née, our file converter, makes JPEG copies from Finder: hold Option while dragging the images and "
            "drop them on the action you want.",
        ],
        "steps": [
            ("Set the quality and fill", "92 suits most images; lower it for a smaller file. Pick the color for transparent areas."),
            ("Add the images", "Drop the PNG, GIF or BMP files on the box, click it to choose them, or paste an image you copied."),
            ("Wait for each row", "Each image is converted in turn and the row shows the old and new size."),
            ("Download", "Download each JPG from its row, or use Download all as .zip."),
        ],
        "limits": [
            "Up to 100 MB a file and 200 files at a time.",
            "An animated PNG or GIF gives one JPG of its first frame, and the row says so.",
            "Text notes stored in a PNG and any EXIF data are not copied into the JPG.",
            "On an iPhone or iPad, the browser can draw at most about 16.7 megapixels.",
            "Needs Chrome or Edge 69, Firefox 105 or Safari 16.4, or later.",
        ],
        "faq": [
            faq_uploaded("image", "The only things the page downloads are its own scripts."),
            ("How much smaller will the JPG be?",
             "For a photo saved as PNG, often five to ten times smaller at the default quality. For a screenshot or "
             "diagram with large flat areas, the PNG may already be small, and the JPG can even be larger. The row shows "
             "both sizes."),
            ("What happens to a transparent background?",
             "JPG cannot store transparency, so those areas are filled with the color you choose, white by default. To keep "
             "transparency, stay with PNG, or use WebP to PNG and HEIC to JPG for those formats."),
            ("Which quality should I pick?",
             "92, the default, looks the same as the original to most eyes. 80 to 85 gives a smaller file for the web. "
             "95 and above keeps text and edges cleaner at a larger size."),
            ("Does it work with GIF and BMP?",
             "Yes. A GIF gives its first frame, and a BMP converts like a PNG. Both usually get much smaller as JPG."),
            ("Is it free?",
             "Yes. There is no account, no watermark and no limit beyond the file sizes above."),
        ],
        "related": [("/tools/webp-to-png/", "WebP to PNG"), ("/tools/heic-to-jpg/", "HEIC to JPG"),
                    ("/tools/tiff-to-jpg/", "TIFF to JPG"), ("/tools/pdf-to-jpg/", "PDF to JPG"), ("/nee/", "Née, a Mac converter")],
    },
    {
        "slug": "xlsx-to-csv",
        "name": "XLSX to CSV",
        "title": "XLSX to CSV Converter That Runs in Your Browser | Purplelink",
        "og_title": "XLSX to CSV, converted in your browser",
        "description": "Convert Excel workbooks to CSV in your browser, one sheet or all of them. Dates stay dates, and "
                       "nothing is uploaded. Free, no sign-up.",
        "hero": "Convert Excel workbooks (.xlsx) to CSV files, the first sheet or every sheet. Dates come out as dates, "
                "formulas as their results, and text exactly as typed. The workbook is read on your device.",
        "accept": ".xlsx,.xlsm,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "drop": "Drop Excel workbooks here",
        "hint": "XLSX and XLSM, up to 50 MB each.",
        "outputs": [("csv", "CSV")],
        "opts": [("radio", "sheets", "Sheets", [("first", "First sheet"), ("all", "All sheets, as a zip")]), SEP, SAFE, BOM],
        "category": "BusinessApplication",
        "features": ["Convert Excel .xlsx and .xlsm workbooks to CSV",
                     "The first sheet, or every sheet as its own CSV in a zip",
                     "Dates written as ISO dates; formulas as their saved results",
                     "Comma, semicolon or tab separated",
                     "Read in the browser; workbooks are never uploaded"],
        "how": [
            "An .xlsx file is a zip of XML files: one lists the sheets, one holds the text that cells share, one the "
            "cell styles, and one each sheet's cells. This page opens the zip with JSZip, served from this site, and "
            "reads those parts in a background worker in this tab.",
            "Each cell is written as the workbook stores it. Dates are stored as day counts and shown as dates only "
            "through their format, so the page reads the format and writes 2026-11-03 rather than 46329. A formula "
            "gives the result Excel saved with the file. Empty cells and rows stay empty, so columns line up.",
            "Text that starts with =, +, - or @ was harmless in the workbook but can run as a formula when Excel opens "
            "a CSV. With the first option on, such text gets an apostrophe in front, which Excel hides. Numbers are "
            "never changed, so -5 stays -5.",
        ],
        "steps": [
            ("Pick the sheets and separator", "First sheet for a one-sheet export, All sheets for a zip with one CSV per sheet. Comma suits most tools; semicolon suits Excel where a comma is the decimal mark."),
            ("Add the workbooks", "Drop the .xlsx files on the box, or click it to choose them."),
            ("Check the row", "Each row says how many rows were read and notes hidden sheets or formulas without a saved result."),
            ("Download", "Download each CSV from its row, or use Download all as .zip."),
        ],
        "limits": [
            "Up to 50 MB a workbook, 100 MB of data in a sheet once unpacked, and 5 million cells.",
            "Numbers are written as stored, not as displayed: a cell shown as 12% is written 0.12, and currency signs "
            "and thousands separators are left out. An ID typed as a number with more than 15 digits has already been "
            "rounded inside the workbook.",
            "The older .xls format and workbooks protected with a password cannot be read. Save them as an unprotected "
            ".xlsx first.",
            "Charts, images, comments and cell colors are not part of a CSV.",
            "The CSV is UTF-8. Excel on Windows needs the byte-order mark option to show accented letters correctly; "
            "R, Python and most other tools read it either way.",
        ],
        "faq": [
            ("Are my files uploaded?",
             "No. The page reads each workbook with your browser and converts it in a background worker in this tab. "
             "There is no server step. The meter under the drop zone counts the bytes the page and its worker send "
             "while they work, so you can check this yourself. The only things the page downloads are its own scripts."),
            ("How are dates written?",
             "As ISO 8601: 2026-11-03 for a date, 2026-11-03 14:05:00 for a date and time, 14:05:00 for a time. Excel "
             "stores dates as day counts, and the page reads each cell's format to tell a date from a number. Workbooks "
             "from old Mac Excel that count from 1904 are read correctly too."),
            ("What happens to formulas?",
             "Each formula gives the result Excel saved in the file, as Excel's own Save as CSV does. A workbook made by a "
             "program that writes formulas without results has empty cells there; the row says how many. Opening it in "
             "Excel and saving it once stores the results."),
            ("Why does some text start with an apostrophe?",
             "Text that starts with =, +, - or @ can run as a formula when Excel opens a CSV, which is how malicious "
             "spreadsheets spread. The apostrophe makes Excel show it as text. Turn the option off if the CSV is for R, "
             "Python or a database, which do not run formulas."),
            ("Can I convert every sheet?",
             "Yes. Choose All sheets and each sheet becomes its own CSV, named after the sheet, in one zip. Hidden sheets "
             "are included, and the row names them. Chart sheets have no cells and are skipped."),
            ("Is it free?",
             "Yes. There is no account, no watermark and no limit beyond the sizes above."),
        ],
        "related": [("/tools/csv-to-xlsx/", "CSV to XLSX"), ("/tools/json-to-csv/", "JSON to CSV"),
                    ("/tools/pdf-tools/", "PDF Tools"), ("/tools/metadata-cleaner/", "Metadata Cleaner")],
    },
    {
        "slug": "json-to-csv",
        "name": "JSON to CSV",
        "title": "JSON to CSV Converter That Runs in Your Browser | Purplelink",
        "og_title": "JSON to CSV, converted in your browser",
        "description": "Convert JSON and JSON Lines to CSV or Excel in your browser. Nested objects become columns, and "
                       "long IDs stay exact. Nothing is uploaded. Free.",
        "hero": "Convert JSON from an API, a survey tool or a database export to a CSV file or an Excel workbook. Nested "
                "objects become columns, every key gets a column, and long numeric IDs are kept digit for digit. The "
                "file is read on your device.",
        "accept": ".json,.jsonl,.ndjson,.geojson,.txt,application/json",
        "drop": "Drop JSON files here",
        "hint": "JSON, JSON Lines and NDJSON, up to 50 MB each.",
        "outputs": [("csv", "CSV"), ("xlsx", "XLSX")],
        "opts": ["output", ("radio", "nested", "Nested objects", [("columns", "As columns (a.b)"), ("json", "As JSON text")]),
                 SEP + ("output=csv",), SAFE + ("output=csv",), BOM + ("output=csv",)],
        "category": "DeveloperApplication",
        "features": ["Convert JSON arrays, API replies and JSON Lines to CSV or XLSX",
                     "Nested objects flattened into a.b columns, or kept as JSON text",
                     "A column for every key, in the order they first appear",
                     "Integers longer than 15 digits kept exactly",
                     "Converted in the browser; files are never uploaded"],
        "how": [
            "The page looks for the rows in your file. A JSON array is the rows. An API reply such as {\"data\": [...]} "
            "uses its largest list of objects, and the row says which key that was. A file with one JSON value per "
            "line is read as JSON Lines.",
            "Every key becomes a column, in the order the keys first appear, so records with different fields still "
            "line up. A nested object such as {\"user\": {\"name\": \"Ada\"}} becomes a column user.name. Lists stay "
            "as JSON text in one cell, since they have no fixed width.",
            "Browsers round integers past 9,007,199,254,740,991 when they read JSON, which quietly breaks long IDs. "
            "This page reads those numbers as text before parsing, so a 19-digit ID comes out exactly as written.",
        ],
        "steps": [
            ("Pick CSV or XLSX", "CSV for scripts and databases, XLSX to open in Excel with long IDs kept as text."),
            ("Choose how nested objects are written", "As columns gives one column per nested field; As JSON text keeps each object in one cell."),
            ("Add the files", "Drop the JSON files on the box, or click it to choose them."),
            ("Download", "Download each result from its row, or use Download all as .zip."),
        ],
        "limits": [
            "Up to 50 MB a file and 5 million cells.",
            "Lists inside a record are written as JSON text, not spread over columns.",
            "When an API reply holds several lists, the largest is used and the row names the others.",
            "In XLSX output, a value that looks like a number, such as the text \"42\", becomes a number cell; leading "
            "zeros and long IDs stay text.",
            "The CSV is UTF-8. Excel on Windows needs the byte-order mark option to show accented letters correctly.",
        ],
        "faq": [
            ("Are my files uploaded?",
             "No. The page reads each file with your browser and converts it in a background worker in this tab. There "
             "is no server step. The meter under the drop zone counts the bytes the page and its worker send while they "
             "work, so you can check this yourself. The only things the page downloads are its own scripts."),
            ("What JSON shapes does it read?",
             "An array of objects, an object that holds such an array (common in API replies), a single object, an "
             "array of plain values, and JSON Lines with one value per line. Records do not need the same keys."),
            ("How are nested objects handled?",
             "With As columns, {\"user\": {\"name\": \"Ada\", \"age\": 36}} gives the columns user.name and user.age. "
             "With As JSON text, the whole object goes in one user column. Lists are always kept as JSON text. If a "
             "record already has a key named user.name, the flattened one becomes user.name (2)."),
            ("Will my long IDs survive?",
             "Yes. Integers of 16 digits or more, such as social media post IDs, are read as text before the browser "
             "parses the file, so they are written exactly. In Excel output they are text cells, so Excel cannot round "
             "them either."),
            ("Why does some text start with an apostrophe?",
             "Text that starts with =, +, - or @ can run as a formula when Excel opens a CSV. The apostrophe makes Excel "
             "treat it as text. Numbers are never changed. Turn the option off for CSVs meant for scripts."),
            ("Is it free?",
             "Yes. There is no account, no watermark and no limit beyond the sizes above."),
        ],
        "related": [("/tools/csv-to-xlsx/", "CSV to XLSX"), ("/tools/xlsx-to-csv/", "XLSX to CSV"),
                    ("/tools/file-to-markdown/", "File to Markdown"), ("/tools/pii-checker/", "PII Checker")],
    },
    {
        "slug": "tiff-to-jpg",
        "name": "TIFF to JPG",
        "title": "TIFF to JPG Converter That Runs in Your Browser | Purplelink",
        "og_title": "TIFF to JPG, converted in your browser",
        "description": "Convert TIFF scans and images to JPG or PNG in your browser, including multi-page, 16-bit and "
                       "fax TIFFs. Nothing is uploaded. Free, no sign-up.",
        "hero": "Convert TIFF scans, microscope images and archive files to JPG, or to PNG. Multi-page TIFFs give one "
                "picture per page. Each file is decoded on your device, in this browser tab.",
        "accept": ".tif,.tiff,image/tiff",
        "drop": "Drop TIFF files here",
        "hint": "TIFF, up to 100 MB each. You can also paste a file with Ctrl or Cmd V.",
        "outputs": [("jpg", "JPG"), ("png", "PNG")],
        "opts": ["output", "quality", "background",
                 ("radio", "tiffpages", "Pages", [("first", "First page"), ("all", "All pages, as a zip")])],
        "libs": ["pako", "utif"],
        "features": ["Convert TIFF files to JPG or PNG",
                     "Multi-page TIFFs, one picture per page",
                     "LZW, Deflate, PackBits, CCITT fax and JPEG compression",
                     "8 and 16-bit gray and color, palette and CMYK",
                     "Decoded in the browser; files are never uploaded"],
        "how": [
            "TIFF is the format of scanners, microscopes, archives and print shops. Only Safari opens it in a web page, "
            "and many upload forms refuse it. This page reads the TIFF itself: it walks the file's list of pages, "
            "decompresses each strip or tile, and turns the samples into pixels in a background worker.",
            "The LZW and fax decoders come from UTIF.js, an open-source TIFF library, and the Deflate one from pako, "
            "both served from this site and loaded when you add a TIFF that needs them. JPEG-compressed TIFFs are "
            "decoded by the browser's own JPEG decoder.",
            "16-bit images, common from microscopes and film scanners, are reduced to 8 bits for the JPG or PNG. "
            "Nothing is brightened, so a dim image stays dim; adjust it in Fiji or Photoshop first if it needs it. "
            "Scanner thumbnails stored inside the file are skipped, and the orientation the file records is applied.",
        ],
        "steps": [
            ("Pick the format and pages", "JPG for photos and scans you will share, PNG to keep every pixel. First page or All pages for a multi-page TIFF."),
            ("Add the TIFFs", "Drop the files on the box, click it to choose them, or paste one."),
            ("Wait for each row", "The row shows the pixel size, or the number of pages, and any notes."),
            ("Download", "Download each picture from its row, a multi-page TIFF as one zip, or everything with Download all as .zip."),
        ],
        "limits": [
            "Up to 100 MB a file, 40 megapixels a page (16.7 on a phone), and 500 pages at a time.",
            "BigTIFF files, floating-point samples, files with each color in a separate plane, and old-style JPEG "
            "compression are refused with a message that says so.",
            "16 bits per sample are reduced to 8; nothing is stretched or brightened.",
            "Layers, extra channels beyond alpha, and the TIFF's metadata are not copied over.",
            "Needs Chrome or Edge 69, Firefox 105 or Safari 16.4, or later.",
        ],
        "faq": [
            ("Are my files uploaded?",
             "No. The page reads each TIFF with your browser and converts it in a background worker in this tab. There "
             "is no server step. The meter under the drop zone counts the bytes the page and its worker send while they "
             "work, so you can check this yourself. The only things the page downloads are its own scripts and the "
             "TIFF decoder."),
            ("Does it handle multi-page TIFFs?",
             "Yes. Choose All pages and each page becomes its own JPG or PNG, numbered in a zip. With First page, the row "
             "says how many pages the file has. Small preview images that scanners store next to the real pages are skipped."),
            ("Why is my microscope image dark?",
             "Many cameras store 12 bits of data in a 16-bit TIFF, so the brightest pixel is far below the 16-bit maximum. "
             "Reduced to 8 bits, the picture looks dark. The page does not stretch it, so measurements are not changed "
             "silently; set the display range in Fiji or ImageJ and export from there if you need a brighter picture."),
            ("Which compressions work?",
             "Uncompressed, LZW, Deflate, PackBits, CCITT Group 3 and Group 4 (fax and black-and-white scans) and JPEG. "
             "A TIFF in a compression the page cannot read gets a message naming it."),
            ("Should I choose JPG or PNG?",
             "JPG for photos and color scans, where it is far smaller. PNG for black-and-white documents, line art and "
             "anything you will measure, since it keeps every pixel exactly."),
            ("Is it free?",
             "Yes. There is no account, no watermark and no limit beyond the file sizes above."),
        ],
        "related": [("/tools/png-to-jpg/", "PNG to JPG"), ("/tools/pdf-to-jpg/", "PDF to JPG"),
                    ("/tools/jpg-to-pdf/", "JPG to PDF"), ("/tools/heic-to-jpg/", "HEIC to JPG")],
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
         "applicationCategory": p.get("category", "MultimediaApplication"), "operatingSystem": "Any",
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


def option_html(p: dict, spec) -> str:
    """One control. "output", "quality" and "background" are the image options; tuples describe the others:
    ("radio", key, label, [(value, text)], show) with the first value checked, ("check", key, label, default, show),
    ("select", key, label, [(value, text)], show), ("text", key, label, placeholder, show, hint, nostore) and
    ("number", key, label, (default, min, max), show). show is "key=a,b" or None."""
    if spec == "output":
        spec = ("radio", "output", "Save as", p["outputs"], None)
    if spec == "quality":
        return ('<label class="cv-field" data-show-when="output=jpg">JPEG quality <input type="range" id="cv-quality" '
                'data-opt="quality" min="50" max="100" step="1" value="92"> '
                '<output id="cv-quality-out" for="cv-quality">92</output></label>')
    if spec == "background":
        return ('<label class="cv-field" data-show-when="output=jpg">Fill transparent areas with '
                '<input type="color" id="cv-bg" data-opt="background" value="#ffffff"></label>')
    kind, key, label = spec[0], spec[1], spec[2]
    show = spec[4] if len(spec) > 4 else None
    when = f' data-show-when="{show}"' if show else ""
    if kind == "radio":
        loc = spec[5] if len(spec) > 5 else {}
        radios = "".join(
            f'<label><input type="radio" name="cv-{key}" data-opt="{key}" value="{v}"{" checked" if i == 0 else ""}'
            + (f' data-default-locale="{loc[v]}"' if v in loc else "") + f"> {e(lab)}</label>"
            for i, (v, lab) in enumerate(spec[3]))
        return (f'<div class="cv-field"{when}><span id="cv-{key}-label">{e(label)}</span>'
                f'<span class="cv-choice" role="radiogroup" aria-labelledby="cv-{key}-label">{radios}</span></div>')
    if kind == "check":
        return (f'<label class="cv-field"{when}><input type="checkbox" id="cv-{key}" data-opt="{key}"'
                f'{" checked" if spec[3] else ""}> {e(label)}</label>')
    if kind == "text":
        hint = spec[5] if len(spec) > 5 else ""
        nostore = " data-nostore" if len(spec) > 6 and spec[6] else ""
        described = f' aria-describedby="cv-{key}-hint"' if hint else ""
        hint_html = f' <span class="cv-hint" id="cv-{key}-hint">{e(hint)}</span>' if hint else ""
        return (f'<label class="cv-field cv-text"{when}>{e(label)} <input type="text" id="cv-{key}" data-opt="{key}"'
                f' placeholder="{e(spec[3])}" autocomplete="off" spellcheck="false" inputmode="text"{described}{nostore}>'
                f'</label>{hint_html}')
    if kind == "number":
        default, lo, hi = spec[3]
        return (f'<label class="cv-field"{when}>{e(label)} <input type="number" id="cv-{key}" data-opt="{key}"'
                f' value="{default}" min="{lo}" max="{hi}" step="1" inputmode="numeric"></label>')
    if kind == "select":
        opts = "".join(f'<option value="{v}">{e(lab)}</option>' for v, lab in spec[3])
        return f'<label class="cv-field"{when}>{e(label)} <select id="cv-{key}" data-opt="{key}">{opts}</select></label>'
    raise ValueError(spec)


def options_html(p: dict) -> str:
    rows = [option_html(p, o) for o in p.get("opts", []) if not (o == "output" and len(p["outputs"]) < 2)]
    if not rows:
        return ""
    if len(p["outputs"]) < 2:
        # The quality and fill controls show only while output=jpg, so a page with one output still names it.
        rows.insert(0, f'<input type="hidden" data-opt="output" value="{p["outputs"][0][0]}">')
    return ('        <fieldset class="cv-opts">\n          <legend>Options</legend>\n          '
            + "\n          ".join(rows) + "\n        </fieldset>\n")


def one_html(p: dict) -> str:
    if not p.get("combine"):
        return ""
    return '          <button type="button" class="btn btn-primary" id="cv-one" hidden>Download as one PDF</button>\n'


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
{one_html(p)}          <button type="button" class="btn btn-primary" id="cv-all" hidden>Download all as .zip</button>
          <button type="button" class="btn btn-ghost" id="cv-clear">Clear</button>
        </div>
        <p class="tool-privacy">{e(p.get("privacy", PRIVACY))}</p>
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


PRIVACY = ("Files are read and converted in this tab, in a background worker. The only requests the page makes are for "
           "its own scripts. Your files are never sent anywhere.")
PDFJS = "/assets/vendor/pdfjs-6.4.299/"
UTIF = "/assets/vendor/utif-3.1.0/"
LIBS = {"pdf": "/assets/vendor/pdf-lib.min.js", "pdfjs": PDFJS + "pdf.min.mjs", "pdfjs-worker": PDFJS + "pdf.worker.min.mjs",
        "pako": UTIF + "pako_inflate.min.js", "utif": UTIF + "UTIF.js"}


def libs_html(p: dict) -> str:
    """Libraries the worker loads with importScripts, or the page with import(). A .js link gets a ?v= stamp from
    fingerprint_assets.py, which the page hands to the worker; JSZip is already on every page as a script tag. The
    pdf.js .mjs files are not stamped (the script stamps .js and .css only): their folder carries the version."""
    return "".join(f'    <link rel="prefetch" as="script" data-convert-lib="{k}" href="{LIBS[k]}">\n' for k in p.get("libs", []))


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
{libs_html(p)}    <script src="/tools/convert/convert-core.js" defer></script>
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
