import json, html, re, sys
from datetime import date
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from games_meta import GAMES as META, HUB as HUBMETA, FOUNDED
from games_art import art
SITE = Path(__file__).resolve().parent.parent / "site"
TODAY = date.today().isoformat()
ORG = {"@type": "Organization", "@id": "https://purplelink.llc/#organization", "name": "Purplelink LLC", "url": "https://purplelink.llc/", "sameAs": ["https://www.youtube.com/@PurplelinkPL", "https://github.com/purplelink-llc"]}
CF = """<!-- Cloudflare Web Analytics --><script defer src="https://static.cloudflareinsights.com/beacon.min.js" data-cf-beacon='{"token": "cf4dd1d7290844b4ab9693930738cad4"}'></script><!-- End Cloudflare Web Analytics -->"""

def first_sentence(text):
    return re.split(r"(?<=[.!?]) ", text, maxsplit=1)[0]


def seo_extras(path, m):
    """Tips and a related-games list, added after the page's own prose."""
    tips = "".join(f"          <li>{html.escape(t)}</li>\n" for t in m["tips"])
    rel = ""
    for slug in m["related"]:
        r = next(v for v in META.values() if v["slug"] == slug)
        rel += f'          <li><a href="/games/{slug}/"><strong>{html.escape(r["name"])}</strong></a>: {html.escape(first_sentence(r["answer"]))}</li>\n'
    return (f'        <div class="games-prose">\n          <h2>Tips for {html.escape(m["name"])}</h2>\n          <ul>\n{tips}          </ul>\n'
            f'          <h2>More daily games</h2>\n          <ul class="games-related">\n{rel}          </ul>\n        </div>\n')


def seo_graph(path, m, faq_node, url, og):
    crumb = {"@type": "BreadcrumbList", "@id": url + "#breadcrumb", "itemListElement": [
        {"@type": "ListItem", "position": 1, "name": "Home", "item": "https://purplelink.llc/"},
        {"@type": "ListItem", "position": 2, "name": "Games", "item": "https://purplelink.llc/games/"},
        {"@type": "ListItem", "position": 3, "name": m["name"], "item": url}]}
    app = {"@type": "WebApplication", "@id": url + "#app", "name": m["name"], "url": url, "description": m["answer"],
           "applicationCategory": "GameApplication", "applicationSubCategory": m["genre"], "genre": m["genre"],
           "operatingSystem": "Any (web-based)", "browserRequirements": "Requires JavaScript", "inLanguage": "en",
           "isAccessibleForFree": True, "offers": {"@type": "Offer", "price": "0", "priceCurrency": "USD"},
           "featureList": m["features"], "image": og, "datePublished": FOUNDED, "dateModified": TODAY,
           "publisher": {"@id": ORG["@id"]}, "author": {"@id": ORG["@id"]}}
    web = {"@type": "WebPage", "@id": url + "#webpage", "url": url, "name": m["title"], "description": m["desc"], "inLanguage": "en",
           "isPartOf": {"@type": "WebSite", "@id": "https://purplelink.llc/#website", "url": "https://purplelink.llc/", "name": "Purplelink"},
           "about": {"@id": url + "#app"}, "mainEntity": {"@id": url + "#app"}, "breadcrumb": {"@id": url + "#breadcrumb"},
           "primaryImageOfPage": {"@type": "ImageObject", "url": og, "width": 1200, "height": 630},
           "datePublished": FOUNDED, "dateModified": TODAY,
           "speakable": {"@type": "SpeakableSpecification", "cssSelector": [".game-lede", "h1"]}}
    how = {"@type": "HowTo", "@id": url + "#howto", "name": f"How to play {m['name']}", "totalTime": f"PT{m['minutes']}M",
           "step": [{"@type": "HowToStep", "position": i + 1, "name": n, "text": t} for i, (n, t) in enumerate(m["steps"])]}
    return {"@context": "https://schema.org", "@graph": [ORG, web, app, how, faq_node, crumb]}


def page(path, title, desc, body, jsonld, scripts, og_title=None, robots="index, follow", ads=False):
    url = f"https://purplelink.llc/{path}"
    og_image, og_alt = "https://purplelink.llc/assets/og/brand.png", "Purplelink: Mac apps and manuscript tools for researchers"
    m = META.get(path)
    if m:
        title = m["title"] + (" | Purplelink" if len(m["title"]) <= 52 else "")
        desc = m["desc"]
        og_title = m["title"]
        og_image = f"https://purplelink.llc/assets/og/games-{m['slug']}.png"
        og_alt = f"{m['name']}, a free daily puzzle from Purplelink"
        body = re.sub(r'<p class="game-lede">.*?</p>', '<p class="game-lede">' + html.escape(m["answer"]) + '</p>', body, count=1, flags=re.S)
        body = body.replace('        <p class="games-note"><a href="/games/">All daily games</a></p>', seo_extras(path, m) + '        <p class="games-note"><a href="/games/">All daily games</a></p>', 1)
        faq_node = next(n for n in jsonld["@graph"] if n.get("@type") == "FAQPage")
        jsonld = seo_graph(path, m, faq_node, url, og_image)
        robots = "index, follow, max-image-preview:large"
    elif path == "games/":
        title, desc, og_title = HUBMETA["title"], HUBMETA["desc"], HUBMETA["title"]
        og_image, og_alt = "https://purplelink.llc/assets/og/games-hub.png", "Purplelink's free daily games"
        robots = "index, follow, max-image-preview:large"
    slug = m["slug"] if m else None
    main_attr = f' data-g="{slug}"' if slug else ""
    dock_html = dock(slug) if slug else ""
    if slug:
        scripts = [x for x in scripts if x not in ("/games/achievements.js", "/games/confetti.js", "/games/sync.js")]
        scripts = ["/games/core.js", "/games/fx.js", "/games/sync.js", "/games/achievements.js", "/games/goals.js", "/games/confetti.js", "/games/dock.js", "/games/share.js"] + [x for x in scripts if x != "/games/core.js"]
    game_css = f'    <link rel="stylesheet" href="/games/{slug}.css">\n' if slug and (SITE / "games" / f"{slug}.css").exists() else ""
    ads_tag = '    <script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-6407975157274256" crossorigin="anonymous"></script>' if ads else ""
    ld = json.dumps(jsonld, indent=2)
    ld = "\n".join("    " + l for l in ld.splitlines())
    sc = "\n".join(f'    <script src="{s}"{" defer" if True else ""}></script>' for s in scripts)
    t = html.escape(title, quote=False)
    d = html.escape(desc)
    ot = html.escape(og_title or title.split(" | ")[0], quote=False)
    out = f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta name="robots" content="{robots}">
    <title>{t}</title>
    <meta name="description" content="{d}">
    <link rel="canonical" href="{url}">
    <meta property="og:title" content="{ot}">
    <meta property="og:description" content="{d}">
    <meta property="og:type" content="website">
    <meta property="og:url" content="{url}">
    <meta property="og:site_name" content="Purplelink">
    <meta property="og:locale" content="en_US">
    <meta property="og:image" content="{og_image}">
    <meta property="og:image:width" content="1200">
    <meta property="og:image:height" content="630">
    <meta property="og:image:alt" content="{html.escape(og_alt)}">
    <meta name="twitter:card" content="summary_large_image">
    <meta name="twitter:title" content="{ot}">
    <meta name="twitter:description" content="{d}">
    <meta name="twitter:image" content="{og_image}">
    <meta name="twitter:image:alt" content="{html.escape(og_alt)}">
    <script type="application/ld+json">
{ld}
    </script>
    <link rel="icon" href="/assets/purplelink-logo.png" type="image/png">
    <meta name="theme-color" content="#19141d">
    <link rel="preload" href="/assets/fonts/fraunces-latin.woff2" as="font" type="font/woff2" crossorigin>
    <link rel="preload" href="/assets/fonts/plus-jakarta-sans-latin.woff2" as="font" type="font/woff2" crossorigin>
    <script src="/theme.js"></script>
{ads_tag}
    <link rel="stylesheet" href="/styles.css">
    <link rel="stylesheet" href="/motion.css">
    <link rel="stylesheet" href="/games/games.css">
    <link rel="stylesheet" href="/games/games-ui.css">
{game_css}    <script src="/site.js" defer></script>
    <script src="/motion.js" defer></script>
