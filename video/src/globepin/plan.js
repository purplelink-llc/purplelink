// Edit plan for the GlobePin preview (frames at 30 fps). Shot clips come from globepin/cut.py; each plays
// `dur` frames plus the XF cross-fade into the next, so its clip must hold at least dur + XF frames.
export const XF = 8;

const CUT = [
  // id, frames on screen, optional slow push-in and its origin
  ["globe", 96],
  ["empty", 45],
  ["scan", 34],
  ["list", 96, 1.05, "50% 45%"],
  ["done", 40],
  ["pins", 52],
  ["timeline", 96],
  ["stats", 96, 1.05, "50% 30%"],
  ["place", 79],
  ["goals", 69],
  ["reel", 87],
  ["end", 90],
];

let at = 0;
export const SHOTS = CUT.map(([id, dur, zoom, origin]) => {
  const s = { id, src: `clips/${id}.mp4`, from: at, dur, zoom, origin };
  at += dur;
  return s;
});
export const TOTAL = at;

const span = (a, b) => {
  const s = SHOTS.find((x) => x.id === a), e = SHOTS.find((x) => x.id === b);
  return { from: s.from, to: e.from + e.dur + (b === "end" ? 0 : XF / 2) };
};

// `hot` words take the app's orange.
export const CAPTIONS = [
  { ...span("globe", "globe"), text: "Every place you've been", hot: ["Every", "place"] },
  { ...span("empty", "done"), text: "Built from your photos", sub: "Trips, flights and drives found for you", hot: ["photos"] },
  { ...span("pins", "timeline"), text: "Replay every trip", hot: ["every", "trip"] },
  { ...span("stats", "stats"), text: "Your travel in numbers", hot: ["numbers"] },
  { ...span("place", "place"), text: "Nights, miles and notes for each place", hot: ["each", "place"] },
  { ...span("goals", "goals"), text: "Pick where you go next", hot: ["next"] },
  { ...span("reel", "reel"), text: "Turn your travels into a reel", hot: ["reel"] },
  { ...span("end", "end"), text: "GlobePin", sub: "Your private travel map, in your iCloud", icon: true, hot: ["GlobePin"] },
];
