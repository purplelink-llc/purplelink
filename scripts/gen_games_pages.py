import json, html, re, sys
from datetime import date
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from games_meta import GAMES as META, HUB as HUBMETA, FOUNDED
SITE = Path(__file__).resolve().parent.parent / "site"
TODAY = date.today().isoformat()
ORG = {"@type": "Organization", "@id": "https://purplelink.llc/#organization", "name": "Purplelink LLC", "url": "https://purplelink.llc/"}
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


def page(path, title, desc, body, jsonld, scripts, og_title=None, robots="index, follow"):
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
    <meta name="theme-color" content="#7c3aed">
    <link rel="preload" href="/assets/fonts/fraunces-latin.woff2" as="font" type="font/woff2" crossorigin>
    <link rel="preload" href="/assets/fonts/plus-jakarta-sans-latin.woff2" as="font" type="font/woff2" crossorigin>
    <script src="/theme.js"></script>
    <link rel="stylesheet" href="/styles.css">
    <link rel="stylesheet" href="/motion.css">
    <link rel="stylesheet" href="/games/games.css">
    <script src="/site.js" defer></script>
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

    <main id="main-content" class="games">
{body}
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
              <span class="game-note" id="wg-share-note"></span>
            </div>
            <textarea class="wg-share-text" id="wg-share-text" hidden readonly aria-label="Result text"></textarea>
            <p class="game-next">Next puzzle in <span id="wg-next"></span>.</p>
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
        <h2>Questions</h2>
""" + faq_html(QUAD_FAQ)

page("games/quadlink/",
     "Quadlink: a free daily four-board word game | Purplelink",
     "Solve four five-letter words at once in nine guesses. A new puzzle every day, free, with no third-party ads.",
     WORD_UI.format(h1="Quadlink", boards=4, lede="Four five-letter words at once. Nine guesses.", prose=QUAD_PROSE, twist="", meta=""),
     {"@context": "https://schema.org", "@graph": [
         game_app("Quadlink", "https://purplelink.llc/games/quadlink/", "A free daily word game where you solve four five-letter words at once in nine guesses."),
         faq(QUAD_FAQ),
         crumbs(("Home", "https://purplelink.llc/"), ("Games", "https://purplelink.llc/games/"), ("Quadlink", "https://purplelink.llc/games/quadlink/"))]},
     ["/games/core.js", "/games/sync.js", "/games/achievements.js", "/games/confetti.js", "/games/config-quadlink.js", "/games/wordgame.js"])

(SITE / "games/config-linkle.js").write_text('window.PLWordGame = { name: "linkle", title: "Linkle", boards: 1, maxGuesses: 6, dataFile: "linkle.json", url: "https://purplelink.llc/games/linkle/", twists: true };\n')
(SITE / "games/config-quadlink.js").write_text('window.PLWordGame = { name: "quadlink", title: "Quadlink", boards: 4, maxGuesses: 9, dataFile: "quadlink.json", url: "https://purplelink.llc/games/quadlink/" };\n')


# ---------------- Daily Five ----------------
DF_FAQ = [
    ("How many questions are there?", "Five multiple-choice questions a day, with one correct answer each. Two come from a set we write about science, computing, research methods and Macs. Three come from a general trivia pool."),
    ("When do the questions change?", "At midnight in your time zone. Everyone sees the same five on the same date."),
    ("Where do the questions come from?", "Part of the pool is the Open Trivia Database, licensed CC BY-SA 4.0. The rest we write ourselves. We check our own questions, but a general trivia pool can contain mistakes. If you spot one, email ben@purplelink.llc."),
    ("What counts as my streak?", "Finishing the day's five questions, whatever your score. Your streak and scores stay in this browser only."),
]
DF_PROSE = """        <h2>How it works</h2>
        <p>Pick one answer for each question. You see right away whether you were correct, then move on. After the fifth question you get your score and a result you can copy and share. You cannot change an answer once you choose it.</p>
        <h2>Questions</h2>