</head>
  <body>
    <a class="skip-link" href="#main-content">Skip to content</a>
    <header class="topbar">
      <a class="brand" href="/" aria-label="Purplelink home">
        <img src="/assets/purplelink-mark.svg" alt="" width="30" height="30">
        <span>Purplelink</span>
      </a>
      <nav aria-label="Primary navigation">
      </nav>
    </header>

    <main id="main-content" class="games"{main_attr}>
{dock_html}{body}
    </main>

{sc}
    <footer class="footer"></footer>
  {CF}
      <script src="/analytics.js" defer></script>
</body>
</html>
"""
    p = SITE / path / "index.html"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(out)


EXTRA = [("chess-puzzles", "Chess Puzzles"), ("leaderboard", "Leaderboards")]
MORE_DAILY = ["peaklink"]
SPORTS_GAMES = ["lockerlink"]
STRATEGY_GAMES = []
ORDER = ["linkle", "quadlink", "crossword"]
BYSLUG = {m["slug"]: m for m in META.values()}
TAGLINE = {
    "linkle": "Five letters, six tries, and a new twist every weekday.",
    "quadlink": "Four hidden words at once, with a new twist every weekday.",
    "crossword": "A themeless crossword. New puzzles stop after November 14.",
    "peaklink": "Guess the mountain from height, place and volcano clues.",
    "lockerlink": "Link two players from any era through real teammates.",
    "chess-puzzles": "Unlimited rated tactics, plus a three-minute Rush mode.",
    "leaderboard": "The top ratings in Chess Puzzles and Lockerlink, and this week's climbers.",
}
MINUTES = {"lockerlink": 4, "peaklink": 3, "chess-puzzles": 2, "leaderboard": 1, "linkle": 3, "quadlink": 5, "crossword": 10}
USE = '<svg class="gl" aria-hidden="true" focusable="false"><use href="/games/glyphs.svg#{}"/></svg>'


def dock(current):
    items = []
    for slug in ORDER:
        m = BYSLUG[slug]
        cur = ' aria-current="page"' if slug == current else ""
        items.append(f'<li><a class="dock-link" data-g="{slug}" href="/games/{slug}/"{cur}>{USE.format(slug)}<span class="dock-name">{html.escape(m["name"])}</span>'
                     f'<span class="dock-state" aria-hidden="true"></span><span class="visually-hidden dock-sr"></span></a></li>')
    for slug in MORE_DAILY:
        m = BYSLUG[slug]
        cur = ' aria-current="page"' if slug == current else ""
        items.append(f'<li><a class="dock-link" data-g="{slug}" href="/games/{slug}/"{cur}>{USE.format(slug)}<span class="dock-name">{html.escape(m["name"])}</span>'
                     f'<span class="dock-state" aria-hidden="true"></span><span class="visually-hidden dock-sr"></span></a></li>')
    for slug in SPORTS_GAMES + STRATEGY_GAMES:
        m = BYSLUG[slug]
        cur = ' aria-current="page"' if slug == current else ""
        items.append(f'<li><a class="dock-link" data-g="{slug}" href="/games/{slug}/"{cur}>{USE.format(slug)}<span class="dock-name">{html.escape(m["name"])}</span>'
                     f'<span class="dock-state" aria-hidden="true"></span><span class="visually-hidden dock-sr"></span></a></li>')
    extra = []
    for slug, label in EXTRA:
        cur = ' aria-current="page"' if slug == current else ""
        extra.append(f'<li class="dock-more"><a class="dock-link" data-g="{slug}" data-x href="/games/{slug}/"{cur} title="{label}">{USE.format(slug)}<span class="dock-name">{label}</span></a></li>')
    return ('    <nav class="game-dock" aria-label="Daily games">\n'
            f'      <ul class="dock-list">\n        <li><a class="dock-link dock-all" href="/games/" title="All games">{USE.format("grid")}<span class="dock-name">All games</span></a></li>\n        ' + "\n        ".join(items + extra) + '\n      </ul>\n'
            '      <div class="dock-tools">\n'
            '        <span class="dock-chip" id="dock-streak" hidden></span>\n'
            '        <a class="dock-chip" id="dock-level" href="/games/account/" title="Your level and achievements"></a>\n'
            f'        <button type="button" class="dock-btn" data-fx-sound aria-pressed="true" aria-label="Sound on. Turn sound off">{USE.format("sound-on")}<span class="fx-label visually-hidden">Sound on</span></button>\n'
            '      </div>\n    </nav>\n')


def tile(slug):
    m = BYSLUG[slug]
    return (f'          <a class="tile" data-game="{slug}" data-g="{slug}" href="/games/{slug}/">\n'
            f'            <span class="tile-art">{art(slug)}<span class="tile-badge">{USE.format("bolt").replace('class="gl"', 'class="gl gl-sm"')}Spotlight</span>'
            f'<span class="tile-check" aria-hidden="true">{USE.format("check")}</span></span>\n'
            f'            <span class="tile-body"><h2>{html.escape(m["name"])}</h2><p>{html.escape(TAGLINE[slug])}</p>\n'
            f'              <span class="tile-foot"><span class="tile-status" data-status>About {MINUTES[slug]} {"minute" if MINUTES[slug] == 1 else "minutes"}</span><span class="tile-go" data-go>Play</span></span></span>\n'
            f'          </a>\n')


def crumbs(*items):
    return {"@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": i + 1, "name": n, "item": u} for i, (n, u) in enumerate(items)]}

def faq(qas):
    return {"@type": "FAQPage", "mainEntity": [
        {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in qas]}

def faq_html(qas):
    return "\n".join(f"        <h3>{html.escape(q)}</h3>\n        <p>{html.escape(a)}</p>" for q, a in qas)

def game_app(name, url, desc):
    return {"@type": "WebApplication", "name": name, "url": url, "applicationCategory": "GameApplication",
            "operatingSystem": "Any (web-based)", "browserRequirements": "Requires JavaScript", "description": desc,
            "offers": {"@type": "Offer", "price": "0", "priceCurrency": "USD"},
            "provider": {"@type": "Organization", "name": "Purplelink LLC", "url": "https://purplelink.llc/"}}

WORD_UI = """      <div class="games-wrap">
        <div class="game-head">
          <h1>{h1}</h1>
          <span class="game-num" id="wg-number" aria-live="off"></span>
        </div>
        <p class="game-lede">{lede}</p>
        <p id="wg-loading" class="games-note">Loading today's puzzle.</p>
        <div id="wg-game" hidden>
          <div class="wg-status" id="wg-status" role="status" aria-live="polite"></div>
{twist}
          <p class="wg-msg" id="wg-msg" aria-hidden="true"></p>
          <div class="wg-boards" id="wg-boards" data-boards="{boards}"></div>
          <div class="wg-keys" id="wg-keys" aria-label="Keyboard"></div>
          <section class="game-result" id="wg-result" hidden aria-labelledby="wg-result-head">
            <h2 id="wg-result-head"></h2>
            <p class="game-reveal" id="wg-reveal"></p>
            <div class="game-statline">
              <div><b id="wg-played">0</b><span>Played</span></div>
              <div><b id="wg-winpct">0%</b><span>Won</span></div>
              <div><b id="wg-streak">0</b><span>Streak</span></div>
              <div><b id="wg-max">0</b><span>Best streak</span></div>
            </div>
            <div class="wg-dist" id="wg-dist"></div>
            <p class="game-pct" id="wg-pct"></p>
            <p class="game-pct" id="wg-saver"></p>
{meta}
            <div class="game-actions">
              <button type="button" class="btn btn-primary" id="wg-share">Copy result</button>
              <button type="button" class="gbtn gbtn--ghost" id="wg-practice-btn">Play a practice word</button>
              <span class="game-note" id="wg-share-note"></span>
            </div>
            <textarea class="wg-share-text" id="wg-share-text" hidden readonly aria-label="Result text"></textarea>
            <p class="game-next">Next puzzle in <span id="wg-next"></span>.</p>
          </section>
          <section class="game-result" id="wg-practice" hidden aria-label="Practice result">
            <p class="game-reveal" id="wg-practice-text" role="status"></p>
            <div class="game-actions">
              <button type="button" class="gbtn" id="wg-practice-again">Another word</button>
              <a class="gbtn gbtn--ghost" href="/games/">More games</a>
            </div>
          </section>
        </div>
        <div class="games-prose">
{prose}
        </div>
        <p class="games-note"><a href="/games/">All daily games</a></p>
      </div>"""

TWIST_HTML = """          <p class="wg-twist" id="wg-twist" hidden><strong id="wg-twist-name"></strong> <span id="wg-twist-text"></span></p>"""
META_HTML = """            <p class="wg-rank" id="wg-rank"></p>
            <div class="wg-week" id="wg-week" role="group" aria-label="This week"></div>
            <p class="game-note" id="wg-week-note"></p>
            <p class="game-note" id="wg-tomorrow"></p>"""

def legend(sample):
    return f"""        <h2>How to play</h2>
{sample}"""

# ---------------- Linkle ----------------
LINKLE_FAQ = [
    ("What are the weekday twists?", "Each day has its own rule. Monday is standard. Tuesday shows the first letter. Wednesday gives you a seventh guess. Thursday tells you how many vowels the word has. Friday's word never repeats a letter. Saturday's word always repeats one. Sunday is hard mode, where every hint you find must be used in your next guess."),
    ("What are ranks and the weekly tracker?", "Your rank rises with the number of puzzles you have solved: Newcomer, Reader, Scribe, Wordsmith, Lexicographer and Sage. The tracker shows which days of the current Monday-to-Sunday week you solved, and counts the weeks where you solved all seven."),
    ("Does the puzzle change every day?", "Yes. A new word is ready at midnight your time, and everyone sees the same word on the same date."),
    ("Which words are accepted?", "Any five-letter word from a public-domain English word list of about 8,600 words. Answers are drawn from a smaller set of everyday words."),
    ("What happens with repeated letters?", "A letter is marked only as many times as it appears in the answer. If you guess two Es and the word has one, only one E is marked."),
    ("Where is my streak stored?", "Saved in your browser on this device. If you sign in with an email link, your streaks and achievements also follow you to other devices; without signing in, clearing site data or switching devices starts fresh."),
    ("How do I share my result?", "Copy result puts the grid and your score on the clipboard as plain text, with no letters, so it does not give the word away."),
]
LINKLE_PROSE = """        <h2>How to play</h2>
        <p>Guess the five-letter word in six tries. After each guess the tiles show how close you were.</p>
        <div class="game-legend">
          <span><span class="wg-tile" data-s="c">C</span> Right letter, right place</span>
          <span><span class="wg-tile" data-s="p">R</span> In the word, wrong place (striped)</span>
          <span><span class="wg-tile" data-s="a">X</span> Not in the word</span>
        </div>
        <p>Type with your keyboard or tap the keys. Press Enter to submit and Backspace to delete. A new puzzle appears every day at midnight in your time zone.</p>
        <h2>The weekday twists</h2>
        <ul>
          <li><strong>Monday:</strong> standard rules.</li>
          <li><strong>Tuesday, head start:</strong> you are told the first letter.</li>
          <li><strong>Wednesday, extra guess:</strong> seven guesses instead of six.</li>
          <li><strong>Thursday, vowel count:</strong> you are told how many vowels the word has.</li>
          <li><strong>Friday, no repeats:</strong> no letter appears twice.</li>
          <li><strong>Saturday, double up:</strong> at least one letter appears twice.</li>
          <li><strong>Sunday, hard mode:</strong> every hint you have found must be used in your next guess.</li>
        </ul>
        <h2>Practice words</h2>
        <p>After you finish the daily puzzle you can play as many practice rounds as you like. They use random words and never count toward your streak, rank or stats.</p>
        <h2>Questions</h2>
