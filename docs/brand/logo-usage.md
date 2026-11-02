# Purplelink logo: which version goes where, and why

The design log for the 2026-10 identity. The visual companion is the art book (`docs/brand/art-book.html`).
When a new surface needs a logo, decide it here first and add a row to the table.

## The pieces

**The rule (Ben, 2026-10-30): the striped mark always accompanies wordmark B.** Stacked (mark above) in large and hero spots: press,
covers, a credits end, cards. Side by side (mark left) in small and signature spots: site header, site and game footers, app About
windows, game boot splash. The mark alone stays for small square uses: favicon, app and social avatars, the site footer icon.

| Piece | Files | What it is |
|---|---|---|
| **Primary logo (stacked lockup)** | `site/assets/purplelink-lockup-dark.svg` / `-light.svg`, `.png` copies | The striped mark with wordmark B ("purplelink / software company") centred beneath it. **This is the main logo.** |
| **Side-by-side lockup** | `site/assets/purplelink-lockup-horizontal-dark.svg` / `-light.svg`, `.png` copies (2175 x 448) | The striped mark left of wordmark B at the same height. The signature version for small spots. Supplied as final artwork; copy exactly. |
| **Mark** | `site/assets/purplelink-mark.svg`, `purplelink-logo.png` (512), `purplelink-logo-64.png` | The striped P-L monogram alone, gradient fill. |
| **Single-colour mark** | `site/assets/purplelink-logo-v2.png` | The mark in flat brand purple `rgb(140,22,197)` (light-theme `--purple`), for places that cannot show a gradient. |
| **Wordmark B only** | `site/assets/purplelink-wordmark-dark.svg` / `-light.svg`, `.png` copies (1563 x 448) | "purplelink / software company" with no mark: ink text plus a purple underline swoosh and star. Used inside the lockups and as the header masks; do not use it without the mark. Ink hex fills (`#f0edf4` on dark, `#12001e` on light) and an accent gradient of `#c07af1` to `#9222cc`, so native renderers that do not know OKLCH draw it correctly. |
| **Wordmark masks** | `site/assets/purplelink-wordmark-text-mask.svg`, `purplelink-wordmark-accent-mask.svg` (same 1563 x 448 box, black shapes) | The two layers of B, split for CSS masks. Used only by the site header. |

Wordmark B is Ben's own artwork, never re-typeset in a site font. It replaced the earlier "purplelink / softwares"
wordmark on 2026-10-30.

**What it means.** A hyperlink turns purple once you have clicked it. The swoosh under "purplelink" is the link's
underline; the star at its end is the click. That is why the text is ink and only the swoosh and star are purple.

## Colour

- Mark: vertical gradient `oklch(70% 0.18 310)` at the top to `oklch(52% 0.24 310)` at the bottom (hue 310 is the
  site's purple). Chosen so the mark keeps contrast on both the dark default theme and the light theme.
- Wordmark text: the site's `--ink` for the background it sits on. Dark backgrounds: `oklch(95% 0.01 310)` / `#f0edf4` (the
  `-dark` files). Light backgrounds: `oklch(14% 0.07 310)` / `#12001e` (the `-light` files). Never purple.
- Wordmark swoosh and star: horizontal gradient, left to right, `oklch(70% 0.18 310)` / `#c07af1` to
  `oklch(52% 0.24 310)` / `#9222cc`, the same two purples as the mark.

## Where each one is used