""" + faq_html(DF_FAQ) + """
        <p class="quiz-credit">Some questions come from the <a href="https://opentdb.com/" rel="noopener">Open Trivia Database</a>, used under <a href="https://creativecommons.org/licenses/by-sa/4.0/" rel="noopener">CC BY-SA 4.0</a>. Questions we wrote ourselves are shared under the same licence.</p>"""
DF_BODY = """      <div class="games-wrap">
        <div class="game-head">
          <h1>Daily Five</h1>
          <span class="game-num" id="qz-number"></span>
        </div>
        <p class="game-lede">Five trivia questions a day: science, computing, research and a little of everything else.</p>
        <p id="qz-loading" class="games-note">Loading today's questions.</p>
        <div id="qz-game" hidden>
          <div class="quiz" id="qz-quiz" hidden>
            <p class="quiz-progress" id="qz-progress"></p>
            <div class="quiz-dots" id="qz-dots" aria-hidden="true"></div>
            <p class="quiz-cat" id="qz-cat"></p>
            <h2 class="quiz-q" id="qz-q"></h2>
            <ul class="quiz-opts" id="qz-opts"></ul>
            <p class="quiz-note" id="qz-note" role="status" aria-live="polite"></p>
            <button type="button" class="btn btn-primary" id="qz-next" hidden>Next question</button>
          </div>
          <section class="game-result" id="qz-result" hidden aria-labelledby="qz-result-head">
            <h2 id="qz-result-head"></h2>
            <div class="game-statline">
              <div><b id="qz-played">0</b><span>Days played</span></div>
              <div><b id="qz-avg">0.0</b><span>Average score</span></div>
              <div><b id="qz-streak">0</b><span>Streak</span></div>
              <div><b id="qz-max">0</b><span>Best streak</span></div>
            </div>
            <div class="wg-dist" id="qz-dist"></div>
            <p class="game-pct" id="qz-pct"></p>
            <p class="game-pct" id="qz-saver"></p>
            <ul class="quiz-review" id="qz-review"></ul>
            <div class="game-actions">
              <button type="button" class="btn btn-primary" id="qz-share">Copy result</button>
              <span class="game-note" id="qz-share-note"></span>
            </div>
            <textarea class="wg-share-text" id="qz-share-text" hidden readonly aria-label="Result text"></textarea>
            <p class="game-next">Next quiz in <span id="qz-next-in"></span>.</p>
          </section>
        </div>
        <div class="games-prose">
""" + DF_PROSE + """
        </div>
        <p class="games-note"><a href="/games/">All daily games</a></p>
      </div>"""
page("games/daily-five/",
     "Daily Five: a free daily trivia quiz | Purplelink",
     "Five trivia questions a day on science, computing, research and more. Free, with no third-party ads. You do not need an account.",
     DF_BODY,
     {"@context": "https://schema.org", "@graph": [
         game_app("Daily Five", "https://purplelink.llc/games/daily-five/", "A free daily five-question trivia quiz."),
         faq(DF_FAQ),
         crumbs(("Home", "https://purplelink.llc/"), ("Games", "https://purplelink.llc/games/"), ("Daily Five", "https://purplelink.llc/games/daily-five/"))]},
     ["/games/core.js", "/games/sync.js", "/games/achievements.js", "/games/confetti.js", "/games/daily-five.js"])


# ---------------- Daily Stars ----------------
ST_FAQ = [
    ("Are these real predictions?", "No. Daily Stars is written for entertainment. It is a short, ordinary suggestion for the day with a nod to the moon and the weekday. It does not predict anything and it is not advice about health, money or relationships."),
    ("How are the readings made?", "They are written ahead of time in batches, one short reading per sign per day, and published on the date. The moon phase shown is calculated from the date and is accurate to about half a day."),
    ("When do they change?", "At midnight in your time zone."),
    ("Is anything stored about me?", "Your chosen sign, in this browser. If you sign in with an email link, it follows you between devices."),
]
ST_PROSE = """        <h2>About these readings</h2>
        <p>Daily Stars gives each sign a short suggestion for the day. They are meant to be read in a few seconds. Nothing here is a forecast, and no reading is advice about health, money or relationships.</p>
        <h2>Questions</h2>
""" + faq_html(ST_FAQ)
ST_BODY = """      <div class="games-wrap">
        <div class="game-head">
          <h1>Daily Stars</h1>
          <span class="game-num" id="st-date"></span>
        </div>
        <p class="game-lede">A short reading for each sign, new every day. For entertainment only.</p>
        <p id="st-loading" class="games-note">Loading today's readings.</p>
        <p id="st-missing" class="games-note" hidden>Today's readings are not ready yet. Please check back soon.</p>
        <div id="st-game" hidden>
          <p class="stars-sky" id="st-sky"></p>
          <ul class="stars-signs" id="st-signs" aria-label="Choose your sign"></ul>
          <section class="stars-card" id="st-card" hidden aria-live="polite">
            <h2 id="st-name"></h2>
            <p class="stars-sub" id="st-range"></p>
            <p id="st-text"></p>
          </section>
          <div class="stars-all">
            <h2>All signs today</h2>
            <div id="st-all"></div>
          </div>
        </div>
        <div class="games-prose">