""" + faq_html(LINKLE_FAQ)

page("games/linkle/",
     "Linkle: a free daily five-letter word game | Purplelink",
     "Guess the five-letter word in six tries. A new puzzle every day, free, with no third-party ads. You do not need an account.",
     WORD_UI.format(h1="Linkle", boards=1, lede="One five-letter word a day, with a new twist each weekday.", prose=LINKLE_PROSE, twist=TWIST_HTML, meta=META_HTML),
     {"@context": "https://schema.org", "@graph": [
         game_app("Linkle", "https://purplelink.llc/games/linkle/", "A free daily five-letter word guessing game with six tries."),
         faq(LINKLE_FAQ),
         crumbs(("Home", "https://purplelink.llc/"), ("Games", "https://purplelink.llc/games/"), ("Linkle", "https://purplelink.llc/games/linkle/"))]},
     ["/games/core.js", "/games/sync.js", "/games/achievements.js", "/games/confetti.js", "/games/config-linkle.js", "/games/wordgame.js"])

# ---------------- Quadlink ----------------
QUAD_FAQ = [
    ("How is Quadlink different from Linkle?", "You solve four words at once. Each guess is scored against all four boards, and you get nine guesses."),
    ("How do I read the keyboard?", "Each key has four small bars, one per board, in board order. A bar shows the best state of that letter on that board."),
    ("Does the puzzle change every day?", "Yes. Four new words are ready at midnight your time, and everyone sees the same four on the same date."),
    ("Can the four words repeat a letter?", "Yes. The four words can share letters, and the same word never appears twice in one day."),
    ("Where is my streak stored?", "Saved in your browser on this device. If you sign in with an email link, your streaks and achievements also follow you to other devices; without signing in, clearing site data or switching devices starts fresh."),
]
QUAD_PROSE = """        <h2>How to play</h2>
        <p>Find all four hidden five-letter words in nine guesses. Every guess you make is checked against all four boards at once. A board stops taking guesses once you solve it.</p>
        <div class="game-legend">
          <span><span class="wg-tile" data-s="c">C</span> Right letter, right place</span>
          <span><span class="wg-tile" data-s="p">R</span> In the word, wrong place (striped)</span>
          <span><span class="wg-tile" data-s="a">X</span> Not in the word</span>
        </div>
        <p>The keyboard shows four small bars under each letter, one for each board, in order from the first board to the fourth.</p>
        <h2>The weekday twists</h2>
        <ul>
          <li><strong>Monday:</strong> standard rules, nine guesses.</li>
          <li><strong>Tuesday, head start:</strong> you are told the first letter of each word.</li>
          <li><strong>Wednesday, extra guess:</strong> ten guesses.</li>
          <li><strong>Thursday, vowel counts:</strong> you are told how many vowels each word has.</li>
          <li><strong>Friday, last letters:</strong> you are told the last letter of each word.</li>
          <li><strong>Saturday, tight squeeze:</strong> eight guesses.</li>
          <li><strong>Sunday, hard mode:</strong> hints you find on the first board must be used in your next guess.</li>
        </ul>
        <h2>Practice words</h2>
        <p>After you finish the daily puzzle you can play as many practice rounds as you like. They use random puzzles and never count toward your streak or stats.</p>
        <h2>Questions</h2>
