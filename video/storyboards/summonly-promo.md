# Summonly promo: storyboard

Target: about 29 seconds including the Purplelink bumpers (product cut about 25 s). 16:9 for the site and YouTube, 9:16 for Shorts, Reels and TikTok. An 8 second silent hero loop and a poster for the Summonly page. A short cut (`summonly-promo-15`, about 21 s with bumpers) from the same screens. The operators screen ("invoice -draft") is a screenshot only; it was cut from the video for length. Facts come only from `site/summonly/index.html` and `site/llms.txt`. No statistics, ratings, testimonials or user counts.

Footage: not a screen recording. Every screen is the app's own SwiftUI view (the search panel, the first-run window) drawn offscreen into a bitmap by `Summonly/scripts/live/run-shots.sh`, running the real search engine on invented files in a throwaway home folder (Quarterly report.pdf, Customer terms.pdf, Invoice 1042.pdf and so on). Nothing from the owner's Mac is shown. The page and the lower thirds say "Sample data". Dark appearance. Voice: en-GB-SoniaNeural at +2% (edge-tts, `narrate.py`) as the Legroom and Keyfeel promos. `narrate.py` points edge-tts at Microsoft's new host since the old one answers 403 from 2026-10-10 (`EDGE_TTS_HOST=legacy` reverts).

Two limits the video states rather than hides: question search is optional and off until it is turned on, and it finds the words you use, so a question worded very differently from the document is found less often. The optional downloaded model helps with reworded questions; this cut does not claim more than the page does, so the model is not mentioned.

## 0. Title card (about 1.2 s)
- **Sees:** app icon, "Summonly", "Files, apps and clipboard history, from one box."
- **Connects to next:** the search panel rises in.

## 1. Search (about 3.5 s)
- **Sees:** the panel with "report" typed: a folder, three files, then Search Google, Ask Claude and Ask ChatGPT rows. A ring on the search box, then on the file rows.
- **Understands:** one box, opened from the keyboard, returns files first.
- **On-screen copy:** "1 Search / Option-Space, type, Return."
- **Narration:** "Press Option-Space, type a few letters, and press Return."

## 2. Questions (about 6 s)
- **Sees:** the panel with "which file mentions the refund policy?" and two answers: Customer terms.pdf "page 3: Refund policy ...", Meeting notes.md with its passage. Ring on the first answer, then on its page number.
- **Understands:** it answers with the file and the passage, and a page for PDFs. It is optional, and it matches words.
- **On-screen copy:** "2 Questions · Optional / It finds the words you use."
- **Narration:** "Ask a question, and it shows the passage, with the page for a PDF. It matches the words you use."

## 3. Clipboard (about 3 s)
- **Sees:** "clip": a pinned item and recent items with their age.
- **On-screen copy:** "3 Clipboard / Search what you copied."
- **Narration:** "Clipboard history keeps what you copy."

## 4. Clipboard privacy (about 4.5 s)
- **Sees:** the first-run window, Clipboard history group: the unticked "Keep clipboard history" box, then the sentence about password managers, card numbers and one-time codes.
- **On-screen copy:** "4 Privacy / Off until you turn it on."
- **Narration:** "It is off until you turn it on, and it skips password managers."

## 6. End card (about 4.5 s, settles)
- **Sees:** icon, "Summonly", pill "$9.99 once. 7-day free trial.", "purplelink.llc/summonly", then the Purplelink bumper.
- **Narration:** "Nine ninety-nine, once, with a seven day free trial."

## 15 second cut
Title, scene 1, scene 2 (shorter narration: "Ask a question, and it shows the passage and the page. It matches the words you use."), end card.

## Claims and where they come from
See the table in the build report; every line maps to a row of "What it does", "Privacy" or the pricing text on `site/summonly/index.html`.

## Media for the site
`site/summonly/media/summonly-poster.webp` (1920x1080), `summonly-hero.mp4` and `summonly-hero.webm` (1280x720, silent loop), `summonly-promo.mp4` (full 16:9), `summonly-promo.vtt` (captions).
