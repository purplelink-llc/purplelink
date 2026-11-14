"""Textures for the Publication suite film: the manuscript page, the response letter and the floating report cards.

Every word on screen is real typeset text taken from the sample-report excerpts on /publication-suite/, so nothing in
the film is generated pseudo-text. Writes PNGs plus layout.json (highlight rectangles in page UV space) to OUT.

    python3 tools/publication-film/make_textures.py OUT_DIR
"""

import io
import json
import math
import sys
from pathlib import Path

from fontTools.ttLib import TTFont
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
FONTS = ROOT / "site" / "assets" / "fonts"
SERIF = "/System/Library/Fonts/Supplemental/Times New Roman.ttf"
SERIF_B = "/System/Library/Fonts/Supplemental/Times New Roman Bold.ttf"
SERIF_I = "/System/Library/Fonts/Supplemental/Times New Roman Italic.ttf"


def oklch(l, c, h):
    """OKLCH to an sRGB 0-255 tuple (the site's colour tokens are written in OKLCH)."""
    a, b = c * math.cos(math.radians(h)), c * math.sin(math.radians(h))
    l_ = (l + 0.3963377774 * a + 0.2158037573 * b) ** 3
    m_ = (l - 0.1055613458 * a - 0.0638541728 * b) ** 3
    s_ = (l - 0.0894841775 * a - 1.2914855480 * b) ** 3
    rgb = (4.0767416621 * l_ - 3.3077115913 * m_ + 0.2309699292 * s_,
           -1.2684380046 * l_ + 2.6097574011 * m_ - 0.3413193965 * s_,
           -0.0041960863 * l_ - 0.7034186147 * m_ + 1.7076147010 * s_)

    def enc(x):
        x = min(max(x, 0.0), 1.0)
        return round(255 * (12.92 * x if x <= 0.0031308 else 1.055 * x ** (1 / 2.4) - 0.055))

    return tuple(enc(x) for x in rgb)


PANEL = oklch(0.24, 0.02, 310)
INK = oklch(0.95, 0.01, 310)
MUTED = oklch(0.74, 0.03, 300)
PURPLE = oklch(0.72, 0.17, 310)
LINE = oklch(0.36, 0.03, 310)
OK = oklch(0.72, 0.14, 150)
PART = oklch(0.80, 0.13, 85)
NO = oklch(0.65, 0.18, 25)
PAPER_INK = (34, 30, 38)


def woff2_font(name, size, weight=None):
    """Load a self-hosted woff2 (decompressed in memory), optionally pinning a variable-font weight."""
    tt = TTFont(FONTS / name)
    tt.flavor = None
    buf = io.BytesIO()
    tt.save(buf)
    buf.seek(0)
    font = ImageFont.truetype(buf, size)
    if weight is not None:
        try:
            font.set_variation_by_axes([weight] + ([] if len(font.get_variation_axes()) == 1 else
                                                   [a["default"] for a in font.get_variation_axes()[1:]]))
        except OSError:
            pass
    return font


def wrap(draw, text, font, width):
    words, lines, cur = text.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if draw.textlength(t, font=font) <= width:
            cur = t
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


# ---------------------------------------------------------------- manuscript page

PAGE_W, PAGE_H = 1700, 2200  # US Letter at 200 dpi
MARGIN = 190


