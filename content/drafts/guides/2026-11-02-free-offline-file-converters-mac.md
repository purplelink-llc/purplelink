# Free Offline File Converters for Mac, by Job

By Benjamin Ampel · November 2, 2026

Status: listed at the AKA launch (indexable, linked from the guides index and the sitemap).

Most file conversions on a Mac need no upload and no paid app. macOS converts images, audio, video, text documents and archives with built-in tools, and a few free Purplelink browser tools handle the rest inside the tab. This guide goes job by job: the free built-in way first, then the matching browser tool where one exists, then free open-source apps.

## How this guide was checked

I ran every command below on a Mac running macOS 27.0.1 on November 2, 2026, with files I made for the test. Menu paths such as File, Export are from Apple's documentation and my own use of these apps, and menu names shift between macOS releases, so treat them as a starting point. Where a command did not do what people expect, I say so. Purplelink makes the browser tools named here, and I describe their limits as their own pages state them.

## Which Purplelink tools stay in your browser

Five tools run in the browser tab and send nothing: HEIC to JPG, WebP to PNG, PNG to ICNS, Metadata Cleaner, and the merge and split tabs of PDF Tools. The first four show a counter, "Bytes of your files sent anywhere", that you can watch stay at 0.

Three others do send the file to a Purplelink server, which converts it and deletes it when the request ends: PDF Tools' compress tab (PDFs up to 20 MB), File to Markdown (up to 20 MB) and Markdown to PDF (up to 2 MB). They are listed below with that label, because a guide about not uploading should not blur the line.

## Images

### HEIC to JPG

To convert HEIC to JPG on a Mac without uploading, open the photo in Preview and choose File, Export, then set the format to JPEG. For many photos, select them in Finder, right-click, and choose Quick Actions, Convert Image, which offers JPEG, PNG or HEIF and a size. In Terminal, `sips` does the same for a whole folder:

```
mkdir converted
sips -s format jpeg -s formatOptions 85 *.[hH][eE][iI][cC] --out converted/
```

`formatOptions` takes low, normal, high, best or a percentage. I ran this on a lowercase and an uppercase file name and both were converted. The bracket pattern matters, because iPhone files often end in `.HEIC`.