""" + ST_PROSE + """
        </div>
        <p class="games-note"><a href="/games/">All daily games</a></p>
      </div>"""
page("games/daily-stars/",
     "Daily Stars: a short daily horoscope for every sign | Purplelink",
     "A short, plain daily reading for each of the twelve signs, written for entertainment. Free, with no third-party ads.",
     ST_BODY,
     {"@context": "https://schema.org", "@graph": [
         {"@type": "WebApplication", "name": "Daily Stars", "url": "https://purplelink.llc/games/daily-stars/", "applicationCategory": "EntertainmentApplication",
          "operatingSystem": "Any (web-based)", "browserRequirements": "Requires JavaScript",
          "description": "A short daily reading for each of the twelve signs, for entertainment only.",
          "offers": {"@type": "Offer", "price": "0", "priceCurrency": "USD"},
          "provider": {"@type": "Organization", "name": "Purplelink LLC", "url": "https://purplelink.llc/"}},
         faq(ST_FAQ),
         crumbs(("Home", "https://purplelink.llc/"), ("Games", "https://purplelink.llc/games/"), ("Daily Stars", "https://purplelink.llc/games/daily-stars/"))]},
     ["/games/core.js", "/games/sync.js", "/games/achievements.js", "/games/daily-stars.js"])


# ---------------- Crossword ----------------
CW_FAQ = [
    ("Is there a new crossword every day?", "Yes. A new themeless puzzle is ready at midnight your time. Monday is the easiest and Sunday the hardest, with bigger grids and trickier clues as the week goes on."),
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
        <p class="game-lede">A new themeless crossword every day. Easiest on Monday, hardest on Sunday.</p>
        <p id="cw-loading" class="games-note">Loading today's crossword.</p>
        <p id="cw-missing" class="games-note" hidden>Today's crossword is not ready yet. Please check back soon.</p>
        <div id="cw-game" hidden>
          <div class="cw-layout">
            <div class="cw-main">
              <div class="cw-bar" role="group" aria-label="Check and reveal">
                <span class="cw-bar-label">Check</span>
                <button type="button" class="btn btn-ghost" id="cw-check-letter">Letter</button>
                <button type="button" class="btn btn-ghost" id="cw-check-word">Word</button>
                <button type="button" class="btn btn-ghost" id="cw-check">Puzzle</button>
                <button type="button" class="btn btn-ghost" id="cw-auto" aria-pressed="false">Auto-check: off</button>
                <span class="cw-timer" id="cw-timer" aria-label="Elapsed time">0:00</span>
              </div>
              <div class="cw-bar" role="group" aria-label="Reveal answers">
                <span class="cw-bar-label">Reveal</span>
                <button type="button" class="btn btn-ghost" id="cw-reveal-letter">Letter</button>
                <button type="button" class="btn btn-ghost" id="cw-reveal-word">Word</button>
                <button type="button" class="btn btn-ghost" id="cw-reveal-puzzle">Reveal puzzle</button>
              </div>
              <p class="cw-current" id="cw-current" aria-live="polite"></p>
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
                <p class="game-next">Next crossword in <span id="cw-next-in"></span>.</p>
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
     "A new free crossword every day, easiest on Monday and hardest on Sunday. No third-party ads, and you do not need an account.",
     CW_BODY,
     {"@context": "https://schema.org", "@graph": [
         game_app("Daily Crossword", "https://purplelink.llc/games/crossword/", "A free daily themeless crossword that gets harder from Monday to Sunday."),
         faq(CW_FAQ),
         crumbs(("Home", "https://purplelink.llc/"), ("Games", "https://purplelink.llc/games/"), ("Daily Crossword", "https://purplelink.llc/games/crossword/"))]},
     ["/games/core.js", "/games/sync.js", "/games/achievements.js", "/games/confetti.js", "/games/crossword.js"])



# ---------------- Daily Photo ----------------
PH_FAQ = [
    ("What is Daily Photo?", "Five photographs a day, each taken by Ben Ampel on his travels. For each one you pick which of four countries it was taken in. After every answer you see the exact place, a short description and a link to more photographs from there."),
    ("Where do the photographs come from?", "They are Purplelink's own photographs from Iceland, Japan, Switzerland, the United Kingdom, Germany, Denmark, the Netherlands, Canada, Panama and the United States. They are also available to license through the photography pages."),
    ("When do the photographs change?", "At midnight in your time zone. Everyone sees the same five on the same date."),
    ("What counts as my streak?", "Finishing the day's five photographs, whatever your score. Your streak and scores are saved in this browser, or on your account if you sign in with an email link."),
]
PH_PROSE = """        <h2>How it works</h2>
        <p>Look at the photograph, pick the country you think it was taken in, and see the answer straight away. After the fifth photograph you get your score and a result you can copy and share.</p>
        <h2>Questions</h2>
