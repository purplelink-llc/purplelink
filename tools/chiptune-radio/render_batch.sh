#!/bin/bash
# One finished long-form video and everything around it: the render, the thumbnail, the upload metadata, and the check (ffprobe, loudness, silence, four frames).
#   ./render_batch.sh campfire-2h campfire 2
#   ./render_batch.sh campfire-ambience-1h campfire 1 --no-music
#   ./render_batch.sh study-pomodoro-2h study 2 --pomodoro 25/5
# Output goes outside the repo, in $AMBIENT_OUT (default /Volumes/Extreme SSD/PurplelinkVideos/ambient). Run at most two of these at once.
set -u
[ $# -ge 3 ] || { echo "usage: $0 SLUG THEME HOURS [longform.py options]"; exit 2; }
slug=$1; theme=$2; hours=$3; shift 3
root=${AMBIENT_OUT:-/Volumes/Extreme\ SSD/PurplelinkVideos/ambient}
root=${root//\\/}
here=$(cd "$(dirname "$0")" && pwd)
py=${PYTHON:-/Library/Frameworks/Python.framework/Versions/3.12/bin/python3}
[ -n "$slug" ] || exit 2
dir="$root/$slug"
mkdir -p "$dir" || exit 1
cd "$here" || exit 1
if [ ! -f "$dir/$slug.mp4" ]; then
  nice -n 10 "$py" longform.py --theme "$theme" --hours "$hours" --out "$dir/$slug.mp4" "$@" >> "$dir/render.log" 2>&1 || { echo "render failed, see $dir/render.log"; exit 1; }
fi
pub_args=(--theme "$theme" --hours "$hours")
skip=0
for x in "$@"; do                      # longform_pub.py takes the scene options, not the render-only ones (--workers N)
  if [ "$skip" = 1 ]; then skip=0; continue; fi
  case "$x" in --video-loop|--workers) skip=1; continue ;; esac
  pub_args+=("$x")
done
nice -n 10 "$py" longform_pub.py thumb "${pub_args[@]}" --out "$dir/$slug-thumb.jpg" >> "$dir/render.log" 2>&1
nice -n 10 "$py" longform_pub.py meta "${pub_args[@]}" --slug "$slug" --out "$dir/$slug.json" >> "$dir/render.log" 2>&1
loop_file=$(ls "$dir/$slug"-loop*min.mp4 2>/dev/null | head -1)
if [ -n "$loop_file" ]; then
  # the long file is the verified loop repeated: check the loop's loudness and silence in full, the long file's format, length and frames
  nice -n 10 "$py" longform_pub.py verify --video "$loop_file" --out "$dir/$slug-loop-verify.json" > /dev/null 2>> "$dir/render.log" || exit 1
  nice -n 10 "$py" longform_pub.py verify --quick --video "$dir/$slug.mp4" --frames-dir "$dir" --out "$dir/$slug-verify.json" > /dev/null 2>> "$dir/render.log"
else
  nice -n 10 "$py" longform_pub.py verify --video "$dir/$slug.mp4" --frames-dir "$dir" --out "$dir/$slug-verify.json" > /dev/null 2>> "$dir/render.log"
fi
echo "$slug done"
