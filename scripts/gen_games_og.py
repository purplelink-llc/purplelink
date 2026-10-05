"""Render the 1200x630 share cards for /games/ (one per game plus the hub) into site/assets/og/games-<slug>.png.

Needs Playwright (python3.12 -m playwright). Run after editing scripts/games_meta.py.
"""
import html, sys, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from games_meta import GAMES, HUB
from playwright.sync_api import sync_playwright

SITE = Path(__file__).resolve().parent.parent / "site"
CSS = """
@font-face { font-family: 'Fraunces'; font-weight: 300 900; src: url('@SITE@/assets/fonts/fraunces-latin.woff2') format('woff2'); }
@font-face { font-family: 'Plus Jakarta Sans'; font-weight: 400 700; src: url('@SITE@/assets/fonts/plus-jakarta-sans-latin.woff2') format('woff2'); }
* { margin: 0; padding: 0; box-sizing: border-box; }
html, body { width: 1200px; height: 630px; overflow: hidden; }
.card { width: 1200px; height: 630px; position: relative; background: oklch(18% 0.025 310); color: oklch(96% 0.01 310); font-family: 'Plus Jakarta Sans', system-ui, sans-serif; overflow: hidden; }
.photo { position: absolute; top: 0; right: 0; width: 560px; height: 630px; background-size: cover; background-position: center; }
.fade { position: absolute; top: 0; right: 0; width: 640px; height: 630px; background: linear-gradient(90deg, oklch(18% 0.025 310) 0%, oklch(18% 0.025 310 / 0.55) 40%, transparent 100%); }
.body { position: absolute; inset: 0; padding: 72px 80px; display: flex; flex-direction: column; justify-content: space-between; }
.top { display: flex; align-items: center; gap: 16px; }
.top img { width: 48px; height: 48px; }
.brand { font-family: 'Fraunces', serif; font-weight: 600; font-size: 30px; }
.kind { font-size: 21px; font-weight: 600; letter-spacing: 2px; text-transform: uppercase; color: oklch(82% 0.13 310); margin-bottom: 18px; }
h1 { font-family: 'Fraunces', serif; font-weight: 600; font-size: 104px; line-height: 0.98; letter-spacing: -2px; max-width: 8ch; }
.tag { font-size: 32px; color: oklch(88% 0.02 300); max-width: 17ch; line-height: 1.3; margin-top: 22px; }
.url { font-size: 26px; font-weight: 600; color: oklch(80% 0.12 310); }
"""
TAG = {"linkle": "Five letters. Six tries. A new twist every weekday.", "quadlink": "Four words at once, in nine guesses.",
       "daily-five": "Five trivia questions, every day.", "daily-photo": "Five photographs. Which country?",
       "daily-chess": "A new tactics puzzle from Lichess.", "sudoku": "Harder every week of the season.",
       "crossword": "A new crossword daily. Easy Monday, hard Sunday.", "daily-stars": "A short horoscope for every sign.",
       "landlink": "Guess the country from seven clues.", "citylink": "Guess the city with a compass.", "peaklink": "Guess the mountain.", "codelink": "Guess the programming language.", "thinkerlink": "Guess the scientist.", "riverlink": "Guess the river.", "wildlink": "Guess the animal.", "atomlink": "Guess the element on the periodic table.", "prizelink": "Guess the Nobel laureate.",
       "lockerlink": "Link two players through teammates.", "gridlink": "Fill the grid with players who fit.", "unbeaten": "Build a team. Go undefeated.", "chess-puzzles": "Unlimited puzzles. Climb the rating.", "sudoku-unlimited": "Unlimited Sudoku, five levels, rated.", "leaderboard": "Top ratings in chess and Sudoku."}

def card(name, kind, tag, photo, site):
    return (f"<!doctype html><meta charset=utf-8><style>{CSS.replace('@SITE@', site)}</style><div class=card>"
            f"<div class=photo style=\"background-image:url('{site}/assets/photography/hub/{photo}-1200.webp')\"></div><div class=fade></div>"
            f"<div class=body><div class=top><img src='{site}/assets/purplelink-logo.png' alt=''><span class=brand>Purplelink</span></div>"
            f"<div><p class=kind>{html.escape(kind)}</p><h1>{html.escape(name)}</h1><p class=tag>{html.escape(tag)}</p></div>"
            f"<p class=url>purplelink.llc/games</p></div></div>")

def main():
    site = SITE.as_uri()
    jobs = [(m["slug"], m["name"], m["genre"] + ", free daily", TAG[m["slug"]], m["og_photo"]) for m in GAMES.values()]
    jobs.append(("hub", "Daily games", "Free, every midnight", "Word games, trivia, chess, Sudoku and a crossword.", HUB["og_photo"]))
    tmp = Path(tempfile.mkdtemp()) / "card.html"
    with sync_playwright() as p:
        b = p.chromium.launch(); pg = b.new_page(viewport={"width": 1200, "height": 630})
        for slug, name, kind, tag, photo in jobs:
            tmp.write_text(card(name, kind, tag, photo, site)); pg.goto(tmp.as_uri(), wait_until="load")
            pg.evaluate("document.fonts.ready"); pg.wait_for_timeout(400)
            out = SITE / "assets" / "og" / f"games-{slug}.png"
            pg.screenshot(path=str(out)); print("wrote", out.name)
        b.close()

if __name__ == "__main__":
    main()
