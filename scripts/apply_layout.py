#!/usr/bin/env python3
"""Stamp the shared header nav and footer onto every page in site/.

The site had nine header variants and six footers, because each page carried
its own copy. Two nav items ("Software", "Products") pointed at homepage ids
that no longer existed, on 226 pages, and 228 pages had no footer link to the
tools. This script is now the one place the nav and footer are defined.

It replaces the contents of <nav aria-label="Primary navigation"> and the
whole <footer class="footer"> element, and marks the current section with
aria-current. It is idempotent: run it after adding or editing a page.

Localized pages (site/de/, site/fr/, site/pt-br/, site/ja/, site/zh-cn/) get their own short nav and footer, in their
language, from LOCALES below. Pages that exist only in English are labelled "(English)" in the
footer so nobody follows a link expecting their language. Add a locale here, not on the page.

Skipped:
  - site/blog/digest/  (generated and committed by the Modal cron; see
    .githooks/pre-commit. backend/digest/publisher.py emits the same markup)
  - checkout success, manage and recover pages, whose short nav is deliberate
  - /stats/ and build-only files under assets/

  python3 scripts/apply_layout.py           # rewrite in place
  python3 scripts/apply_layout.py --check   # exit 1 if any page is out of date
"""
from __future__ import annotations

import hashlib
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"

SKIP_PREFIXES = ("blog/digest/", "assets/", "stats/")
SKIP_PATHS = {
    "moderntex/success/index.html",
    "kits/success/index.html",
    "sheets/success/index.html",
    "sheets/live/setup/index.html",
    "vitae/plus/success/index.html",
    "vitae/plus/manage/index.html",
    "vitae/plus/recover/index.html",
    "tools/paper-review/packs/success/index.html",
}

# (label, href, sections that mark it current)
# Games and Blog are not in the header (2026-10-13 nav trim); they stay in the
# footer ("Daily games" under Free tools, "Blog" and "Changelog" under Learn),
# so pages in those sections simply have no highlighted header item.
NAV = [
    ("Products", "/products/", ("products/", "moderntex/", "outbound-veil/", "suite/", "pricing/", "legroom/", "keyfeel/", "tapefolio/", "panely/", "summonly/", "batterymeter/", "buddy/", "vitae/", "globepin/", "circled-hoops/",
                                "haea/", "binnacle/", "kits/", "sheets/", "scholar-utility-belt/", "labs/", "recover/")),
    ("Tools", "/tools/", ("tools/", "format/")),
    ("Guides", "/guides/", ("guides/", "templates/", "latex-errors/")),
    ("About", "/about/", ("about/", "press/", "photography/", "support/", "security/", "privacy/", "terms/", "feedback/")),
]

FOOTER_COLUMNS = [
    ("Products", [
        ("ModernTex", "/moderntex/"),
        ("Outbound Veil", "/outbound-veil/"),
        ("Vitae", "/vitae/"),
        ("Legroom", "/legroom/"),
        ("Keyfeel", "/keyfeel/"),
        ("Tapefolio", "/tapefolio/"),
        ("Panely", "/panely/"),
        ("Summonly", "/summonly/"),
        ("BatteryMeter", "/batterymeter/"),
        ("Paper Review", "/tools/paper-review/"),
        ("Scholar Utility Belt", "/scholar-utility-belt/"),
        ("Mac Suite", "/suite/"),
        ("All products", "/products/"),
    ]),
    ("Free tools", [
        ("LaTeX to PDF", "/tools/latex-to-pdf/"),
        ("BibTeX Validator", "/tools/bib-validator/"),
        ("Citation Generator", "/tools/citation-generator/"),
        ("LaTeX Diff", "/tools/latex-diff/"),
        ("Word Counter", "/tools/word-counter/"),
        ("Daily games", "/games/"),
        ("Sports games", "/games/sports/"),
        ("All tools", "/tools/"),
    ]),
    ("Learn", [
        ("Guides", "/guides/"),
        ("Research methods", "/guides/methodology-problems-peer-reviewers-flag/"),
        ("LaTeX templates", "/templates/"),
        ("LaTeX errors", "/latex-errors/"),
        ("Reference formats", "/format/"),
        ("Blog", "/blog/"),
        ("Changelog", "/changelog/"),
        ("Search", "/search/"),
    ]),
    ("Company", [
        ("About", "/about/"),
        ("Pricing", "/pricing/"),
        ("Press", "/press/"),
        ("Photography", "/photography/"),
        ("Support", "/support/"),
        ("Contact", "mailto:ben@purplelink.llc"),
        ("LinkedIn", "https://www.linkedin.com/company/purplelink-llc/", ' rel="noopener"'),
        ("Privacy", "/privacy/"),
        ("Terms", "/terms/"),
        ("Find a purchase", "/recover/"),
        ("For labs", "/labs/"),
    ]),
]


