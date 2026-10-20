// Shared by the Watchlight plans (watchlight.js long, watchlightshort.js Short): the simulator screenshots of build
// 1.0 (14) in assets/watchlight/ (iPhone 17 Pro Max, 1320x2868, 3x of 440x956 points) and the boxes the camera and
// rings use, in screenshot pixels [x, y, w, h].

const files = ["home", "home2", "checking", "shot0", "res0b", "res0c", "clean1", "recov1", "setup1", "setup2", "setup3", "calls", "missing1", "unlock", "unlock2"];

export const wlMedia = {
  "watchlight-icon.png": "assets/watchlight/icon-1024.png",
  ...Object.fromEntries(files.map((f) => [`wl-${f}.jpg`, `assets/watchlight/${f}.jpg`])),
};

export const IMG = Object.fromEntries(files.map((f) => [f, { src: `media/wl-${f}.jpg`, w: 1320, h: 2868 }]));

// Camera presets: scale per format [16x9, 9x16] and where the focus point sits on screen.
// The 16:9 phone sits right of centre so the lower thirds (bottom left) never cover it.
export const WL = {
  wide: [0.29, 0.44],
  zoom: [0.56, 0.66],
  ax: { wide: [0.62, 0.5], zoom: [0.7, 0.5] },
  ay: { wide: [0.5, 0.36], zoom: [0.46, 0.34] },
};

export const mid = (r) => [r[0] + r[2] / 2, r[1] + r[3] / 2];

export const R = {
  home: {
    top: [57, 240, 1204, 780],
    card: [57, 549, 1204, 466],
    check: [62, 1080, 1196, 1180],
    paste: [530, 1467, 260, 119],
    chips: [122, 1906, 853, 287],
    tiles: [57, 2314, 1204, 337],
  },
  home2: { share: [60, 375, 1200, 630] },
  checking: { card: [57, 549, 1204, 1900] },
  shot0: {
    verdict: [62, 408, 1196, 734],
    reasons: [62, 1194, 1196, 1378],
    weights: [1075, 1390, 150, 803],
    bar: [110, 2320, 1100, 200],
  },
  res0b: { link: [60, 420, 1200, 1350], todo: [60, 1830, 1200, 1038] },
  res0c: {
    buttons: [60, 1300, 1200, 830],
    ask: [60, 1380, 1200, 165],
    report: [60, 1581, 1200, 165],
    already: [60, 1950, 1200, 165],
  },
  clean1: { green: [60, 411, 1200, 1140] },
  recov1: { tapped: [60, 780, 1200, 810] },
  setup1: { night: [60, 384, 1200, 525], filter: [60, 960, 1200, 1170], steps: [110, 1390, 1100, 490] },
  setup2: { safari: [60, 1104, 1200, 1251] },
  setup3: { report: [60, 684, 1200, 1095], family: [60, 2346, 1200, 384] },
  calls: { label: [60, 666, 1200, 684] },
  missing1: { intro: [60, 465, 1140, 231], find: [60, 750, 1200, 870] },
  unlock: { free: [60, 1440, 1200, 735] },
  unlock2: { adds: [60, 735, 1200, 975], button: [60, 1770, 1200, 165] },
};