""" + faq_html(PH_FAQ)
PH_BODY = """      <div class="games-wrap">
        <div class="game-head">
          <h1>Daily Photo</h1>
          <span class="game-num" id="ph-number"></span>
        </div>
        <p class="game-lede">Five photographs, five countries. Where in the world was each one taken?</p>
        <p id="ph-loading" class="games-note">Loading today's photographs.</p>
        <div id="ph-game" hidden>
          <div class="quiz" id="ph-quiz" hidden>
            <p class="quiz-progress" id="ph-progress"></p>
            <div class="quiz-dots" id="ph-dots" aria-hidden="true"></div>
            <img class="ph-photo" id="ph-img" alt="Today's photograph. Its description appears after you answer." width="1200" height="800" decoding="async">
            <p class="quiz-cat">Which country?</p>
            <ul class="quiz-opts" id="ph-opts"></ul>
            <div class="ph-reveal" id="ph-reveal" hidden>
              <p class="ph-where" id="ph-where"></p>
              <p id="ph-caption"></p>
              <p><a id="ph-more" href="/photography/">More photographs</a></p>
            </div>
            <button type="button" class="btn btn-primary" id="ph-next" hidden>Next photo</button>
          </div>
          <section class="game-result" id="ph-result" hidden aria-labelledby="ph-result-head">
            <h2 id="ph-result-head"></h2>
            <div class="game-statline">
              <div><b id="ph-played">0</b><span>Days played</span></div>
              <div><b id="ph-avg">0.0</b><span>Average score</span></div>
              <div><b id="ph-streak">0</b><span>Streak</span></div>
              <div><b id="ph-max">0</b><span>Best streak</span></div>
            </div>
            <p class="game-pct" id="ph-pct"></p>
            <p class="game-pct" id="ph-saver"></p>
            <ul class="quiz-review" id="ph-review"></ul>
            <div class="game-actions">
              <button type="button" class="btn btn-primary" id="ph-share">Copy result</button>
              <span class="game-note" id="ph-share-note"></span>
            </div>
            <textarea class="wg-share-text" id="ph-share-text" hidden readonly aria-label="Result text"></textarea>
            <p class="game-next">Next set in <span id="ph-next-in"></span>.</p>
          </section>
        </div>
        <div class="games-prose">
""" + PH_PROSE + """
        </div>
        <p class="games-note"><a href="/games/">All daily games</a></p>
      </div>"""
page("games/daily-photo/",
     "Daily Photo: guess the country in five photographs | Purplelink",
     "Five photographs a day from Purplelink's own travel photography. Pick the country for each one. Free, with no third-party ads. You do not need an account.",
     PH_BODY,
     {"@context": "https://schema.org", "@graph": [
         game_app("Daily Photo", "https://purplelink.llc/games/daily-photo/", "A free daily game: pick the country each of five travel photographs was taken in."),
         faq(PH_FAQ),
         crumbs(("Home", "https://purplelink.llc/"), ("Games", "https://purplelink.llc/games/"), ("Daily Photo", "https://purplelink.llc/games/daily-photo/"))]},
     ["/games/core.js", "/games/sync.js", "/games/achievements.js", "/games/confetti.js", "/games/daily-photo.js"])


# ---------------- Daily Chess ----------------
CH_FAQ = [
    ("Where do the chess puzzles come from?", "From the Lichess puzzle database, which is released under the Creative Commons CC0 licence. Each puzzle starts from a position in a real game, and Lichess rates its difficulty from how many players have solved it."),
    ("How does the difficulty change through the week?", "Monday's puzzle comes from the easiest rating band, roughly 800 to 1250, and each day is harder than the last. Sunday's comes from the 2150 to 2600 band."),
    ("What counts as a slip?", "A wrong move or a hint. You can keep trying after a wrong move, but your result shows the number of slips, and a clean solve has none."),
    ("Do I have to find the exact solution?", "You have to find the puzzle's solution move by move, with one exception: any move that gives checkmate is accepted."),
    ("Can I see the solution?", "Yes. Show solution plays it out on the board, and the puzzle then counts as not solved for today."),
    ("What is the rating shown on the page?", "It is the Lichess puzzle rating. Players rated near that number solve the puzzle about half the time."),
    ("Do I need an account?", "No. Signing in is optional and only keeps your streak and achievements on every device."),
]
CH_PROSE = """        <h2>How to play</h2>
        <p>The position shows a game where the opponent has just moved. Find the best move for the side shown at the bottom of the board. Click a piece to see where it can go, then click the square. After a correct move the opponent replies and you continue until the puzzle is won.</p>
        <h2>Questions</h2>