def manuscript(out):
    """A journal-style manuscript page. Returns highlight rects (u0, v0, u1, v1 in 0..1, v from the top)."""
    img = Image.new("RGB", (PAGE_W, PAGE_H), (250, 248, 243))
    d = ImageDraw.Draw(img)
    body = ImageFont.truetype(SERIF, 34)
    bold = ImageFont.truetype(SERIF_B, 36)
    title = ImageFont.truetype(SERIF_B, 58)
    ital = ImageFont.truetype(SERIF_I, 32)
    w = PAGE_W - 2 * MARGIN
    lh = 48
    y = 210

    for line in wrap(d, "Tuned Baselines and the Illusion of Progress in Tabular Benchmarks", title, w):
        tw = d.textlength(line, font=title)
        d.text(((PAGE_W - tw) / 2, y), line, font=title, fill=PAPER_INK)
        y += 74
    y += 14
    sub = "Anonymous submission for double-blind review"
    d.text(((PAGE_W - d.textlength(sub, font=ital)) / 2, y), sub, font=ital, fill=(90, 84, 96))
    y += 92

    hl = []

    def para(chunks, indent=True):
        """chunks: list of (text, highlight_id or None). Lays out word by word and records highlight boxes."""
        nonlocal y
        x = MARGIN + (40 if indent else 0)
        boxes = {}
        for text, hid in chunks:
            for word in text.split():
                ww = d.textlength(word + " ", font=body)
                if x + d.textlength(word, font=body) > MARGIN + w:
                    x = MARGIN
                    y += lh
                d.text((x, y), word, font=body, fill=PAPER_INK)
                if hid is not None:
                    boxes.setdefault((hid, y), [x, x + d.textlength(word, font=body)])
                    boxes[(hid, y)][1] = x + d.textlength(word, font=body)
                x += ww
        y += lh + 18
        for (hid, ly), (x0, x1) in boxes.items():
            hl.append({"id": hid, "u0": (x0 - 6) / PAGE_W, "u1": (x1 + 6) / PAGE_W,
                       "v0": (ly - 4) / PAGE_H, "v1": (ly + 42) / PAGE_H})

    def heading(text):
        nonlocal y
        y += 10
        d.text((MARGIN, y), text, font=bold, fill=PAPER_INK)
        y += 64

    heading("Abstract")
    para([("Gradient-boosted trees remain strong on tabular data. We introduce a transformer that", None),
          ("beats all baselines by a wide margin", 3),
          ("on seven public benchmarks and reduces error by 40% relative to prior attention models.", None)],
         indent=False)
    heading("1  Introduction")
    para([("Recent work reports that attention models close the gap with tree ensembles on tabular tasks, although "
           "results depend on preprocessing and on how much tuning each model receives. Prior evidence shows that",
           None), ("Method X reduces error by 40% [14],", 2),
          ("which motivates a closer look at architectures that share its inductive bias.", None)])
    heading("3.2  Methods")
    para([("Each model is trained for 50 epochs with early stopping on a held-out split.", None),
          ("We tuned learning rate and batch size on the validation set; baselines used reported defaults.", 1),
          ("We then trained each model for 50 epochs and report the mean of five seeds.", None)])
    para([("Table 2 lists accuracy and standard errors for all seven datasets. Hyperparameter ranges and the "
           "search budget appear in Appendix B, and the code is available on request.", None)])
    heading("4  Results")
    para([("Our model ranks first on average across the benchmark suite. Gains are largest on the two datasets "
           "with the most categorical features, where the attention layers can share information across columns. "
           "We discuss the remaining datasets in Section 5.", None)])

    # A results table with real numbers (Table 2 of the example), so the page reads as a paper at a glance.
    y += 6
    cap = "Table 2. Accuracy (mean of five seeds, standard error in parentheses)."
    d.text((MARGIN, y), cap, font=ital, fill=PAPER_INK)
    y += 58
    small = ImageFont.truetype(SERIF, 30)
    cols = [MARGIN, MARGIN + 380, MARGIN + 700, MARGIN + 1000]
    rows = [("Dataset", "Ours", "Baseline C", "XGBoost"),
            ("adult", "0.872 (.003)", "0.869 (.004)", "0.871 (.002)"),
            ("covertype", "0.961 (.002)", "0.958 (.003)", "0.955 (.002)"),
            ("higgs", "0.781 (.004)", "0.779 (.004)", "0.776 (.003)"),
            ("jannis", "0.732 (.005)", "0.731 (.005)", "0.724 (.004)")]
    d.line([(MARGIN, y - 8), (MARGIN + w, y - 8)], fill=PAPER_INK, width=3)
    for i, row in enumerate(rows):
        for cx, cell in zip(cols, row):
            d.text((cx, y), cell, font=bold if i == 0 else small, fill=PAPER_INK)
        y += 46
        if i == 0:
            d.line([(MARGIN, y - 4), (MARGIN + w, y - 4)], fill=PAPER_INK, width=2)
    d.line([(MARGIN, y + 2), (MARGIN + w, y + 2)], fill=PAPER_INK, width=3)
    d.text(((PAGE_W - 40) / 2, PAGE_H - 140), "7", font=body, fill=(90, 84, 96))
    img.save(out / "page_manuscript.png")
    return hl


def letter(out):
    """The response letter: the page Response Review reads."""
    img = Image.new("RGB", (PAGE_W, PAGE_H), (250, 248, 243))
    d = ImageDraw.Draw(img)
    body = ImageFont.truetype(SERIF, 34)
    bold = ImageFont.truetype(SERIF_B, 36)
    title = ImageFont.truetype(SERIF_B, 54)
    w = PAGE_W - 2 * MARGIN
    y = 220
    d.text((MARGIN, y), "Response to the Reviewers", font=title, fill=PAPER_INK)
    y += 110
    items = [
        ("R1.2  Sample size.", "We added a power analysis to Section 3.2. With five seeds per dataset, the design "
         "detects a difference of 0.4 points at 80% power."),
        ("R1.4  Figure 3 labels.", "We enlarged the labels. The legend now sits below the plot."),
        ("R2.1  Comparison with Chen et al.", "We are aware of this work."),
        ("R1.5  Exclusion criteria.", ""),
        ("R2.3  Tuning budget.", "Every baseline now receives the same search budget of 60 trials, and Table 2 "
         "reports the tuned results."),
    ]
    for head, text in items:
        d.text((MARGIN, y), head, font=bold, fill=PAPER_INK)
        y += 56
        for line in wrap(d, text, body, w - 40) if text else []:
            d.text((MARGIN + 40, y), line, font=body, fill=PAPER_INK)
            y += 48
        y += 40
    img.save(out / "page_letter.png")