""" + faq_html(QUAD_FAQ)

page("games/quadlink/",
     "Quadlink: a free daily four-board word game | Purplelink",
     "Solve four five-letter words at once in nine guesses. A new puzzle every day, free, with no third-party ads.",
     WORD_UI.format(h1="Quadlink", boards=4, lede="Four five-letter words at once, with a new twist each weekday.", prose=QUAD_PROSE, twist=TWIST_HTML, meta="""            <p class="game-note" id="wg-tomorrow"></p>"""),
     {"@context": "https://schema.org", "@graph": [
         game_app("Quadlink", "https://purplelink.llc/games/quadlink/", "A free daily word game where you solve four five-letter words at once in nine guesses."),
         faq(QUAD_FAQ),
         crumbs(("Home", "https://purplelink.llc/"), ("Games", "https://purplelink.llc/games/"), ("Quadlink", "https://purplelink.llc/games/quadlink/"))]},
     ["/games/core.js", "/games/sync.js", "/games/achievements.js", "/games/confetti.js", "/games/config-quadlink.js", "/games/wordgame.js"])

(SITE / "games/config-linkle.js").write_text('window.PLWordGame = { name: "linkle", title: "Linkle", boards: 1, maxGuesses: 6, dataFile: "linkle.json", url: "https://purplelink.llc/games/linkle/", twists: true };\n')
(SITE / "games/config-quadlink.js").write_text('window.PLWordGame = { name: "quadlink", title: "Quadlink", boards: 4, maxGuesses: 9, dataFile: "quadlink.json", url: "https://purplelink.llc/games/quadlink/", twists: "quad" };\n')


# ---------------- Crossword ----------------
CW_FAQ = [
    ('What does Pencil do?', 'Pencil mode marks the letters you type as tentative: they show lighter until you tap Ink all. They count exactly like any other letter when you check or finish.'),
    ("Are there still new crosswords?", "Not for now. New crosswords are paused, and the last new one is for Saturday, November 14, 2026. After that the page shows that puzzle to play again; replays do not count toward stats, streaks or the leaderboard."),
    ("How is the crossword made?", "The grids are built by a program that fills a symmetric pattern from a word list, and the clues are written for each puzzle. The size of the grid, how rare the words are and how the clues are phrased all grow from Monday to Sunday."),
    ("What do Check and Reveal do?", "You can check one letter, one word or the whole puzzle, and wrong letters turn red. Auto-check marks a wrong letter as soon as you type it. Reveal fills in a letter, a word or the whole puzzle. Using any of them is shown as solving with help, and only unaided solves count toward your best time."),
    ("Where are my times and streak stored?", "Saved in your browser on this device. If you sign in with an email link, your streaks and achievements also follow you to other devices; without signing in, clearing site data or switching devices starts fresh."),
    ("How do I play on a phone?", "Tap a square, then type with the on-screen keyboard. Tap the same square again to switch between across and down, or tap a clue in the list."),
]
CW_SIZES = [("Monday", "9 by 9, everyday words, direct clues"), ("Tuesday", "9 by 9, everyday words"), ("Wednesday", "11 by 11"), ("Thursday", "11 by 11, harder words"), ("Friday", "13 by 13, harder clues"), ("Saturday", "13 by 13, the hardest words"), ("Sunday", "15 by 15, the biggest grid")]
CW_PROSE = """        <h2>How it works</h2>
        <p>Click a square and type. Click it again, or press Space, to switch between across and down. Arrow keys move around the grid, Tab jumps to the next clue and Backspace deletes. On a phone, use the keyboard below the grid.</p>
        <h2>Difficulty through the week</h2>
        <ul>
""" + "\n".join(f"          <li><strong>{d}:</strong> {t}.</li>" for d, t in CW_SIZES) + """
        </ul>
        <h2>Questions</h2>
""" + faq_html(CW_FAQ)
CW_BODY = """      <div class="games-wrap">
        <div class="game-head">
          <h1>Daily Crossword</h1>
          <span class="game-num" id="cw-number"></span>
        </div>
        <p class="game-lede">A themeless crossword, easiest on Monday and hardest on Sunday. New crosswords stop after November 14, 2026.</p>
        <p id="cw-loading" class="games-note">Loading the crossword.</p>
        <p id="cw-missing" class="games-note" hidden>Today's crossword is not ready yet. Please check back soon.</p>
        <p id="cw-paused" class="games-note" hidden>New crosswords are paused. Here is the most recent one to play again; it does not count toward your stats.</p>
        <div id="cw-game" hidden>
          <div class="cw-layout">
            <div class="cw-main">
              <div class="cw-bar" role="group" aria-label="Check and reveal">
                <span class="cw-bar-label">Check</span>
                <button type="button" class="btn btn-ghost" id="cw-check-letter">Letter</button>
                <button type="button" class="btn btn-ghost" id="cw-check-word">Word</button>
                <button type="button" class="btn btn-ghost" id="cw-check">Puzzle</button>
                <button type="button" class="btn btn-ghost" id="cw-auto" aria-pressed="false">Auto-check: off</button>
                <button type="button" class="btn btn-ghost" id="cw-pencil" aria-pressed="false">Pencil: off</button>
                <button type="button" class="btn btn-ghost" id="cw-ink">Ink all</button>
                <span class="cw-timer" id="cw-timer" aria-label="Elapsed time">0:00</span>
              </div>
              <div class="cw-bar" role="group" aria-label="Reveal answers">
                <span class="cw-bar-label">Reveal</span>
                <button type="button" class="btn btn-ghost" id="cw-reveal-letter">Letter</button>
                <button type="button" class="btn btn-ghost" id="cw-reveal-word">Word</button>
                <button type="button" class="btn btn-ghost" id="cw-reveal-puzzle">Reveal puzzle</button>
              </div>
              <div class="cw-cluebar">
                <button type="button" class="cw-arrow" id="cw-prev-clue" aria-label="Previous clue">&lsaquo;</button>
                <p class="cw-current" id="cw-current" aria-live="polite"></p>
                <button type="button" class="cw-arrow" id="cw-next-clue" aria-label="Next clue">&rsaquo;</button>
              </div>
              <div class="cw-grid" id="cw-grid" role="grid" aria-label="Crossword grid"></div>
              <p class="cw-status" id="cw-status" role="status" aria-live="polite"></p>
              <div class="wg-keys cw-keys" id="cw-keys" aria-label="Keyboard"></div>
              <section class="game-result" id="cw-result" hidden aria-labelledby="cw-result-head">
                <h2 id="cw-result-head"></h2>
                <div class="game-statline">
                  <div><b id="cw-played">0</b><span>Solved</span></div>
                  <div><b id="cw-streak">0</b><span>Streak</span></div>
                  <div><b id="cw-max">0</b><span>Best streak</span></div>
                  <div><b id="cw-best">none</b><span id="cw-best-label">Best time</span></div>
                </div>
                <p class="game-pct" id="cw-pct"></p>
                <p class="game-pct" id="cw-saver"></p>
                <div class="game-actions">
                  <button type="button" class="btn btn-primary" id="cw-share">Copy result</button>
                  <span class="game-note" id="cw-share-note"></span>
                </div>
                <textarea class="wg-share-text" id="cw-share-text" hidden readonly aria-label="Result text"></textarea>
                <p class="game-next" id="cw-next">Next crossword in <span id="cw-next-in"></span>.</p>
              </section>
            </div>
            <div class="cw-clues">
              <div><h2>Across</h2><ol id="cw-across"></ol></div>
              <div><h2>Down</h2><ol id="cw-down"></ol></div>
            </div>
          </div>
        </div>
        <div class="games-prose">