""" + faq_html(CH_FAQ) + """
        <p class="quiz-credit">Puzzles come from the <a href="https://database.lichess.org/#puzzles" rel="noopener">Lichess puzzle database</a>, released under CC0. Chess rules are handled by <a href="https://github.com/jhlywa/chess.js" rel="noopener">chess.js</a>, used under its BSD licence.</p>"""
CH_BODY = """      <div class="games-wrap">
        <div class="game-head">
          <h1>Daily Chess</h1>
          <span class="game-num" id="ch-number"></span>
        </div>
        <p class="game-lede">Daily Chess is a free daily chess tactics puzzle.</p>
        <p id="ch-loading" class="games-note">Loading today's puzzle.</p>
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
            <button type="button" class="btn btn-ghost" id="ch-hint">Hint</button>
            <button type="button" class="btn btn-ghost" id="ch-giveup">Show solution</button>
          </div>
          <details class="ch-fen"><summary>Position as text (FEN)</summary><code id="ch-fen"></code></details>
          <section class="game-result" id="ch-result" hidden aria-labelledby="ch-result-head">
            <h2 id="ch-result-head"></h2>
            <p class="game-reveal" id="ch-about"></p>
            <div class="game-statline">
              <div><b id="ch-played">0</b><span>Played</span></div>
              <div><b id="ch-won">0</b><span>Solved</span></div>
              <div><b id="ch-streak">0</b><span>Streak</span></div>
              <div><b id="ch-max">0</b><span>Best streak</span></div>
            </div>
            <p class="game-pct" id="ch-pct"></p>
            <p class="game-pct" id="ch-saver"></p>
            <div class="game-actions">
              <button type="button" class="btn btn-primary" id="ch-share">Copy result</button>
              <a class="btn btn-ghost" id="ch-game-link" href="https://lichess.org/training" rel="noopener">See this puzzle on Lichess</a>
              <span class="game-note" id="ch-share-note"></span>
            </div>
            <textarea class="wg-share-text" id="ch-share-text" hidden readonly aria-label="Result text"></textarea>
            <p class="game-next">Next puzzle in <span id="ch-next-in"></span>.</p>
          </section>
        </div>
        <div class="games-prose">