# Localized sections. Each entry gives the nav and footer for pages under site/<code>/. A link may carry a third
# item: extra attributes for the <a>. Destinations that exist only in English say so in their label.
def _locale(guide, nav_label, nav_guide, home, blurb, loc, toggle, cols):
    return {
        "nav_aria": nav_label, "guide": guide, "nav_guide": nav_guide, "home": home, "blurb": blurb, "loc": loc,
        "toggle": toggle, "cols": cols,
    }


LOCALES = {
    "de": _locale(
        guide=("LaTeX auf dem Mac einrichten", "/de/guides/latex-auf-dem-mac-einrichten/"),
        nav_label="Hauptnavigation", nav_guide="Anleitung", home="English",
        blurb="Apps und Werkzeuge aus einem Ein-Personen-Studio in Atlanta, Georgia.",
        loc="Atlanta, Georgia · Seit 2026",
        toggle=("Helles Design verwenden", "Dunkles Design verwenden"),
        cols=[
            ("ModernTex", [("Produktseite", "/de/moderntex/"), ("@guide",), ("Änderungsprotokoll (Englisch)", "/changelog/"),
                           ("Kauf wiederfinden (Englisch)", "/recover/")]),
            ("Weitere Seiten (Englisch)", [("Alle Produkte", "/products/"), ("Kostenlose Tools", "/tools/"),
                                           ("Anleitungen", "/guides/"), ("Blog", "/blog/")]),
            ("Unternehmen", [("Über uns (Englisch)", "/about/"), ("Support (Englisch)", "/support/"),
                             ("Kontakt", "mailto:ben@purplelink.llc"), ("Datenschutz (Englisch)", "/privacy/"),
                             ("Nutzungsbedingungen (Englisch)", "/terms/")]),
        ]),
    "fr": _locale(
        guide=("LaTeX en français sur Mac", "/fr/guides/latex-en-francais-sur-mac/"),
        nav_label="Navigation principale", nav_guide="Guide", home="English",
        blurb="Des apps et des outils conçus par un studio d’une seule personne, à Atlanta, en Géorgie.",
        loc="Atlanta, Géorgie · Depuis 2026",
        toggle=("Utiliser le thème clair", "Utiliser le thème sombre"),
        cols=[
            ("ModernTex", [("Page du produit", "/fr/moderntex/"), ("@guide",), ("Journal des modifications (en anglais)", "/changelog/"),
                           ("Retrouver un achat (en anglais)", "/recover/")]),
            ("Autres pages (en anglais)", [("Tous les produits", "/products/"), ("Outils gratuits", "/tools/"),
                                           ("Guides", "/guides/"), ("Blog", "/blog/")]),
            ("Entreprise", [("À propos (en anglais)", "/about/"), ("Assistance (en anglais)", "/support/"),
                            ("Contact", "mailto:ben@purplelink.llc"), ("Confidentialité (en anglais)", "/privacy/"),
                            ("Conditions d’utilisation (en anglais)", "/terms/")]),
        ]),
    "pt-br": _locale(
        guide=("LaTeX em português do Brasil no Mac", "/pt-br/guides/latex-em-portugues-do-brasil-no-mac/"),
        nav_label="Navegação principal", nav_guide="Guia", home="English",
        blurb="Apps e ferramentas feitos por um estúdio de uma pessoa só, em Atlanta, na Geórgia.",
        loc="Atlanta, Geórgia · Desde 2026",
        toggle=("Usar o tema claro", "Usar o tema escuro"),
        cols=[
            ("ModernTex", [("Página do produto", "/pt-br/moderntex/"), ("@guide",), ("Histórico de alterações (em inglês)", "/changelog/"),
                           ("Recuperar uma compra (em inglês)", "/recover/")]),
            ("Outras páginas (em inglês)", [("Todos os produtos", "/products/"), ("Ferramentas gratuitas", "/tools/"),
                                            ("Guias", "/guides/"), ("Blog", "/blog/")]),
            ("Empresa", [("Sobre (em inglês)", "/about/"), ("Suporte (em inglês)", "/support/"),
                         ("Contato", "mailto:ben@purplelink.llc"), ("Privacidade (em inglês)", "/privacy/"),
                         ("Termos de uso (em inglês)", "/terms/")]),
        ]),
    "ja": _locale(
        guide=("Mac で日本語 LaTeX を使う", "/ja/guides/mac-nihongo-latex/"),
        nav_label="メインナビゲーション", nav_guide="ガイド", home="English",
        blurb="米国ジョージア州アトランタの一人運営スタジオが作るアプリとツール。",
        loc="アトランタ（ジョージア州）· 2026年創業",
        toggle=("ライトテーマにする", "ダークテーマにする"),
        cols=[
            ("ModernTex", [("製品ページ", "/ja/moderntex/"), ("@guide",), ("変更履歴（英語）", "/changelog/"),
                           ("購入の再確認（英語）", "/recover/")]),
            ("英語のページ", [("すべての製品", "/products/"), ("無料ツール", "/tools/"), ("ガイド", "/guides/"),
                              ("ブログ", "/blog/")]),
            ("会社情報", [("会社概要（英語）", "/about/"), ("サポート（英語）", "/support/"),
                          ("お問い合わせ", "mailto:ben@purplelink.llc"), ("プライバシー（英語）", "/privacy/"),
                          ("利用規約（英語）", "/terms/")]),
        ]),
    "zh-cn": _locale(
        guide=("在 Mac 上用 XeLaTeX 和 ctex 写中文论文", "/zh-cn/guides/mac-xelatex-ctex-zhongwen-lunwen/"),
        nav_label="主导航", nav_guide="指南", home="English",
        blurb="美国佐治亚州亚特兰大的一人工作室，制作应用和工具。",
        loc="亚特兰大，佐治亚州 · 创立于 2026 年",
        toggle=("切换为浅色主题", "切换为深色主题"),
        cols=[
            ("ModernTex", [("产品页面", "/zh-cn/moderntex/"), ("@guide",), ("更新日志（英文）", "/changelog/"),
                           ("找回购买记录（英文）", "/recover/")]),
            ("英文页面", [("全部产品", "/products/"), ("免费工具", "/tools/"), ("指南", "/guides/"), ("博客", "/blog/")]),
            ("公司", [("关于（英文）", "/about/"), ("支持（英文）", "/support/"), ("联系", "mailto:ben@purplelink.llc"),
                      ("隐私政策（英文）", "/privacy/"), ("服务条款（英文）", "/terms/")]),
        ]),
}