""" + CW_PROSE + """
        </div>
        <p class="games-note"><a href="/games/">All daily games</a></p>
      </div>"""
page("games/crossword/",
     "Daily Crossword: a free themeless puzzle, easy Monday to hard Sunday | Purplelink",
     "A free themeless crossword, easiest on Monday and hardest on Sunday. New crosswords stop after November 14, 2026, and the last one stays here to play again. No account needed.",
     CW_BODY,
     {"@context": "https://schema.org", "@graph": [
         game_app("Daily Crossword", "https://purplelink.llc/games/crossword/", "A free themeless crossword. New puzzles stop after November 14, 2026, and the last one stays here to play again."),
         faq(CW_FAQ),
         crumbs(("Home", "https://purplelink.llc/"), ("Games", "https://purplelink.llc/games/"), ("Daily Crossword", "https://purplelink.llc/games/crossword/"))]},
     ["/games/core.js", "/games/sync.js", "/games/achievements.js", "/games/confetti.js", "/games/crossword.js"])



# ---------------- Chess Puzzles (rated, unlimited) ----------------
CP_FAQ = [
    ('What is Rush?', 'Rush is a three-minute run mode on the same page. Puzzles start easy and get harder. A wrong move costs five seconds and a strike, three strikes end the run, and your score is the number of puzzles solved. Rush does not change your rating, and your best score is kept on this device.'),
    ("How is my puzzle rating worked out?", "It is an Elo rating, like a chess rating. Each puzzle has a rating from the Lichess database. If you solve a puzzle rated above you, you gain a lot; if you solve one well below you, you gain a little; a miss costs more the easier the puzzle was. Early on, ratings move faster, and they settle after about 20 puzzles."),
    ("Is this the same as my Lichess puzzle rating?", "No. It is a separate rating that starts at 1000 here, so the numbers are not comparable with Lichess or any other site."),
    ("What counts as a miss?", "The first wrong move ends the puzzle, as on Lichess, and the correct line is shown. Show solution also counts as a miss. A move that gives checkmate is always accepted."),
    ("Is there a daily limit?", "No. Play as many puzzles as you like. Each new puzzle is picked near your current rating and avoids ones you saw recently."),
    ("Do I need an account?", "No. Without one, your rating is kept on this device. Signing in with an email link keeps it across devices and lets you appear on the leaderboard if you choose."),
    ("How do the leaderboards work?", "Signed-in players can opt in under a display name. The board shows the top 100 by rating and the top 100 by rating gained this week. The rating service checks that every report is for a real puzzle taken in a plausible time and works out the rating itself, so the browser cannot send a rating."),
    ("Where do the puzzles come from?", "From the Lichess puzzle database, released under the CC0 licence. Move rules are handled by chess.js, used under its BSD licence."),
    ("Are there ads?", "Yes. This page shows Google ads, which is how the unlimited puzzles stay free. The daily games have none."),
]
CP_PROSE = """        <h2>How it works</h2>
        <p>Each puzzle starts right after your opponent moves. Find the best move for the side at the bottom of the board and keep going until the puzzle ends. A solve raises your rating and a miss lowers it. The next puzzle is picked near your rating, so the level follows you.</p>
        <h2>Ratings at a glance</h2>
        <table class="games-table">
          <thead><tr><th scope="col">Rating</th><th scope="col">Title</th></tr></thead>
          <tbody>
            <tr><td>Under 800</td><td>Novice</td></tr><tr><td>800 to 1199</td><td>Learner</td></tr><tr><td>1200 to 1499</td><td>Club player</td></tr>
            <tr><td>1500 to 1799</td><td>Strong</td></tr><tr><td>1800 to 2099</td><td>Expert</td></tr><tr><td>2100 to 2399</td><td>Master</td></tr><tr><td>2400 and up</td><td>Grandmaster</td></tr>
          </tbody>
        </table>
        <h2>Questions</h2>
""" + faq_html(CP_FAQ) + """
        <p class="quiz-credit">Puzzles come from the <a href="https://database.lichess.org/#puzzles" rel="noopener">Lichess puzzle database</a>, released under CC0. Chess rules are handled by <a href="https://github.com/jhlywa/chess.js" rel="noopener">chess.js</a>, used under its BSD licence.</p>"""
CP_BODY = """      <div class="games-wrap">
        <div class="game-head">
          <h1>Chess Puzzles</h1>
          <span class="game-num" id="ch-number"></span>
        </div>
        <p class="game-lede">Chess Puzzles is a free, unlimited chess tactics trainer.</p>
        <p class="mode-switch" role="group" aria-label="Choose a mode"><a class="mode-opt" id="mode-rated" href="/games/chess-puzzles/">Rated</a><a class="mode-opt" id="mode-rush" href="/games/chess-puzzles/?mode=rush">Rush, 3 minutes</a></p>
        <section class="game-result" id="rush-start" hidden aria-labelledby="rush-start-h">
          <h2 id="rush-start-h">Rush</h2>
          <p class="game-reveal">Three minutes. Solve as many puzzles as you can, starting easy and getting harder. A wrong move costs five seconds and a strike, and three strikes end the run. Rush does not change your rating.</p>
          <p class="game-note" id="rush-best-line"></p>
          <div class="game-actions"><button type="button" class="gbtn" id="rush-go" data-g="chess-puzzles">Start the clock</button></div>
        </section>
        <div class="rush-hud" id="rush-hud" hidden>
          <div class="rate-stat"><span class="rate-n" id="rush-time" role="timer">3:00</span><span class="rate-l">Time left</span></div>
          <div class="rate-stat"><span class="rate-n rate-n--sm" id="rush-score">0</span><span class="rate-l">Solved</span></div>
          <div class="rate-stat"><span class="rate-n rate-n--sm" id="rush-strikes">0 of 3</span><span class="rate-l">Strikes</span></div>
        </div>
        <section class="game-result rate-result" id="rush-result" hidden aria-labelledby="ru-head">
          <h2 id="ru-head"></h2>
          <p class="rate-delta" id="ru-score" data-up="1"></p>
          <p class="rate-line">puzzles solved</p>
          <p class="game-reveal" id="ru-best"></p>
          <div class="game-actions">
            <a class="gbtn" id="ru-again" href="/games/chess-puzzles/?mode=rush" data-g="chess-puzzles">Play again</a>
            <button type="button" class="btn btn-primary" id="ru-share">Share</button>
            <a class="gbtn gbtn--ghost" href="/games/chess-puzzles/">Back to rated</a>
            <span class="game-note" id="ru-share-note"></span>
          </div>
          <textarea class="wg-share-text" id="ru-share-text" hidden readonly aria-label="Result text"></textarea>
        </section>
        <div class="rate-hud" id="rate-hud">
          <div class="rate-stat"><span class="rate-n" id="cr-rating">1000</span><span class="rate-l" id="cr-tier-top">Learner</span></div>
          <div class="rate-stat"><span class="rate-n rate-n--sm" id="cr-streak-top">0</span><span class="rate-l">Solved in a row</span></div>
          <a class="gbtn gbtn--ghost" href="/games/leaderboard/?g=chess" data-g="leaderboard">Leaderboard</a>
        </div>
        <p id="ch-loading" class="games-note">Loading a puzzle.</p>
        <div id="ch-game" hidden>
          <p class="ch-turn" id="ch-turn"></p>
          <p class="ch-msg" id="ch-msg" role="status" aria-live="polite"></p>
          <div class="cb-board" id="ch-board" role="group" aria-label="Chess board"></div>
          <div class="ch-promo" id="ch-promo" hidden role="group" aria-label="Promote the pawn to">
            <span>Promote to</span>
            <button type="button" class="btn btn-ghost" data-p="q">Queen</button>
            <button type="button" class="btn btn-ghost" data-p="r">Rook</button>
            <button type="button" class="btn btn-ghost" data-p="b">Bishop</button>
            <button type="button" class="btn btn-ghost" data-p="n">Knight</button>
          </div>
          <div class="game-actions" id="ch-controls">
            <button type="button" class="btn btn-ghost" id="ch-giveup">Show solution</button>
          </div>
          <details class="ch-fen"><summary>Position as text (FEN)</summary><code id="ch-fen"></code></details>
          <section class="game-result rate-result" id="cr-result" hidden aria-labelledby="cr-head">
            <h2 id="cr-head"></h2>
            <p class="rate-delta" id="cr-delta" data-up="1" aria-live="polite"></p>
            <p class="rate-line">Rating <b id="cr-new"></b> <span id="cr-tier"></span></p>
            <div class="game-statline">
              <div><b id="cr-streak">0</b><span>Solved in a row</span></div>
              <div><b id="cr-peak">0</b><span>Peak rating</span></div>
            </div>
            <p class="game-reveal" id="cr-about"></p>
            <div class="rate-join" id="cr-join"></div>
            <aside class="partner" id="partner" hidden aria-label="Chess resources"></aside>
            <div class="game-actions">
              <a class="gbtn" id="cr-next" href="/games/chess-puzzles/" data-g="chess-puzzles">Next puzzle</a>
              <button type="button" class="btn btn-primary" id="cr-share">Share</button>
              <a class="gbtn gbtn--ghost" id="ch-game-link" href="https://lichess.org/training" rel="noopener">See it on Lichess</a>
              <span class="game-note" id="cr-share-note"></span>
            </div>
            <textarea class="wg-share-text" id="cr-share-text" hidden readonly aria-label="Result text"></textarea>
          </section>
        </div>
        <p class="ad-note">This page shows Google ads. They are how the unlimited puzzles stay free.</p>
        <div class="games-prose">