""" + CH_PROSE + """
        </div>
        <p class="games-note"><a href="/games/">All daily games</a></p>
      </div>"""
page("games/daily-chess/", "", "", CH_BODY,
     {"@context": "https://schema.org", "@graph": [faq(CH_FAQ)]},
     ["/games/core.js", "/games/sync.js", "/games/achievements.js", "/games/confetti.js", "/games/daily-chess.js"])

# ---------------- Sudoku ----------------
SD_FAQ = [
    ("How hard is each week's Sudoku?", "Difficulty rises every week across a ten-week season. Weeks 1 and 2 are Beginner, weeks 3 and 4 Easy, weeks 5 and 6 Medium, weeks 7 and 8 Hard and weeks 9 and 10 Expert. After week 10 a new season starts again at Beginner."),
    ("Does every puzzle have exactly one solution?", "Yes. Each puzzle is generated by removing digits from a complete grid one pair at a time, and a solver confirms that exactly one solution remains."),
    ("How is the difficulty decided?", "By the techniques a person needs to solve the puzzle without guessing. Beginner needs only singles. Easy adds locked candidates, Medium adds pairs and triples, Hard needs X-Wing, and Expert needs a forced guess to get started."),
    ("What do Check and Auto-check do?", "Duplicate digits in a row, column or box turn red automatically. Check tests one square or the whole grid against the solution. Auto-check flags a wrong digit the moment you type it. Using Check, Auto-check or Reveal is shown as solving with help."),
    ("What are notes?", "Notes let you pencil small candidate digits into a square without committing to them. When you place a digit, matching notes in its row, column and box are cleared."),
    ("Is there a time limit?", "No. A timer runs while the page is open and visible, and only unaided solves count toward your best time for each difficulty level."),
    ("Do I need an account?", "No. Signing in is optional and keeps your streak, best times and achievements on every device."),
]
SD_WEEKS = [("1 to 2", "Beginner", "Only singles are needed. Many digits are given."), ("3 to 4", "Easy", "Adds locked candidates (pointing and claiming)."),
            ("5 to 6", "Medium", "Adds naked and hidden pairs and triples."), ("7 to 8", "Hard", "Adds X-Wing patterns."), ("9 to 10", "Expert", "Needs a forced guess to get started. Fewest digits given.")]
SD_PROSE = """        <h2>How it works</h2>
        <p>Fill the grid so every row, column and 3 by 3 box contains the digits 1 to 9 once. Click a square and type a digit, or use the number pad. Duplicates turn red as you go.</p>
        <h2>Difficulty by week of the season</h2>
        <table class="games-table">
          <thead><tr><th>Weeks</th><th>Level</th><th>What it needs</th></tr></thead>
          <tbody>
""" + "\n".join(f"            <tr><td>{w}</td><td>{l}</td><td>{d}</td></tr>" for w, l, d in SD_WEEKS) + """
          </tbody>
        </table>
        <h2>Questions</h2>
""" + faq_html(SD_FAQ)
SD_BODY = """      <div class="games-wrap">
        <div class="game-head">
          <h1>Sudoku</h1>
          <span class="game-num" id="sd-number"></span>
        </div>
        <p class="game-lede">Daily Sudoku is a free daily puzzle that gets harder every week.</p>
        <p id="sd-loading" class="games-note">Loading today's puzzle.</p>
        <div id="sd-game" hidden>
          <div class="sd-layout">
            <div class="sd-main">
              <div class="cw-bar" role="group" aria-label="Notes and checking">
                <button type="button" class="btn btn-ghost" id="sd-notes-btn" aria-pressed="false">Notes: off</button>
                <button type="button" class="btn btn-ghost" id="sd-check-cell">Check square</button>
                <button type="button" class="btn btn-ghost" id="sd-check">Check puzzle</button>
                <button type="button" class="btn btn-ghost" id="sd-auto" aria-pressed="false">Auto-check: off</button>
                <button type="button" class="btn btn-ghost" id="sd-reveal">Reveal square</button>
                <span class="cw-timer" id="sd-timer" aria-label="Elapsed time">0:00</span>
              </div>
              <p class="sd-level">Level: <strong id="sd-level"></strong>, week <span id="sd-week"></span> of 10</p>
              <div class="sd-grid" id="sd-grid" role="group" aria-label="Sudoku grid"></div>
              <p class="cw-status" id="sd-status" role="status" aria-live="polite"></p>
              <div class="sd-pad" id="sd-pad" aria-label="Number pad">
                <button type="button" class="wg-key" data-d="1">1</button><button type="button" class="wg-key" data-d="2">2</button><button type="button" class="wg-key" data-d="3">3</button>
                <button type="button" class="wg-key" data-d="4">4</button><button type="button" class="wg-key" data-d="5">5</button><button type="button" class="wg-key" data-d="6">6</button>
                <button type="button" class="wg-key" data-d="7">7</button><button type="button" class="wg-key" data-d="8">8</button><button type="button" class="wg-key" data-d="9">9</button>
                <button type="button" class="wg-key wg-wide" id="sd-erase">Erase</button>
              </div>
            </div>
          </div>
          <section class="game-result" id="sd-result" hidden aria-labelledby="sd-result-head">
            <h2 id="sd-result-head"></h2>
            <div class="game-statline">
              <div><b id="sd-played">0</b><span>Solved</span></div>
              <div><b id="sd-streak">0</b><span>Streak</span></div>
              <div><b id="sd-max">0</b><span>Best streak</span></div>
              <div><b id="sd-best">none</b><span id="sd-best-label">Best time</span></div>
            </div>
            <p class="game-pct" id="sd-pct"></p>
            <p class="game-pct" id="sd-saver"></p>
            <div class="game-actions">
              <button type="button" class="btn btn-primary" id="sd-share">Copy result</button>
              <span class="game-note" id="sd-share-note"></span>
            </div>
            <textarea class="wg-share-text" id="sd-share-text" hidden readonly aria-label="Result text"></textarea>
            <p class="game-next">Next puzzle in <span id="sd-next-in"></span>.</p>
          </section>
        </div>
        <div class="games-prose">