| Surface | Piece | Why |
|---|---|---|
| Generic social cards (`site/assets/og/brand.png`, `purplelink-card.png`) | Primary logo | The card is about the company, at 1200x630 there is room for the wordmark to read, and a shared link should carry the full name. |
| Press kit downloads (`/press/`) | Stacked lockup first, then the side-by-side lockup, then mark-only files | Journalists should reach for the full logo by default; the side-by-side files fit wide, short spaces; the mark-only files are for avatars and tight spaces. |
| Site header (30 px) | Side-by-side lockup, built from CSS: mark plus wordmark B | B is drawn from two CSS masks in `site/styles.css` (`.brand > span`): `::before` is the text mask filled with `currentColor` (so it follows the theme), `::after` is the accent mask filled with the gradient (oklch, hex fallback). The box is 105 x 30 px (1563:448). The name stays in the markup as hidden text for screen readers and search. |
| Site footer icon (26 px) | Mark | Square icon beside the text "Purplelink LLC". A footer signature line uses the side-by-side lockup. |
| Homepage hero stage mark (88 px) | Mark alone for now; a hero spot that carries the name uses the stacked lockup | The page title already says the name. |
| Favicon, web app manifest icons, `theme_color` `#8c16c5` | Mark | Browser tabs and home-screen icons are square and tiny. |
| Per-page social cards (`site/assets/og/cards/*.jpg`, 94 cards) | Stacked lockup on newly rendered cards; existing cards keep the mark until re-rendered | Each card's subject is the page title; the logo signs it. Forward only. |
| App icons (ModernTex, Legroom and the rest) | Neither | Each app has its own icon. |
| App About and credits windows | Side-by-side lockup, small, at the bottom | Small signature spot; the mark travels with the wordmark (Ben, 2026-10-30). |
| Game boot splash, game footers | Side-by-side lockup | Small signature spot. |
| Game credits end, product video credits end | Stacked lockup | Large spot after the product. |
| Company videos (channel intros, how-to end cards about Purplelink itself) | Primary logo | The company is the subject. |
| Social profile avatars (LinkedIn page, Bluesky, Threads, Mastodon, Instagram, Facebook Page) | Mark | Avatars are cropped to a circle; the wordmark would be cut off. Use `purplelink-logo.png`. |
| Social banners and cover images | Stacked lockup | Wide format with room for the name. |
| Email signatures, invoices, documents | Stacked lockup, light version (side-by-side where the slot is wide and short) | Usually printed or shown on white. |
| Anything one colour only (embossing, single-ink print, a monochrome partner list) | Single-colour mark | The gradient cannot be reproduced. |

**Minimum sizes.** Side-by-side lockup: at least 120 px wide on screen. Primary logo: at least 160 px wide on screen (or 30 mm in print), so "software company" stays legible.
Below that, use the mark. Mark: at least 16 px.

**Clear space.** Keep empty space around the lockup equal to the height of the "software company" line on every side.

**Do not:** recolour the mark outside the gradient or the single brand purple, set the wordmark in another font, arrange
the mark and wordmark by hand instead of using the supplied lockup files, show the wordmark without the mark, stretch either piece, or place the mark on a busy photo without a
dark scrim.

## Decisions and reasons, in order

1. **2026-10-28, mark adopted.** Ben supplied eight versions of a striped P-L monogram. The mark was traced into a
   vector from the image's transparency (not resized as a picture) so edges stay crisp at every size, and filled with
   the hue-310 gradient. The gradient's two ends were adjusted twice (72%→50%, then 66%→50%, then 70%→52%) until it
   read on both themes. Kept the old file names so all pages picked it up without markup edits (PRs 419, 420).
2. **2026-10-29, primary logo is the lockup.** Ben: "The main one should be the purplelink softwares one underneath
   the new logo." The wordmark sits centred under the mark at 72 percent of the mark's width, with a gap of a quarter
   of the wordmark's height. The two generic social cards and the press kit now lead with it.
3. **2026-10-29, wordmark alone inside products (reversed by decision 6).** Ben: Circled Hoops "should have just the 'purplelink softwares'
   logo (no design) at the bottom somewhere". Generalised to every app, game and product video.
4. **2026-10-29, logo files are versioned.** The live site served the new mark, but `/assets/*` is cached for 30 days,
   so returning visitors (Ben included) still saw the old one. `scripts/fingerprint_assets.py` now stamps
   `?v=<hash>` on every mark, logo and lockup reference, and `scripts/apply_layout.py` writes the footer mark with the
   same stamp, so a changed logo reaches everyone on their next page load.

5. **2026-10-30, wordmark B.** Ben approved a new wordmark, "purplelink / software company", replacing "purplelink /
   softwares", with the underline swoosh and star in the brand purple gradient (meaning above). The lockup, the
   press kit, the generic social cards and the site header carry it; the header moved from one mask to two. Forward
   only: videos, cards and posts already published keep the old wordmark and are not re-rendered.

6. **2026-10-30, the mark comes back with the wordmark.** Ben: "I still want the <> P logo that we had before above it or
   to the side of it where relevant." This reverses decision 3 ("wordmark alone inside products"), which stays above as
   history. The mark now always accompanies wordmark B, stacked in large and hero spots and side by side (mark left) in
   small and signature spots; the mark alone stays for favicon, avatars and the footer icon. New files:
   `purplelink-lockup-horizontal-dark` / `-light` (`.svg`, `.png`).

## Regenerating

- Mark: an alpha-channel trace of Ben's PNG with the gradient fill; the SVG is the source of truth.
- Lockup and wordmark B: supplied as final artwork (SVG and PNG, dark and light); copy them into `site/assets/` exactly, do not retrace.
- Generic brand cards: `python3 scripts/gen_og_cards.py --brand` (template `scripts/og-brand-card.html`).
- Per-page cards: `python3 scripts/gen_og_cards.py --refresh`.
- After changing any logo file: `python3 scripts/fingerprint_assets.py`.