# ---------------------------------------------------------------- cards

CARD_SCALE = 2  # draw at 2x for crisp text when the camera pushes in


def rounded_card(size, radius):
    s = CARD_SCALE
    img = Image.new("RGBA", (size[0] * s, size[1] * s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, size[0] * s - 1, size[1] * s - 1], radius * s, fill=PANEL + (238,),
                        outline=LINE + (255,), width=2 * s)
    return img, d


def finding_card(out, name, grade, label, detail):
    s = CARD_SCALE
    img, d = rounded_card((760, 210), 26)
    jak_b = woff2_font("plus-jakarta-sans-latin.woff2", 34 * s)
    jak = woff2_font("plus-jakarta-sans-latin.woff2", 27 * s)
    chip = woff2_font("plus-jakarta-sans-latin.woff2", 28 * s)
    try:
        jak_b.set_variation_by_name("Bold")
        chip.set_variation_by_name("ExtraBold")
    except (OSError, ValueError):
        pass
    d.rounded_rectangle([34 * s, 36 * s, 86 * s, 88 * s], 12 * s, fill=PURPLE if grade == "A" else MUTED)
    gw = d.textlength(grade, font=chip)
    d.text((60 * s - gw / 2, 43 * s), grade, font=chip, fill=PANEL)
    d.text((110 * s, 42 * s), label, font=jak_b, fill=INK)
    for i, line in enumerate(wrap(d, detail, jak, 620 * s)[:2]):
        d.text((110 * s, (100 + i * 40) * s), line, font=jak, fill=MUTED)
    img.save(out / f"card_{name}.png")


def tracker_card(out, name, heading, rows):
    s = CARD_SCALE
    h = 110 + 74 * len(rows)
    img, d = rounded_card((760, h), 26)
    jak_b = woff2_font("plus-jakarta-sans-latin.woff2", 30 * s)
    jak = woff2_font("plus-jakarta-sans-latin.woff2", 27 * s)
    pill = woff2_font("plus-jakarta-sans-latin.woff2", 23 * s)
    try:
        jak_b.set_variation_by_name("Bold")
        pill.set_variation_by_name("Bold")
    except (OSError, ValueError):
        pass
    d.text((34 * s, 34 * s), heading, font=jak_b, fill=INK)
    y = 100
    for status, colour, text in rows:
        pw = d.textlength(status, font=pill) + 32 * s
        tint = tuple(round(c * 0.22 + p * 0.78) for c, p in zip(colour, PANEL))
        d.rounded_rectangle([34 * s, (y + 6) * s, 34 * s + pw, (y + 50) * s], 22 * s, fill=tint,
                            outline=colour, width=2 * s)
        d.text((50 * s, (y + 13) * s), status, font=pill, fill=INK)
        d.text((34 * s + pw + 20 * s, (y + 11) * s), text, font=jak, fill=MUTED)
        y += 74
    img.save(out / f"card_{name}.png")


def main():
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    hl = manuscript(out)
    letter(out)
    finding_card(out, "f1", "A", "Hyperparameter search asymmetry",
                 "Only the proposed method was tuned. Match the search budget for each baseline.")
    finding_card(out, "f2", "A", "Citation contradicted",
                 "Reference [14] reports a 4% reduction, not 40%.")
    finding_card(out, "f3", "B", "Data and claim disagree",
                 "Table 2 shows a tie with Baseline C within standard errors.")
    tracker_card(out, "revision", "Revision Review", [
        ("Addressed", OK, "Same tuning budget for every baseline"),
        ("Partly", PART, "Results say 4%, the abstract still says 40%"),
        ("Not addressed", NO, "Reference [17] has the wrong DOI")])
    tracker_card(out, "response", "Response Review", [
        ("Addressed", OK, "R1.2  Power analysis added"),
        ("Partly", PART, "R1.4  Legend still overlaps"),
        ("Hand-waved", PART, "R2.1  No comparison given"),
        ("Missing", NO, "R1.5  No reply in the letter")])
    (out / "layout.json").write_text(json.dumps({"page": [PAGE_W, PAGE_H], "highlights": hl}, indent=1))
    print(f"wrote textures and {len(hl)} highlight boxes to {out}")


if __name__ == "__main__":
    main()