""" + SD_PROSE + """
        </div>
        <p class="games-note"><a href="/games/">All daily games</a></p>
      </div>"""
page("games/sudoku/", "", "", SD_BODY,
     {"@context": "https://schema.org", "@graph": [faq(SD_FAQ)]},
     ["/games/core.js", "/games/sync.js", "/games/achievements.js", "/games/confetti.js", "/games/sudoku.js"])

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
          <div class="game-actions">
            <button type="button" class="btn btn-ghost" id="ac-sync">Sync now</button>
            <button type="button" class="btn btn-ghost" id="ac-logout">Sign out</button>
            <button type="button" class="btn btn-ghost" id="ac-delete">Delete my account</button>
          </div>
          <p class="games-note" id="ac-delete-note" hidden>This permanently deletes your email address and saved progress from our servers and signs you out everywhere. Progress stored in this browser stays until you clear it. Press the button again to confirm.</p>
        </section>

        <section class="ac-card" aria-labelledby="ac-stats-h">
          <h2 id="ac-stats-h">Stats</h2>
          <div class="ac-table" id="ac-stats"></div>
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
     ["/games/core.js", "/games/sync.js", "/games/achievements.js", "/games/account.js"], robots="noindex, follow")

# ---------------- Hub ----------------
HUB_FAQ = [
    ("Are the games free?", "Yes. You can play every game without signing in, and there are no third-party ads, only an occasional small notice about one of our own apps. An optional email-link sign-in keeps your streaks and achievements across devices."),
    ("When does a new puzzle appear?", "At midnight in your time zone, so everyone sees the same puzzle on the same calendar date."),
    ("Do you track my results?", "Your streaks and results are saved in your own browser. We count anonymous plays and anonymous scores (so we can show how you did against other players) in our own statistics, with no cookies and no third party, and nothing in them identifies you. If you choose to sign in, we also keep your email address, a display name and your saved progress so they follow you between devices; you can delete all of it from the account page at any time."),
    ("Why does a research software site have games?", "Purplelink makes tools for researchers. These are small puzzles for a break between drafts, built by the same person."),
]
HUB_BODY = """      <div class="games-wrap">
        <section class="games-hero">
          <p class="eyebrow">Free, daily</p>
          <h1>Daily games</h1>
          <p class="game-lede">""" + html.escape(HUBMETA["answer"]) + """</p>
          <p>Sign in with an email link if you want your streaks and achievements on every device.</p>
        </section>
        <section class="hub-today" aria-labelledby="hub-today-h">
          <div class="hub-today-main">
            <h2 id="hub-today-h">Today</h2>
            <p class="hub-count" id="hub-count">Eight puzzles, a few minutes each.</p>
            <progress id="hub-progress" max="8" value="0" aria-label="Puzzles finished today"></progress>
            <p class="hub-level" id="hub-level"></p>
            <p class="games-note">Streak saver: miss one day a week and your streak survives.</p>
          </div>
          <a class="btn btn-primary" id="hub-next" href="/games/daily-photo/">Start with a photo</a>
        </section>
        <div class="games-grid">
          <a class="game-card" href="/games/linkle/" data-game="linkle">
            <img class="game-card-art" src="/assets/photography/hub/dsc-3940-480.webp" alt="" width="480" height="320" loading="lazy" decoding="async">
            <h2>Linkle</h2>
            <p>One five-letter word a day, with a new twist each weekday.</p>
            <span class="game-status" data-status></span>
          </a>
          <a class="game-card" href="/games/quadlink/" data-game="quadlink">
            <img class="game-card-art" src="/assets/photography/hub/dsc-8610-480.webp" alt="" width="480" height="320" loading="lazy" decoding="async">
            <h2>Quadlink</h2>
            <p>Four words at once, nine guesses.</p>
            <span class="game-status" data-status></span>
          </a>
          <a class="game-card" href="/games/daily-five/" data-game="daily-five">
            <img class="game-card-art" src="/assets/photography/hub/dsc-7888-480.webp" alt="" width="480" height="320" loading="lazy" decoding="async">
            <h2>Daily Five</h2>
            <p>Five trivia questions, with a few from the world of research and software.</p>
            <span class="game-status" data-status></span>
          </a>
          <a class="game-card" href="/games/daily-photo/" data-game="daily-photo">
            <img class="game-card-art" src="/assets/photography/hub/dsc-3638-480.webp" alt="" width="480" height="320" loading="lazy" decoding="async">
            <h2>Daily Photo</h2>
            <p>Five travel photographs. Which country was each one taken in?</p>
            <span class="game-status" data-status></span>
          </a>
          <a class="game-card" href="/games/daily-chess/" data-game="daily-chess">
            <img class="game-card-art" src="/assets/photography/hub/dsc-6626-edit-480.webp" alt="" width="480" height="320" loading="lazy" decoding="async">
            <h2>Daily Chess</h2>
            <p>A tactics puzzle from the Lichess database, easier on Monday and harder through the week.</p>
            <span class="game-status" data-status></span>
          </a>
          <a class="game-card" href="/games/sudoku/" data-game="sudoku">
            <img class="game-card-art" src="/assets/photography/hub/dsc-4267-480.webp" alt="" width="480" height="320" loading="lazy" decoding="async">
            <h2>Sudoku</h2>
            <p>One solution, and harder every week across a ten-week season.</p>
            <span class="game-status" data-status></span>
          </a>
          <a class="game-card" href="/games/crossword/" data-game="crossword">
            <img class="game-card-art" src="/assets/photography/hub/dsc-7919-480.webp" alt="" width="480" height="320" loading="lazy" decoding="async">
            <h2>Daily Crossword</h2>
            <p>A new themeless crossword every day, easy on Monday and hard on Sunday.</p>
            <span class="game-status" data-status></span>
          </a>
          <a class="game-card" href="/games/daily-stars/" data-game="daily-stars">
            <img class="game-card-art" src="/assets/photography/hub/dsc-8053-480.webp" alt="" width="480" height="320" loading="lazy" decoding="async">
            <h2>Daily Stars</h2>
            <p>A short horoscope for every sign, for entertainment only.</p>
            <span class="game-status" data-status></span>
          </a>
        </div>
        <p class="games-note"><span id="hub-ach"></span><a href="/games/account/">Your stats, achievements and sign-in</a></p>
        <div class="games-prose">
          <h2>The daily games at a glance</h2>
          <table class="games-table">
            <thead><tr><th scope="col">Game</th><th scope="col">What it is</th><th scope="col">Time</th></tr></thead>
            <tbody>