""" + CP_PROSE + """
        </div>
        <p class="games-note"><a href="/games/">All daily games</a></p>
      </div>"""
page("games/chess-puzzles/", "", "", CP_BODY,
     {"@context": "https://schema.org", "@graph": [faq(CP_FAQ)]},
     ["/games/core.js", "/games/ratings.js", "/games/partners.js", "/games/chess-puzzles.js"], ads=True)

# ---------------- Leaderboards ----------------
LB_FAQ = [
    ("Who appears on the leaderboards?", "Only signed-in players who turn the leaderboard on, under the display name they chose, on every board. Nothing else about them is shown. You can leave at any time and your row is removed."),
    ("What is the weekly board?", "It ranks players by how much their rating rose since Monday. A player needs at least three rated puzzles that week to appear, and the board starts fresh each Monday."),
    ("Can the daily boards be faked?", "The daily boards use the results your browser saves and reports, and the service only checks that they are possible: nobody can have more wins or a longer streak than the number of days a game has existed. That is weaker than the rating boards, so treat them as friendly competition. Percentiles are counted once per person per puzzle."),
    ("Can the ratings be faked?", "The rating service only accepts reports for real puzzles, in a plausible time, and works out each rating itself. However, a determined person could still use a chess engine. The daily Lockerlink results are checked for plausibility rather than replayed. Treat the boards as friendly competition."),
    ("How do I join?", "Play any daily game or a few rated puzzles, sign in with an email link on your account page, choose a display name, and turn on the leaderboard there or on this page."),
]
LB_RATED = [("chess", "Chess Puzzles"), ("lockerlink", "Lockerlink")]
LB_DAILY = [("linkle", "Linkle"), ("quadlink", "Quadlink"), ("crossword", "Crossword"), ("peaklink", "Peaklink"), ("lockerlink", "Lockerlink")]
LB_OPTIONS = ('<optgroup label="Daily games, all time">' + "".join(f'<option value="daily:{k}">{n}</option>' for k, n in LB_DAILY) + '</optgroup>'
              + '<optgroup label="Rated puzzles">' + "".join(f'<option value="rated:{k}">{n}</option>' for k, n in LB_RATED) + '</optgroup>')
LB_BODY = """      <div class="games-wrap">
        <div class="game-head">
          <h1>Leaderboards</h1>
          <span class="game-num" id="lb-week"></span>
        </div>
        <p class="game-lede">Who did best today on every daily game, plus all-time boards by wins, best streak and average percentile, and the rating boards for Chess Puzzles and Lockerlink.</p>
        <div class="lb-controls">
          <label class="lb-label" for="lb-game">Game</label>
          <select id="lb-game" class="lb-select">""" + LB_OPTIONS + """</select>
          <div class="lb-tabs" id="lb-boards" role="group" aria-label="Choose a board"></div>
        </div>
        <p class="games-note" id="lb-status" role="status" aria-live="polite">Loading the board.</p>
        <div class="lb-you" id="lb-you" hidden></div>
        <ol class="lb-list" id="lb-list" aria-label="Leaderboard"></ol>
        <p class="games-note" id="lb-note" hidden></p>
        <div class="rate-join" id="lb-join"></div>
        <div class="game-actions">
          <a class="gbtn" id="lb-play" href="/games/linkle/" data-g="linkle">Play today's puzzle</a>
          <a class="gbtn gbtn--ghost" href="/games/account/">Your account</a>
        </div>
        <div class="games-prose">
          <h2>How the boards work</h2>
          <p>Every daily game has a Today board, listing the best results on today\'s puzzle (and Yesterday\'s), plus three all-time boards. Wins counts the days you solved the puzzle. Best streak is your longest run of days in a row. Average percentile is how you ranked against everyone who played each day, and it counts after 20 days with a real crowd. Rank is worked out against every signed-in player, so you can see where you stand even when you are outside the top 100. Only players who opt in, under a display name, are listed.</p>
          <p>The rating boards are Elo ratings worked out by the rating service from the puzzles you finish. Chess Puzzles updates with every puzzle. Lockerlink updates once a day, from your first result on that day\'s puzzle, and a harder chain counts for more. Everyone starts at 1000.</p>
          <h2>Questions</h2>
""" + faq_html(LB_FAQ) + """
        </div>
        <p class="games-note"><a href="/games/">All daily games</a></p>
      </div>"""
page("games/leaderboard/", "", "", LB_BODY,
     {"@context": "https://schema.org", "@graph": [faq(LB_FAQ)]},
     ["/games/core.js", "/games/ratings.js", "/games/leaderboard.js"])


# ---------------- Attribute-guess games (Landlink, Atomlink, Prizelink) ----------------
def attr_page(slug, title, subject, faq_items, legend_extra, credit, art_key=None):
    faq_ = faq_items + [
        ("How do I read the colors?", "Purple means that column matches the answer. Striped yellow means close: a number within range, or related. Gray means no match. An arrow on a number points toward the answer: up if the answer is higher, down if it is lower."),
        ("How many guesses do I get?", "Eight on most days. After four wrong guesses a hint shows the first letter of the answer, and after six it also shows the length."),
        ("What are the weekday twists?", "Each day has its own rule. Monday is standard. Tuesday reveals one fact about the answer. Wednesday gives ten guesses. Thursday hides one column in your first three guesses. Friday turns the arrows off. Saturday gives only six guesses. Sunday is hard mode: every guess must be a possible answer given your clues."),
        ("When does a new puzzle appear?", "At midnight in your time zone, and everyone sees the same answer on the same date."),
        ("Do I need an account?", "No. Streaks and results are kept in your browser. Signing in with an email link keeps them on every device."),
    ]
    prose = f"""        <h2>How to play</h2>
        <p>Type {subject} and pick it from the list. The row that appears compares your guess with the mystery answer, one column at a time. Use the colors and arrows to rule things out, then guess again.</p>
        <div class="game-legend" aria-label="Color key">
          <span><i class="ag-key" data-s="c"></i> Same</span>
          <span><i class="ag-key" data-s="p"></i> Close or related</span>
          <span><i class="ag-key" data-s="a"></i> Different</span>
          <span><b class="ag-arrow">&uarr;</b> Answer is higher</span>
          <span><b class="ag-arrow">&darr;</b> Answer is lower</span>
        </div>
{legend_extra}
        <h2>Questions</h2>