The free browser version is [HEIC to JPG](https://purplelink.llc/tools/heic-to-jpg/). It decodes each photo in a background worker, takes up to 100 MB a file and 200 files a batch, and returns a zip. It writes JPG or PNG without the EXIF block, so the date taken and location are not carried over, and it drops Live Photo motion and HDR data. It is mainly useful on Windows or a Chromebook, or when you want the location gone. Among free apps, ImageMagick (`magick photo.heic photo.jpg`) reads HEIC when it was built with HEIF support.

### WebP to PNG

macOS can open WebP but cannot save it. `sips --formats` lists WebP as readable and not writable, and `sips` converts a WebP to PNG in one line:

```
sips -s format png picture.webp --out picture.png
```

Preview also opens WebP, then File, Export saves it in a format Preview can write. The browser tool [WebP to PNG](https://purplelink.llc/tools/webp-to-png/) does the same for batches, keeps transparency in PNG, can fill it for JPG, and turns an animated WebP into a still of its first frame. It is useful for pdfLaTeX and older Word, which do not take WebP. ImageMagick converts it too: `magick picture.webp picture.png`.

### Resize an image

In Preview, choose Tools, Adjust Size. In Terminal, `sips -Z 1600 photo.jpg --out smaller.jpg` scales the longest side to 1600 pixels and keeps the proportions; I checked it with a 640 pixel image and a 320 limit. `sips -z height width` sets both sides, which can stretch the picture. Purplelink has no resize tool. ImageMagick: `magick photo.jpg -resize 1600x smaller.jpg`.

### Remove location from a photo

To remove the location from one photo, open it in Preview, choose Tools, Show Inspector, open the GPS tab and click Remove Location Info. When sharing from Photos, the Options button on the share sheet has a Location switch.

Do not rely on `sips` for this. In my test, `sips -d all` left the GPS latitude in a JPEG, and converting that JPEG to PNG with `sips` copied it across. [Metadata Cleaner](https://purplelink.llc/tools/metadata-cleaner/) removes EXIF, GPS, XMP and IPTC from photos in the tab without re-encoding the pixels, and it also cleans PDF, Word, Excel, PowerPoint and MP4 or MOV video. The open-source ExifTool does it from Terminal, and I confirmed that `exiftool -gps:all= -overwrite_original photo.jpg` removes only the GPS tags, while `exiftool -all= -overwrite_original photo.jpg` removes all metadata. For manuscripts see [how to remove PDF metadata before double-blind review](https://purplelink.llc/guides/remove-pdf-metadata-before-double-blind-review/).

### PNG to ICNS for Mac icons

Apple's own route is an iconset folder and `iconutil`. Start from a square 1024 pixel PNG:

```
mkdir MyIcon.iconset
for s in 16 32 128 256 512; do
  sips -z $s $s icon.png --out MyIcon.iconset/icon_${s}x${s}.png
  sips -z $((s*2)) $((s*2)) icon.png --out MyIcon.iconset/icon_${s}x${s}@2x.png
done
iconutil -c icns MyIcon.iconset
```

That writes `MyIcon.icns` next to the folder. One trap: `sips -s format icns` is listed as writable, but on this Mac it failed with error 13, so use the iconset route. [PNG to ICNS](https://purplelink.llc/tools/png-to-icns/) builds the same ten sizes, 16 to 1024 pixels, in the browser and can include the `.iconset` folder. It does not accept SVG.

## PDFs

### Merge PDFs

In Preview, open the first PDF, show thumbnails with View, Thumbnails, drag the second PDF file into the sidebar, then File, Export as PDF. For images, select them in Finder and use Quick Actions, Create PDF. macOS also carries a command-line joiner inside its Combine PDF Pages Automator action. Apple does not document it, so it may change, but it merged two PDFs into a two-page file here:

```
"/System/Library/Automator/Combine PDF Pages.action/Contents/MacOS/join" -o merged.pdf a.pdf b.pdf
```

[PDF Tools](https://purplelink.llc/tools/pdf-tools/) merges in the browser with nothing uploaded, in the order you list the files. Free command-line option: `qpdf --empty --pages a.pdf b.pdf -- merged.pdf`.

### Split a PDF

In Preview, show thumbnails, select the pages you want and drag them to the Desktop; they save as a new PDF. The PDF Tools split tab does it in the browser from a page list such as `1-3, 5, 8-10`. With qpdf: `qpdf in.pdf --pages . 1-3,5 -- out.pdf`.

### Compress a PDF

In Preview, choose File, Export, then Quartz Filter, Reduce File Size. That filter is on this Mac, and it often lowers image quality more than you want, so check the result. The PDF Tools compress tab offers four quality levels but uploads the file, kept only while it runs, so it is not an offline option. The offline open-source route is Ghostscript: `gs -sDEVICE=pdfwrite -dPDFSETTINGS=/ebook -o small.pdf in.pdf`, where `/screen`, `/ebook`, `/printer` and `/prepress` trade size for quality.

### Make a scanned PDF searchable

Preview's Live Text lets you select and copy words from a scan on screen, but I found no built-in way to save that text into the file. For a PDF that is itself searchable you need an OCR tool. Tesseract, which is open source, writes one directly, and I confirmed this command produces a PDF:

```
tesseract scan.png scan-searchable pdf
```

OCRmyPDF wraps Tesseract for whole PDFs: `ocrmypdf in.pdf out.pdf`. Purplelink's free tools do not do OCR. Its paid [Tapefolio](https://purplelink.llc/tapefolio/) app reads scanned pages on the Mac, free for 7 days.

## Video and audio

### MOV to MP4

In QuickTime Player, File, Export As offers 4K, 1080p, 720p and 480p, and the result is usually a `.mov`. To get an MP4 container from Terminal, use `avconvert`:

```
avconvert --source clip.mov --preset Preset1280x720 --output clip.mp4 --replace
```

I ran that and the output was an MP4 file. `avconvert --help` lists the presets: `Preset640x480`, `Preset960x540`, `Preset1280x720`, `Preset1920x1080`, `Preset3840x2160`, `PresetAppleM4A` and three `PresetAppleM4V` sizes. It re-encodes. Finder also has Quick Actions, Encode Selected Video Files. If the video is already H.264 with AAC audio, ffmpeg can rewrap it without re-encoding, which I confirmed: `ffmpeg -i clip.mov -c copy clip.mp4`. [HandBrake](https://handbrake.fr/) is the free graphical option, with presets and MP4 or MKV output. Purplelink has no browser video converter, because a browser-based encoder is a large download and slow on a laptop.

### Extract audio from a video

In QuickTime Player, File, Export As, Audio Only gives an M4A. In Terminal, `afconvert` writes M4A directly from a video file, and I confirmed both of these:

```
afconvert -f m4af -d aac clip.mp4 clip.m4a
avconvert --source clip.mov --preset PresetAppleM4A --output clip.m4a --replace
```

For an uncompressed WAV: `afconvert -f WAVE -d LEI16 clip.mp4 clip.wav`. **afconvert cannot write MP3.** Asking for `-f MPG3 -d .mp3` fails with `ExtAudioFileSetProperty ('cfmt') failed`, even though it can read MP3. For MP3, use ffmpeg: `ffmpeg -i clip.mp4 -vn -c:a libmp3lame -q:a 2 clip.mp3`, which worked here with the Homebrew build.

### Make a GIF

Finder has no GIF converter. The Shortcuts app includes a Make GIF action, which I did not test. ffmpeg works from Terminal, and this two-step palette version made a clean GIF here:

```
ffmpeg -i clip.mp4 -vf "fps=10,scale=320:-1:flags=lanczos,split[s0][s1];[s0]palettegen[p];[s1][p]paletteuse" clip.gif
```

Lower the frame rate and width to keep the file small; GIF is an inefficient format and the file grows quickly.

## Documents and Markdown

`textutil` converts text documents between txt, rtf, rtfd, html, doc, docx, odt, wordml and webarchive. I ran HTML to DOCX, DOCX to TXT and HTML to RTF successfully:

```
textutil -convert docx page.html
textutil -convert txt report.docx -stdout
```

Two limits. `textutil` has no PDF output (it answers "Invalid output format"), and it reads a Markdown file as plain text, so asterisks stay asterisks. For a PDF, open the file in TextEdit, Pages or Word and choose File, Export as PDF, or use Print, Save as PDF.

For fully local conversion beyond that, LibreOffice does it headless (`soffice --headless --convert-to pdf report.docx`) and Pandoc handles Markdown (`pandoc notes.md -o notes.docx`); PDF output from Pandoc needs a LaTeX engine installed. Microsoft's open-source markitdown turns PDF, Word, PowerPoint and Excel into Markdown on your own machine. Purplelink's [File to Markdown](https://purplelink.llc/tools/file-to-markdown/) uses markitdown on its server, and [Markdown to PDF](https://purplelink.llc/tools/markdown-to-pdf/) uses Pandoc on its server; both upload the file and delete it afterwards. For research papers, see [turning a paper PDF into clean Markdown](https://purplelink.llc/guides/research-paper-pdf-to-markdown/).

## Fonts

macOS installs TTF and OTF fonts in Font Book but has no converter for web formats. The free open-source fontTools library does it, and I confirmed both directions on a system TTF:

```
pip install fonttools brotli
python3 -m fontTools ttLib.woff2 compress font.ttf
python3 -m fontTools ttLib.woff2 decompress font.woff2 -o font.ttf
```

Check the font's license before converting; some forbid web use or modification. Purplelink has no font tool.

## Archives

In Finder, right-click files and choose Compress to make a ZIP; double-click a ZIP to open it. In Terminal, `ditto` and `bsdtar` are both installed. I ran these:

```
ditto -c -k --keepParent project project.zip
ditto -x -k project.zip restored/
bsdtar -czf project.tgz project
bsdtar -tf project.zip
```

`ditto -c -k` writes the ZIP format Finder uses and keeps Mac file metadata. `bsdtar -tf` lists what is inside an archive without extracting it. For 7z and RAR, [Keka](https://www.keka.io/) is free from its developer's site, and the Mac App Store edition is paid. Purplelink has no archive tool.

## Audio to text

Voice Memos can show a transcript you copy out; the steps and what it leaves out are in [exporting a Voice Memos transcript](https://purplelink.llc/guides/export-voice-memos-transcript-mac/), and [free transcription on a Mac with no time limit](https://purplelink.llc/guides/free-audio-transcription-mac/) compares the free options. Open-source whisper.cpp runs on the Mac and wants 16 kHz mono WAV, which `afconvert` makes:

```
afconvert -f WAVE -d LEI16@16000 -c 1 interview.m4a interview.wav
```

I confirmed that command writes one channel at 16000 Hz. Purplelink's [Tapefolio](https://purplelink.llc/tapefolio/) transcribes on the Mac with speaker labels, free for 7 days, then paid.

## The whole list in one table

"Local" means the file stays on your Mac. "Uploads" means the file goes to a Purplelink server and is deleted after the run.

| Job | Built into macOS | Free Purplelink tool | Free app or command |
|---|---|---|---|
| HEIC to JPG | Preview Export, Convert Image, sips | HEIC to JPG (local) | ImageMagick |
| WebP to PNG | sips (reads WebP, cannot write it) | WebP to PNG (local) | ImageMagick |
| Resize an image | Preview Adjust Size, sips -Z | None | ImageMagick |
| Remove photo location | Preview Inspector, Photos share options | Metadata Cleaner (local) | ExifTool |
| PNG to ICNS | sips and iconutil | PNG to ICNS (local) | None needed |
| Merge PDFs | Preview thumbnails, Create PDF | PDF Tools (local) | qpdf |
| Split a PDF | Preview thumbnails | PDF Tools (local) | qpdf |
| Compress a PDF | Preview Quartz Filter | PDF Tools (uploads) | Ghostscript |
| Make a PDF searchable | Live Text selects text only | None | Tesseract, OCRmyPDF |
| MOV to MP4 | avconvert, QuickTime Export | None | HandBrake, ffmpeg |
| Video to audio | afconvert, avconvert, QuickTime | None | ffmpeg (for MP3) |
| Video to GIF | Shortcuts Make GIF (untested) | None | ffmpeg |
| Word, HTML, RTF, text | textutil, TextEdit | None | LibreOffice, Pandoc |
| To or from Markdown | textutil treats it as plain text | File to Markdown, Markdown to PDF (both upload) | Pandoc, markitdown |
| Fonts to WOFF2 | None | None | fontTools |
| Archives | Finder Compress, ditto, bsdtar | None | Keka |
| Audio to text | Voice Memos transcript | None | whisper.cpp, Tapefolio (paid) |

## AKA, a Mac app for these conversions

Purplelink makes a Mac app called [AKA](/aka/) that does many of the conversions above from one place. Hold Option while you drag files, and a ring of actions opens at the pointer; drop the files on one and the result is saved next to the original, converted on your Mac. AKA is available now: $14.99 once, after a free 7-day trial. Everything above still works without it.

## Questions

**Can a Mac convert HEIC to JPG without extra software?**
Yes. Open the photo in Preview and choose File, Export, JPEG, or run `sips -s format jpeg photo.heic --out photo.jpg` in Terminal. Finder's Quick Actions, Convert Image handles several photos at once.

**Can macOS save an image as WebP?**
No. On macOS 27.0.1, `sips --formats` lists WebP as readable but not writable. You can open a WebP and convert it to PNG or JPEG, but writing WebP needs another tool.

**Can afconvert make MP3 files?**
No. afconvert reads MP3 but fails when asked to write one. It writes M4A, WAV, AIFF and CAF, among others. Use ffmpeg with libmp3lame for MP3.

**Do Purplelink's converters upload my files?**
HEIC to JPG, WebP to PNG, PNG to ICNS, Metadata Cleaner and PDF merge and split run in your browser and upload nothing. PDF compress, File to Markdown and Markdown to PDF send the file to a Purplelink server, which deletes it after the conversion.

**Does converting a photo remove its location?**
Not reliably. In my test, sips copied the GPS tag when it converted a JPEG to PNG, and sips -d all did not remove it. Use Preview's Inspector, Metadata Cleaner or ExifTool, then check the result.

**How do I turn a MOV into an MP4 for free?**
Run `avconvert --source clip.mov --preset Preset1280x720 --output clip.mp4`, or use HandBrake. If the video is already H.264 with AAC, `ffmpeg -i clip.mov -c copy clip.mp4` changes the container without re-encoding.

**How do I merge or compress a PDF without uploading it?**
Merge in Preview by dragging a second PDF into the thumbnail sidebar, or with the PDF Tools merge tab, which runs in the browser. For compression, use Preview's Reduce File Size filter or Ghostscript, since the PDF Tools compress tab uploads the file.
