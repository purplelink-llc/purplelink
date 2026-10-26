// Shared by the haea plans (haeahowto.js long, haeashort.js Short): simulator screenshots of the app with demo data
// in assets/haea/ (iPhone 17 Pro Max, 1320x2868), and the boxes the camera and rings use, in screenshot pixels [x, y, w, h].
// Same camera presets as the Watchlight plans (same device size).

const files = ["terms", "today", "strength", "running", "route", "insights", "coach"];

export const haeaMedia = {
  "haea-icon.png": "assets/haea/icon-1024.png",
  ...Object.fromEntries(files.map((f) => [`haea-${f}.jpg`, `assets/haea/${f}.jpg`])),
};

export const IMG = Object.fromEntries(files.map((f) => [f, { src: `media/haea-${f}.jpg`, w: 1320, h: 2868 }]));

export const WL = {
  wide: [0.29, 0.44],
  zoom: [0.56, 0.66],
  ax: { wide: [0.62, 0.5], zoom: [0.7, 0.5] },
  ay: { wide: [0.5, 0.36], zoom: [0.46, 0.34] },
};

export const mid = (r) => [r[0] + r[2] / 2, r[1] + r[3] / 2];

export const R = {
  terms: { notMedical: [60, 804, 1200, 921] },
  today: {
    briefing: [57, 566, 1204, 512],
    ring: [1003, 609, 215, 266],
    action: [60, 917, 1200, 150],
    warning: [60, 1139, 1200, 251],
    tiles: [60, 1450, 1200, 941],
  },
  strength: {
    start: [102, 834, 1116, 168],
    summary: [51, 555, 1218, 495],
    level: [51, 1596, 1218, 690],
    volume: [51, 2340, 1218, 480],
  },
  running: {
    allTime: [48, 554, 1224, 320],
    week: [48, 931, 1224, 1128],
    suggested: [48, 1228, 1224, 812],
    load: [48, 2119, 1224, 700],
  },
  route: {
    path: [90, 945, 660, 600],
    bar: [36, 2304, 1260, 441],
    distance: [84, 2370, 300, 70],
    follow: [900, 2424, 345, 90],
  },
  insights: {
    picker: [60, 570, 1158, 291],
    chart: [60, 915, 1158, 1005],
    test: [102, 1704, 396, 87],
    drivers: [60, 1974, 1158, 606],
  },
  coach: { chips: [309, 1125, 771, 510], ask: [45, 2454, 1125, 132] },
};