""" + faq_html(faq_) + f"""
        <p class="quiz-credit">{credit}</p>"""
    body = f"""      <div class="games-wrap" id="ag-root" data-ds="{slug}" data-url="https://purplelink.llc/games/{slug}/">
        <div class="game-head">
          <h1 id="ag-title">{title}</h1>
          <span class="game-num" id="ag-number"></span>
        </div>
        <p class="game-lede">{title} is a free daily guessing game.</p>
        <p id="ag-loading" class="games-note">Loading today's puzzle.</p>
        <div id="ag-game" hidden>
          <p class="wg-twist" id="ag-twist" hidden><strong id="ag-twist-name"></strong> <span id="ag-twist-text"></span></p>
          <form class="ag-form" id="ag-form" autocomplete="off">
            <label for="ag-input" class="visually-hidden">Your guess</label>
            <div class="ag-combo">
              <input id="ag-input" type="text" role="combobox" aria-expanded="false" aria-controls="ag-list" aria-autocomplete="list" placeholder="Type to search" autocapitalize="off" spellcheck="false">
              <ul id="ag-list" role="listbox" aria-label="Matches" hidden></ul>
            </div>
            <button type="submit" class="gbtn">Guess</button>
          </form>
          <p class="ag-meta"><span id="ag-count"></span> <span id="ag-msg" role="status" aria-live="polite"></span></p>
          <p class="ag-hint" id="ag-hint" role="status"></p>
          <div class="ag-scroll" id="ag-wrap" hidden tabindex="0" role="region" aria-label="Your guesses. Scroll sideways to see every column.">
            <div class="ag-grid">
              <div class="ag-row ag-headrow" id="ag-head" aria-hidden="true"></div>
              <ol class="ag-rows" id="ag-rows" aria-label="Your guesses, newest first"></ol>
            </div>
          </div>
          <section class="game-result" id="ag-result" hidden aria-labelledby="ag-result-head">
            <h2 id="ag-result-head"></h2>
            <p class="game-reveal" id="ag-reveal"></p>
            <div class="game-statline">
              <div><b id="ag-played">0</b><span>Played</span></div>
              <div><b id="ag-winpct">0%</b><span>Win rate</span></div>
              <div><b id="ag-streak">0</b><span>Streak</span></div>
              <div><b id="ag-max">0</b><span>Best streak</span></div>
            </div>
            <p class="game-pct" id="ag-pct"></p>
            <p class="game-pct" id="ag-saver"></p>
            <div class="game-actions">
              <button type="button" class="btn btn-primary" id="ag-share">Copy result</button>
              <span class="game-note" id="ag-share-note"></span>
            </div>
            <textarea class="wg-share-text" id="ag-share-text" hidden readonly aria-label="Result text"></textarea>
            <p class="game-next">Next puzzle in <span id="ag-next-in"></span>. <span id="ag-tomorrow"></span></p>
          </section>
        </div>
        <div class="games-prose">
{prose}
        </div>
        <p class="games-note"><a href="/games/">All daily games</a></p>
      </div>"""
    page(f"games/{slug}/", "", "", body, {"@context": "https://schema.org", "@graph": [faq(faq_)]},
         ["/games/core.js", "/games/attrguess.js"])


attr_page("peaklink", "Peaklink", "a mountain", [
    ("Where does the data come from?", "From Wikidata (CC0): height, location and the countries each mountain lies in, for well-documented mountains."),
    ("Why do some mountains list two countries?", "Peaks on a border belong to both. Sharing one country shows as close."),
    ("What counts as a volcano?", "Wikidata marks it as a volcano as well as a mountain, for example Mount Fuji and Vesuvius."),
], "", "Mountain data: <a href=\"https://www.wikidata.org/\" rel=\"noopener\">Wikidata</a> (CC0). Continents from Natural Earth (public domain).")

# ---------------- Account ----------------
ACCT_BODY = """      <div class="games-wrap">
        <div class="game-head">
          <h1>Your games</h1>
          <span class="game-num" id="ac-who"></span>
        </div>
        <p class="game-lede">Your stats and achievements, and an optional sign-in that keeps them on every device.</p>
        <p id="ac-msg" class="games-note" role="status" aria-live="polite"></p>

        <section class="ac-card" id="ac-signin" hidden aria-labelledby="ac-signin-h">
          <h2 id="ac-signin-h">Sign in to keep your progress on every device</h2>
          <p class="games-note">You do not need an account to play. If you sign in, we email you a one-time link (no password). We store your email address, a display name and your saved game progress so they follow you between devices. You can delete all of it here at any time. See the <a href="/privacy/">privacy policy</a>.</p>
          <form id="ac-form" class="ac-form">
            <label for="ac-email">Email address</label>
            <input id="ac-email" name="email" type="email" autocomplete="email" required maxlength="254">
            <button type="submit" class="btn btn-primary" id="ac-send">Email me a sign-in link</button>
          </form>
        </section>

        <section class="ac-card" id="ac-profile" hidden aria-labelledby="ac-profile-h">
          <h2 id="ac-profile-h">Account</h2>
          <p class="games-note">Signed in as <strong id="ac-email-shown"></strong>.</p>
          <form id="ac-name-form" class="ac-form">
            <label for="ac-name">Display name</label>
            <input id="ac-name" name="name" type="text" maxlength="24" autocomplete="nickname">
            <button type="submit" class="btn btn-ghost">Save name</button>
          </form>
          <label class="ac-check"><input type="checkbox" id="ac-remind"> Email me in the evening if my streak is about to end (at most one email a day)</label>
          <label class="ac-check"><input type="checkbox" id="ac-public"> Show my display name and puzzle ratings on the <a href="/games/leaderboard/">leaderboards</a> (needs a display name)</label>
          <p class="games-note" id="ac-ratings"></p>
          <div class="game-actions">
            <button type="button" class="btn btn-ghost" id="ac-sync">Sync now</button>
            <button type="button" class="btn btn-ghost" id="ac-logout">Sign out</button>
            <button type="button" class="btn btn-ghost" id="ac-delete">Delete my account</button>
          </div>
          <p class="games-note" id="ac-delete-note" hidden>This permanently deletes your email address and saved progress from our servers and signs you out everywhere. Progress stored in this browser stays until you clear it. Press the button again to confirm.</p>
        </section>

        <section class="ac-card" aria-labelledby="ac-stats-h">
          <h2 id="ac-stats-h">Stats</h2>
          <div class="ac-table" id="ac-stats" tabindex="0" role="region" aria-label="Your stats. Scroll sideways to see every column."></div>
        </section>

        <section class="ac-card" aria-labelledby="ac-ach-h">
          <h2 id="ac-ach-h">Achievements <span id="ac-ach-count" class="games-note"></span></h2>
          <ul class="ac-ach" id="ac-ach"></ul>
        </section>
        <p class="games-note"><a href="/games/">All daily games</a></p>
      </div>"""
page("games/account/",
     "Your games: stats, achievements and sign-in | Purplelink",
     "Your stats and achievements across Purplelink's daily games, with an optional email-link sign-in that keeps them on every device.",
     ACCT_BODY,
     {"@context": "https://schema.org", "@graph": [
         crumbs(("Home", "https://purplelink.llc/"), ("Games", "https://purplelink.llc/games/"), ("Your games", "https://purplelink.llc/games/account/"))]},
     ["/games/core.js", "/games/sync.js", "/games/ratings.js", "/games/achievements.js", "/games/account.js"], robots="noindex, follow")

# ---------------- Sports games ----------------
SP_FORM = """          <form class="ag-form sp-form" id="sp-form" autocomplete="off">
            <label for="sp-input" class="visually-hidden">Player name</label>
            <div class="ag-combo">
              <input id="sp-input" type="text" role="combobox" aria-expanded="false" aria-controls="sp-list" aria-autocomplete="list" placeholder="Type a player's name" autocapitalize="off" spellcheck="false">
              <ul id="sp-list" role="listbox" aria-label="Matches" hidden></ul>
            </div>
            <button type="submit" class="gbtn">Add</button>
          </form>
          <p class="sp-msg" id="sp-msg" role="status" aria-live="polite"></p>"""

def sports_page(slug, title, lede, board, result_extra, prose, faq_items, scripts, diff=False, extra_modes="", under_lede="", extra_links=""):
    d = ('            <label class="sp-field">Difficulty <select id="sp-diff"><option value="easy">Easy</option><option value="medium" selected>Medium</option><option value="hard">Hard</option></select></label>\n' if diff else "")
    body = f"""      <div class="games-wrap sp" id="sp-root" data-ds="{slug}" data-url="https://purplelink.llc/games/{slug}/">
        <div class="game-head">
          <h1><img class="game-logo" src="/assets/games/{slug}.svg" alt="" width="44" height="44">{title}</h1>
          <span class="game-num" id="sp-number"></span>
        </div>
        <p class="game-lede">{lede}</p>
        <div class="sp-modes" role="group" aria-label="Mode">
          <button type="button" class="sp-mode" id="sp-mode-daily" aria-pressed="true">Daily</button>
          <button type="button" class="sp-mode" id="sp-mode-practice" aria-pressed="false">Practice</button>
{extra_modes}        </div>
{under_lede}
        <div class="sp-practice" id="sp-practice-opts" hidden>
            <label class="sp-field">Sport <select id="sp-sport"></select></label>
{d}            <button type="button" class="gbtn gbtn--ghost" id="sp-new">New puzzle</button>
        </div>
        <p id="sp-loading" class="games-note">Loading today's puzzle.</p>
        <div id="sp-game" hidden>
{board}
          <section class="game-result" id="sp-result" hidden aria-labelledby="sp-result-head">
            <h2 id="sp-result-head"></h2>
            <p class="game-reveal" id="sp-reveal"></p>
{result_extra}
            <div class="game-statline" id="sp-statline">
              <div><b id="sp-played">0</b><span>Played</span></div>
              <div><b id="sp-winpct">0%</b><span>Win rate</span></div>
              <div><b id="sp-streak">0</b><span>Streak</span></div>
              <div><b id="sp-max">0</b><span>Best streak</span></div>
            </div>
            <p class="game-pct" id="sp-pct"></p>
            <p class="game-pct" id="sp-rating"></p>
            <p class="game-pct"><a id="sp-lb" href="/games/leaderboard/" hidden>See the leaderboard and join it</a></p>
            <p class="game-pct" id="sp-saver"></p>
            <div class="game-actions">
              <button type="button" class="btn btn-primary" id="sp-share">Copy result</button>
              <button type="button" class="gbtn gbtn--ghost" id="sp-practice-again" hidden>Another puzzle</button>
              <span class="game-note" id="sp-share-note"></span>
            </div>
            <textarea class="wg-share-text" id="sp-share-text" hidden readonly aria-label="Result text"></textarea>
            <p class="game-next" id="sp-next-line">Next puzzle in <span id="sp-next-in"></span>.</p>
          </section>
        </div>
        <div class="games-prose">
{prose}
        </div>
        <p class="games-note">{extra_links}<a href="/games/">All daily games</a></p>
      </div>"""
    page(f"games/{slug}/", "", "", body, {"@context": "https://schema.org", "@graph": [faq(faq_items)]}, scripts)

SP_NOTE = ("Players come from lists we curated of well-known stars in each league, with team histories checked against Wikipedia and Wikidata. "
           "A player counts as a teammate when the two were on the same franchise in the same season; a team that moved or changed its name is one franchise. "
           'Baseball data comes from the <a href="https://sabr.org/lahman-database/" rel="noopener">Lahman Baseball Database</a>, copyright 1996-2025 SABR, via Sean Lahman, used under <a href="https://creativecommons.org/licenses/by-sa/3.0/" rel="noopener">CC BY-SA 3.0</a>. '
           "We matched it to our own player list and combined it with other sources, so it is changed from the original.")

TL_FAQ = [
    ("What counts as teammates?", "Two players are teammates if they were on the same franchise in at least one common season. A franchise that moved or changed its name counts as one team, so the Seattle SuperSonics and the Oklahoma City Thunder are the same club."),
    ("Which players can I use?", "Any player who ever appeared for a team in that league, from the first seasons to 2025: about 5,000 in the NBA, 27,000 in the NFL, 20,000 in MLB and 9,000 in the NHL. The two players you are asked to link are always well-known stars, but the players in between can be anyone. Coverage is not perfect: NBA and NHL rosters come from Wikipedia and miss some players, clubs that no longer exist are left out, and NFL rosters include some players who were on a roster without playing."),
    ("What is par?", "Par is the fewest links needed to connect the two players, measured over every player in our database. The chain is solved when its two ends are teammates."),
    ("What is the Rival mode?", "Finish a puzzle and press Challenge a friend. It makes a link to the same two players with your result in it, and sends or copies it. When your friend opens the link they get that pair in Rival mode and see who linked it better: fewer links wins, and misses and hints break a tie. Rival games do not touch your streak, rating or stats. The section This week's rivals lists the challenges you answered this week and how many you sent. Everything stays on your device, and nothing is stored on our side."),
    ("Where can I see the shortest chain?", "On the result card right after you finish, and in the section under the puzzle called This week's shortest chains. It lists every puzzle so far this week with its shortest possible chain, the team and seasons that link each pair of players, and how you did. Last week is kept in a drop-down. Today's chain appears once you finish today's puzzle, or tomorrow."),
    ("How do the two ends work?", "You can add a player next to the first player or next to the last player. If a player is a teammate of both ends, the chain closes."),
    ("How are stars awarded?", "Three stars for matching par with no hints and at most two misses, two stars for par plus one, one star for anything longer."),
    ("Which sport is it today?", "The daily puzzle rotates through the NBA, NFL, MLB and NHL. Practice mode lets you pick any sport and a difficulty."),
    ("Is there a rating or a leaderboard?", "Yes. Each day you finish counts once toward a running Elo rating for this game, starting at 1000, and it is worked out by the rating service from your result and the difficulty of that day's puzzle. Without an account the rating stays on this device. Signed-in players can opt in to the all-time and weekly leaderboards under a display name."),
]
TL_PROSE = f"""        <h2>How to play</h2>
        <p>You are given two players, often from different eras. Build a chain of teammates between them. Type a player who shared a team and a season with either end of your chain and pick the name from the list.</p>
        <p>A wrong name counts as a miss. Undo removes the last player you added, and a hint names the team of a good next link, then the player's initials. Par is the shortest chain possible.</p>
        <p class="quiz-credit">{SP_NOTE} Football rosters come from <a href="https://github.com/nflverse/nflverse-data" rel="noopener">nflverse</a> (<a href="https://creativecommons.org/licenses/by/4.0/" rel="noopener">CC BY 4.0</a>). Basketball and hockey rosters come from Wikipedia and its players' pages (<a href="https://creativecommons.org/licenses/by-sa/4.0/" rel="noopener">CC BY-SA 4.0</a>). All of it was matched and merged by us.</p>
        <h2>Questions</h2>
