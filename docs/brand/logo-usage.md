# Purplelink logo: which version goes where, and why

The design log for the 2026-10 identity. The visual companion is the art book (`docs/brand/art-book.html`).
When a new surface needs a logo, decide it here first and add a row to the table.

## The three pieces

| Piece | Files | What it is |
|---|---|---|
| **Primary logo (lockup)** | `site/assets/purplelink-lockup-dark.svg` / `-light.svg`, `.png` copies | The striped mark with the "purplelink / softwares" wordmark centred beneath it. **This is the main logo.** |
| **Mark** | `site/assets/purplelink-mark.svg`, `purplelink-logo.png` (512), `purplelink-logo-64.png` | The striped P-L monogram alone, gradient fill. |
| **Single-colour mark** | `site/assets/purplelink-logo-v2.png` | The mark in flat brand purple `rgb(140,22,197)` (light-theme `--purple`), for places that cannot show a gradient. |
| **Wordmark only** | `site/assets/purplelink-wordmark-dark.svg` / `-light.svg`, `.png` copies (1216 px wide) | "purplelink / softwares" with no mark. The maker's signature inside another product. Hex fills (`#f0edf4` on dark, `#12001e` on light) so native renderers that do not know OKLCH draw it correctly. |

The wordmark is Ben's own artwork (bold sans "purplelink", serif "softwares"), traced from his transparent PNG; it is
never re-typeset in a site font.

## Colour

- Mark: vertical gradient `oklch(70% 0.18 310)` at the top to `oklch(52% 0.24 310)` at the bottom (hue 310 is the
  site's purple). Chosen so the mark keeps contrast on both the dark default theme and the light theme.
- Wordmark: the site's `--ink` for the background it sits on. Dark backgrounds: `oklch(95% 0.01 310)` (the `-dark`
  files). Light backgrounds: `oklch(14% 0.07 310)` (the `-light` files). Never purple, so the mark stays the accent.

## Where each one is used

| Surface | Piece | Why |
|---|---|---|
| Generic social cards (`site/assets/og/brand.png`, `purplelink-card.png`) | Primary logo | The card is about the company, at 1200x630 there is room for the wordmark to read, and a shared link should carry the full name. |
| Press kit downloads (`/press/`) | Primary logo first, then mark-only files | Journalists should reach for the full logo by default; the mark-only files are for avatars and tight spaces. |
| Site header (30 px) and footer (26 px) | Mark | At this size the wordmark is unreadable (its "softwares" line would be about 3 px tall). The header already spells "Purplelink" next to the mark in text, which screen readers and search engines read. |
| Homepage hero stage mark (88 px) | Mark | Same size limit; the page title says the name. |
| Favicon, web app manifest icons, `theme_color` `#8c16c5` | Mark | Browser tabs and home-screen icons are square and tiny. |
| Per-page social cards (`site/assets/og/cards/*.jpg`, 94 cards) | Mark | Each card's subject is the page title; the mark signs it without competing with the title. |
| App icons (ModernTex, Legroom and the rest) | Neither | Each app has its own icon. |
| Inside a product: an app's About or credits screen, a game's title or credits screen, a product video's end card | Wordmark only, small, at the bottom | The product is the subject; Purplelink signs it the way a publisher's name sits on a book's spine. The mark would compete with the product's own icon (Ben, 2026-10-29: Circled Hoops should carry "purplelink softwares", no design, at the bottom). |
| Company videos (channel intros, how-to end cards about Purplelink itself) | Primary logo | The company is the subject. |
| Social profile avatars (LinkedIn page, Bluesky, Threads, Mastodon, Instagram, Facebook Page) | Mark | Avatars are cropped to a circle; the wordmark would be cut off. Use `purplelink-logo.png`. |
| Social banners and cover images | Primary logo | Wide format with room for the name. |
| Email signatures, invoices, documents | Primary logo, light version | Usually printed or shown on white. |
| Anything one colour only (embossing, single-ink print, a monochrome partner list) | Single-colour mark | The gradient cannot be reproduced. |

**Minimum sizes.** Primary logo: at least 160 px wide on screen (or 30 mm in print), so "softwares" stays legible.
Below that, use the mark. Mark: at least 16 px.

**Clear space.** Keep empty space around the lockup equal to the height of the "softwares" line on every side.

**Do not:** recolour the mark outside the gradient or the single brand purple, set the wordmark in another font, put
the wordmark beside the mark instead of beneath it, stretch either piece, or place the mark on a busy photo without a
dark scrim.

## Decisions and reasons, in order

1. **2026-10-28, mark adopted.** Ben supplied eight versions of a striped P-L monogram. The mark was traced into a
   vector from the image's transparency (not resized as a picture) so edges stay crisp at every size, and filled with
   the hue-310 gradient. The gradient's two ends were adjusted twice (72%→50%, then 66%→50%, then 70%→52%) until it
   read on both themes. Kept the old file names so all pages picked it up without markup edits (PRs 419, 420).
2. **2026-10-29, primary logo is the lockup.** Ben: "The main one should be the purplelink softwares one underneath
   the new logo." The wordmark sits centred under the mark at 72 percent of the mark's width, with a gap of a quarter
   of the wordmark's height. The two generic social cards and the press kit now lead with it.
3. **2026-10-29, wordmark alone inside products.** Ben: Circled Hoops "should have just the 'purplelink softwares'
   logo (no design) at the bottom somewhere". Generalised to every app, game and product video.
4. **2026-10-29, logo files are versioned.** The live site served the new mark, but `/assets/*` is cached for 30 days,
   so returning visitors (Ben included) still saw the old one. `scripts/fingerprint_assets.py` now stamps
   `?v=<hash>` on every mark, logo and lockup reference, and `scripts/apply_layout.py` writes the footer mark with the
   same stamp, so a changed logo reaches everyone on their next page load.

## Regenerating

- Mark: an alpha-channel trace of Ben's PNG with the gradient fill; the SVG is the source of truth.
- Lockup: built from `purplelink-mark.svg` plus the traced wordmark.
- Generic brand cards: `python3 scripts/gen_og_cards.py --brand` (template `scripts/og-brand-card.html`).
- Per-page cards: `python3 scripts/gen_og_cards.py --refresh`.
- After changing any logo file: `python3 scripts/fingerprint_assets.py`.
