export const DESK = { W: 1280, H: 800, BAR: 34 };
export const MENU = [
  { t: "Panely: Trial: 5 days left", dim: true },
  { sep: true },
  { t: "Halves", sub: true }, { t: "Quarters", sub: true }, { t: "Thirds", sub: true }, { t: "Fourths (wide screens)", sub: true }, { t: "Sixths", sub: true }, { t: "Size and display", sub: true },
  { sep: true },
  { t: "Layouts", sub: true }, { t: "Custom areas", sub: true },
  { sep: true },
  { t: "Never move windows of Callroom", id: "ignore" },
  { t: "Settings…" }, { t: "Check for Updates…" }, { t: "Quit Panely" },
];
export const MENU_ROW = 30;
export const MENU_W = 372;

// y of the "Never move windows of" row inside the desk (for rings)
export function ignoreRowRect() {
  let y = DESK.BAR + 4 + 8;
  for (const it of MENU) {
    if (it.sep) y += 11;
    else { if (it.id === "ignore") return [DESK.W - 18 - MENU_W + 8, y, MENU_W - 16, MENU_ROW]; y += MENU_ROW; }
  }
  return [0, 0, 0, 0];
}


export function menuHeight() {
  const rows = MENU.filter((i) => !i.sep).length;
  const seps = MENU.filter((i) => i.sep).length;
  return rows * MENU_ROW + seps * 11 + 16;
}