""" + faq_html(TL_FAQ)
TL_BOARD = """          <div class="tl-ends" aria-label="The two players to link">
            <p><span class="tl-end-label">From</span> <strong id="tl-from"></strong></p>
            <p><span class="tl-end-label">To</span> <strong id="tl-to"></strong></p>
          </div>
          <ol class="tl-chain" id="sp-chain" aria-label="Your chain"></ol>
""" + SP_FORM + """
          <div class="sp-tools">
            <button type="button" class="gbtn gbtn--ghost" id="tl-undo">Undo</button>
            <button type="button" class="gbtn gbtn--ghost" id="tl-hint">Hint</button>
            <button type="button" class="gbtn gbtn--ghost" id="tl-giveup">Give up</button>
          </div>
          <p class="sp-count"><span>Links <b id="sp-links">1</b></span> <span>Par <b id="sp-par">?</b></span> <span>Misses <b id="sp-misses">0</b></span> <span>Hints <b id="sp-hints">0</b></span></p>
          <section class="tl-week" id="tl-week" hidden aria-labelledby="tl-week-h">
            <h2 id="tl-week-h">This week's shortest chains</h2>
            <p class="games-note">The shortest possible chain for each day's puzzle so far this week, with the team and seasons of every link. Today's appears once you finish it.</p>
            <ul class="tw-list" id="tl-week-list"></ul>
            <details id="tl-week-prev-wrap" hidden><summary>Last week</summary><ul class="tw-list" id="tl-week-prev"></ul></details>
          </section>
          <section class="tl-week" id="tl-rivals" hidden aria-labelledby="tl-rivals-h">
            <h2 id="tl-rivals-h">This week's rivals</h2>
            <p class="games-note" id="tl-rivals-sum"></p>
            <ul class="tw-list" id="tl-rivals-list"></ul>
          </section>"""
TL_RESULT = """            <p class="game-pct" id="sp-star"></p>
            <p class="game-pct" id="tl-rival-result" hidden></p>
            <div class="game-actions">
              <button type="button" class="gbtn" id="tl-challenge" hidden>Challenge a friend</button>
              <span class="game-note" id="tl-challenge-note"></span>
            </div>"""
sports_page("lockerlink", "Lockerlink", "Link two players from any era through the teammates they shared.", TL_BOARD,
            TL_RESULT, TL_PROSE, TL_FAQ,
            ["/games/core.js", "/games/ratings.js", "/games/sports.js", "/games/lockerlink.js"], diff=True,
            extra_modes='          <button type="button" class="sp-mode" id="sp-mode-rival" aria-pressed="false" hidden>Rival</button>\n',
            under_lede='        <p class="wg-twist" id="tl-rival-banner" hidden></p>')

# ---------------- Hub ----------------
# The /games/ hub page is maintained by hand since the 2026-11-12 games freeze; this script no longer writes it.
# Retired games (Daily Five, Daily Photo, Daily Chess, Sudoku, Sudoku Unlimited, Daily Stars, the attribute-guess
# games except Peaklink, Gridlink, Under the Cap, Tanklink and the sports hub) 301 to /games/ in netlify.toml.
# Do not add page() calls for them: a file at a redirected path disables the redirect.