""" + "\n".join(f'              <tr><th scope="row"><a href="/{p_}">{m_["name"]}</a></th><td>{html.escape(first_sentence(m_["answer"]))}</td><td>About {m_["minutes"]} min</td></tr>' for p_, m_ in META.items()) + """
            </tbody>
          </table>
          <p>Every puzzle changes at midnight in your own time zone, so everyone sees the same puzzle on the same calendar date. Difficulty rises through the week in Linkle, the crossword and Daily Chess, and rises by season in Sudoku.</p>
          <h2>Questions</h2>
""" + faq_html(HUB_FAQ).replace("        <h3>", "          <h3>").replace("        <p>", "          <p>") + """
        </div>
      </div>"""
page("games/",
     "", "",
     HUB_BODY,
     {"@context": "https://schema.org", "@graph": [
         {"@type": "CollectionPage", "name": "Daily games", "url": "https://purplelink.llc/games/",
          "description": HUBMETA["answer"], "speakable": {"@type": "SpeakableSpecification", "cssSelector": [".game-lede", "h1"]},
          "mainEntity": {"@type": "ItemList", "itemListElement": [
              {"@type": "ListItem", "position": i + 1, "name": m_["name"], "url": "https://purplelink.llc/" + p_} for i, (p_, m_) in enumerate(META.items())]}},
         faq(HUB_FAQ),
         crumbs(("Home", "https://purplelink.llc/"), ("Games", "https://purplelink.llc/games/"))]},
     ["/games/core.js", "/games/sync.js", "/games/achievements.js", "/games/hub.js"])
