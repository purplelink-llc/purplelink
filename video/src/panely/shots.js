// Still frames of the schematic desk (for the product page and the video poster). Each shot: a desk spec and a time.
import { deskDrag, deskLayouts, deskIgnore } from "./desk.js";

const lay = (name) => deskLayouts([[name, 0]], { floatStart: false });
const DRAG = { shortcut: 0.2, drag1: 2.0, drag2: 6 };
const IGN = { open: 0.5, hover: 1.3, check: 1.8, close: 3.5, k1: 4.2, k2: 5.2 };

export const SHOTS = {
  "layout-halves": { spec: () => lay("halves"), t: 1 },
  "layout-thirds": { spec: () => lay("thirds"), t: 1 },
  "layout-quarters": { spec: () => lay("quarters"), t: 1 },
  "layout-sixths": { spec: () => lay("sixths"), t: 1 },
  "layout-custom-area": { spec: () => lay("area"), t: 2 },
  "drag-to-corner": { spec: () => deskDrag(DRAG), t: 2.78 },
  "shortcut-snap": { spec: () => deskDrag(DRAG), t: 1.0 },
  "ignored-app-menu": { spec: () => deskIgnore(IGN), t: 2.4 },
};