def locale_of(rel: str):
    first = rel.split("/", 1)[0]
    return LOCALES.get(first) and first


def locale_nav(code: str):
    loc = LOCALES[code]
    return [
        ("ModernTex", f"/{code}/moderntex/", (f"{code}/moderntex/",), ""),
        (loc["nav_guide"], loc["guide"][1], (f"{code}/guides/",), ""),
        (loc["home"], "/", (), ' lang="en" hreflang="en"'),
    ]


def locale_cols(code: str):
    loc = LOCALES[code]
    out = []
    for head, links in loc["cols"]:
        out.append((head, [loc["guide"] if l == ("@guide",) else l for l in links]))
    return out

NAV_LABELS = "|".join(re.escape(l) for l in ["Primary navigation"] + [v["nav_aria"] for v in LOCALES.values()])
NAV_RE = re.compile(r'(<nav aria-label="(?:%s)">)(.*?)(</nav>)' % NAV_LABELS, re.S)
FOOTER_RE = re.compile(r'([ \t]*)<footer class="footer">.*?</footer>', re.S)


def section_of(rel: str) -> str:
    return "" if rel in ("index.html", "404.html") else rel


def nav_html(rel: str, inline: bool, indent: str) -> str:
    items = []
    code = locale_of(rel)
    nav = locale_nav(code) if code else [(a, b, c, "") for a, b, c in NAV]
    for label, href, sections, extra in nav:
        current = any(rel.startswith(s) for s in sections)
        attr = ' aria-current="page"' if current else ""
        items.append(f'<a href="{href}"{attr}{extra}>{label}</a>')
    if inline:
        return "".join(items)
    return "\n" + "".join(f"{indent}  {i}\n" for i in items) + indent


def mark_src() -> str:
    """The mark with the same ?v stamp fingerprint_assets.py gives it, so the two scripts agree and a new mark
    reaches returning visitors instead of hiding behind the 30-day /assets/* cache."""
    digest = hashlib.sha256((SITE / "assets" / "purplelink-mark.svg").read_bytes()).hexdigest()[:10]
    return f"/assets/purplelink-mark.svg?v={digest}"


