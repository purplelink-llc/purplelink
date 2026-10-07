// Bumper timing shared by the compositions and the Node build scripts (no JSX here).
export const BUMPER = { open: 2.2, close: 2.5, xf: 0.4 };
export const BUMPER_BG = "oklch(98.5% 0.007 310)";
// Total composition length once a product cut of `total` seconds sits between the two bumpers.
export function bumperTotal(total, b = BUMPER) {
  return b.open - b.xf + total - b.xf + b.close;
}
