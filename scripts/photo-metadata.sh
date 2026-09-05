#!/usr/bin/env bash
# Photo licensing pipeline — embed IPTC/XMP metadata into images from a CSV.
#
# Stock platforms (Adobe Stock, Shutterstock, Alamy, Dreamstime, ...) auto-fill
# title/description/keywords from embedded IPTC on upload, so metadata is
# written once here and every platform reads it.
#
# Usage:
#   scripts/photo-metadata.sh embed <metadata.csv> <photos-dir>
#   scripts/photo-metadata.sh check <photos-dir>
#   scripts/photo-metadata.sh export <photos-dir> <out.csv>
#
# metadata.csv columns (header required):
#   filename,title,description,keywords
# keywords are semicolon-separated inside the one CSV field, most important
# first (platforms weight the first ~10).
set -euo pipefail

CREATOR="Benjamin Ampel"
COPYRIGHT="© $(date +%Y) Purplelink LLC. All rights reserved."
CREDIT="Purplelink LLC"

need_exiftool() {
  command -v exiftool >/dev/null || { echo "exiftool not found — brew install exiftool" >&2; exit 1; }
}

cmd="${1:-}"; shift || true
case "$cmd" in
  embed)
    need_exiftool
    csv="$1"; dir="$2"
    # exiftool's -csv mode matches rows to files by the SourceFile column;
    # build a temp CSV with the columns mapped to real tag names.
    tmp="$(mktemp)"
    awk -F',' 'NR==1{print "SourceFile,ObjectName,Caption-Abstract,Keywords,Title,Description,Subject"; next}' "$csv" > "$tmp"
    # Proper CSV parsing (quoted fields with commas) via python3:
    python3 - "$csv" "$dir" "$tmp" <<'PY'
import csv, sys, os
src, photodir, out = sys.argv[1], sys.argv[2], sys.argv[3]
with open(src, newline='') as f, open(out, 'w', newline='') as o:
    r = csv.DictReader(f)
    w = csv.writer(o)
    w.writerow(["SourceFile","ObjectName","Caption-Abstract","Keywords",
                "Title","Description","Subject"])
    for row in r:
        path = os.path.join(photodir, row["filename"])
        if not os.path.exists(path):
            print(f"WARN missing file: {path}", file=sys.stderr); continue
        kw = row["keywords"].replace(";", ", ")
        w.writerow([path, row["title"], row["description"], kw,
                    row["title"], row["description"], kw])
PY
    # -sep splits the comma-joined keyword string into SEPARATE list entries.
    # Without it, IPTC:Keywords (IIM) stores one blob and silently truncates at
    # 64 chars per entry — which is the field most stock/POD sites actually read.
    exiftool -sep ", " -csv="$tmp" -overwrite_original \
      -IPTC:By-line="$CREATOR" -IPTC:CopyrightNotice="$COPYRIGHT" -IPTC:Credit="$CREDIT" \
      -XMP-dc:Creator="$CREATOR" -XMP-dc:Rights="$COPYRIGHT" \
      "$dir"
    rm -f "$tmp"
    ;;
  check)
    need_exiftool
    exiftool -ext jpg -ext jpeg -ext tif -ext tiff -ext png \
      -T -FileName -ObjectName -Caption-Abstract -Keywords -CopyrightNotice "$1"
    ;;
  export)
    need_exiftool
    exiftool -ext jpg -ext jpeg -ext tif -ext tiff -ext png \
      -csv -FileName -ObjectName -Caption-Abstract -Keywords -ImageWidth -ImageHeight "$1" > "$2"
    echo "wrote $2"
    ;;
  *)
    grep '^#' "$0" | sed 's/^# \{0,1\}//' | head -16
    exit 1
    ;;
esac