def footer_html(indent: str, code: str | None = None) -> str:
    i = indent
    cols = []
    loc = LOCALES[code] if code else None
    for head, links in (locale_cols(code) if code else FOOTER_COLUMNS):
        # A link may carry a third item: extra attributes for the <a> (external links use rel="noopener").
        lis = "\n".join(f'{i}        <li><a href="{l[1]}"{l[2] if len(l) > 2 else ""}>{l[0]}</a></li>' for l in links)
        cols.append(
            f'{i}    <nav class="footer-col" aria-label="{head}">\n'
            f'{i}      <p class="footer-head">{head}</p>\n'
            f'{i}      <ul>\n{lis}\n{i}      </ul>\n'
            f'{i}    </nav>'
        )
    if loc:
        light, dark = loc["toggle"]
        toggle = (f'<button type="button" class="theme-toggle" data-theme-toggle hidden '
                  f'data-label-light="{light}" data-label-dark="{dark}">{light}</button>')
    else:
        toggle = '<button type="button" class="theme-toggle" data-theme-toggle hidden>Use light theme</button>'
    return (
        f'{i}<footer class="footer">\n'
        f'{i}  <div class="footer-grid">\n'
        f'{i}    <div class="footer-about">\n'
        f'{i}      <a class="footer-brand" href="/">\n'
        f'{i}        <img src="{mark_src()}" alt="" width="26" height="26">\n'
        f'{i}        <span>Purplelink LLC</span>\n'
        f'{i}      </a>\n'
        f'{i}      <p class="footer-blurb">{loc["blurb"] if loc else "Apps and tools made by a one-person studio in Atlanta, Georgia."}</p>\n'
        f'{i}      <a class="footer-mail" href="mailto:ben@purplelink.llc">ben@purplelink.llc</a>\n'
        + ("" if loc else
           f'{i}      <p class="footer-langs"><span>ModernTex in</span> <a href="/de/moderntex/" lang="de" hreflang="de">Deutsch</a> '
           f'<a href="/fr/moderntex/" lang="fr" hreflang="fr">Français</a> '
           f'<a href="/pt-br/moderntex/" lang="pt-BR" hreflang="pt-BR">Português</a> '
           f'<a href="/ja/moderntex/" lang="ja" hreflang="ja">日本語</a> <a href="/zh-cn/moderntex/" lang="zh-Hans" hreflang="zh-Hans">简体中文</a></p>\n') +
        f'{i}    </div>\n'
        + "\n".join(cols) + "\n"
        f'{i}  </div>\n'
        f'{i}  <div class="footer-bottom">\n'
        f'{i}    <span>&copy; 2026 Purplelink LLC</span>\n'
        f'{i}    <span class="footer-loc">{loc["loc"] if loc else "Atlanta, Georgia · Est. 2026"}</span>\n'
        f'{i}    {toggle}\n'
        f'{i}  </div>\n'
        f'{i}</footer>'
    )


MOTION_CSS = '    <link rel="stylesheet" href="/motion.css">\n'
MOTION_JS = '    <script src="/motion.js" defer></script>\n'


THEME_JS = '    <script src="/theme.js"></script>\n'


def with_theme(html: str) -> str:
    """theme.js must run before first paint, so it goes in <head> ahead of the
    stylesheet and without defer. Pages that already carry it are left alone."""
    if "theme.js" in html or "</head>" not in html:
        return html
    m = re.search(r'[ \t]*<link rel="stylesheet" href="/?styles\.css', html)
    if m:
        return html[:m.start()] + THEME_JS + html[m.start():]
    return html.replace("</head>", THEME_JS + "</head>", 1)


def with_motion(html: str) -> str:
    """Every page loads the shared motion module (fingerprint_assets stamps
    the ?v hash). Pages that already carry it are left alone."""
    if "motion.js" in html or "</head>" not in html:
        return html
    if "/site.js" not in html:
        return html.replace("</head>", MOTION_CSS + MOTION_JS + "</head>", 1)
    out = re.sub(r'(<link rel="stylesheet" href="/?styles\.css[^"]*">\n)',
                 lambda m: m.group(1) + MOTION_CSS, html, count=1)
    if "motion.css" not in out:
        out = out.replace("</head>", MOTION_CSS + "</head>", 1)
    return re.sub(r'(<script src="/?site\.js[^"]*" defer></script>\n)',
                  lambda m: m.group(1) + MOTION_JS, out, count=1) if "motion.js" not in out else out


def render(rel: str, html: str) -> str:
    def nav_sub(m: re.Match) -> str:
        inline = "\n" not in m.group(2)
        line_start = html.rfind("\n", 0, m.start()) + 1
        indent = re.match(r"[ \t]*", html[line_start:]).group(0)
        return m.group(1) + nav_html(section_of(rel), inline, indent) + m.group(3)

    out = NAV_RE.sub(nav_sub, html, count=1)
    out = FOOTER_RE.sub(lambda m: footer_html(m.group(1), locale_of(rel)), out, count=1)
    return with_theme(with_motion(out))


def pages():
    for f in sorted(SITE.rglob("*.html")):
        rel = f.relative_to(SITE).as_posix()
        if rel.startswith(SKIP_PREFIXES) or rel in SKIP_PATHS or rel.startswith("google"):
            continue
        yield rel, f


def main() -> int:
    check = "--check" in sys.argv
    stale = 0
    for rel, f in pages():
        html = f.read_text(encoding="utf-8")
        new = render(rel, html)
        if new != html:
            stale += 1
            if not check:
                f.write_text(new, encoding="utf-8")
    verb = "stale" if check else "updated"
    print(f"layout: {stale} page(s) {verb}")
    return 1 if (check and stale) else 0


if __name__ == "__main__":
    sys.exit(main())
