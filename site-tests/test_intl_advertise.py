"""ModernTex advertises its languages and its local-currency checkout (2026-10-29).

Stripe Adaptive Pricing is on for the Mac-app checkout: the buyer sees the USD price converted into their own
currency. The pages say so, in every language, and keep the claims about languages to what has shipped:

  - the app interface is English and German (beta), since ModernTex 2.0; Japanese and Chinese interface
    translations are not released, so no page may claim them (update this test with the pages when they ship)
  - Chinese and Japanese documents compile with XeLaTeX and LuaLaTeX when the TeX installation has the packages
  - every ModernTex price on the site equals the checkout catalog (netlify/functions/checkout.mjs), in 19.99
    and 19,99 notation
  - the language links resolve, and the daily indexing tools read the localized URLs from the sitemap

See docs/products/moderntex-intl.md.
"""
import re
import sys
import unittest
from common import ORIGIN, SITE, ROOT, jsonld_blocks, main_text, page_of, read, read_site, walk

PAGES = {"/moderntex/": "en", "/de/moderntex/": "de", "/fr/moderntex/": "fr", "/pt-br/moderntex/": "pt-BR", "/ja/moderntex/": "ja", "/zh-cn/moderntex/": "zh-Hans"}
LOCALIZED_PAGES = {u: l for u, l in PAGES.items() if l != "en"}
# What the currency fact says on each page, in the page's own language.
CURRENCY_PHRASE = {
    "en": r"local currency",
    "de": r"Landeswährung",
    "fr": r"monnaie locale",
    "pt-BR": r"moeda local",
    "ja": r"お住まいの地域の通貨",
    "zh-Hans": r"所在地区的货币",
}
# Pages that sell through netlify/functions/checkout.mjs and must carry the English currency line near the buy button.
ENGLISH_BUY_PAGES = ["/moderntex/", "/suite/", "/outbound-veil/", "/legroom/", "/keyfeel/", "/tapefolio/", "/panely/", "/summonly/"]


def catalog():
    """Prices from the checkout code, as cents."""
    src = read("netlify/functions/checkout.mjs")
    prices = {k: int(v) for k, v in re.findall(r'"([a-z-]+)":\s*\{ amount: (\d+),', src)}
    seats = read("netlify/lib/seats.mjs")
    prices["seat-units"] = [int(c) for c in re.findall(r"unitCents: (\d+)", seats)]
    bundles = read("netlify/lib/bundles.mjs")
    prices["bundles"] = [int(c) for c in re.findall(r"cents: (\d+)", bundles)]
    return prices


def money(cents):
    return f"{cents // 100}.{cents % 100:02d}"


def known_prices():
    c = catalog()
    cents = [c["moderntex"], c["app-suite"], *c["seat-units"], *c["bundles"]]
    cents += [u * n for u, n in zip(c["seat-units"], (5, 10, 15, 20, 25))]  # the table's totals, "from" 25 seats
    return {money(x) for x in cents}


def visible(url):
    return main_text(page_of(url).read_text(encoding="utf-8"))


class PricesAgreeWithTheCatalog(unittest.TestCase):
    def test_catalog_price_of_moderntex_is_19_99(self):
        self.assertEqual(money(catalog()["moderntex"]), "19.99")

    def test_every_site_page_that_names_a_moderntex_price_uses_a_catalog_price(self):
        known = known_prices()
        stray, with_price = [], 0
        for f in sorted(SITE.rglob("index.html")):
            t = re.sub(r"<[^>]+>", " ", re.sub(r"<(script|style)\b.*?</\1>", "", f.read_text(encoding="utf-8"), flags=re.S | re.I))
            for m in re.finditer(r"ModernTex[^.$<]{0,30}\$(\d+\.\d\d)|\$(\d+\.\d\d)[^.$<]{0,30}ModernTex", t):
                v = m.group(1) or m.group(2)
                with_price += v == "19.99"
                if v not in known:
                    stray.append((str(f.relative_to(SITE)), v))
        self.assertEqual(stray, [])
        self.assertGreater(with_price, 20)  # the scan finds the price at all

    def test_localized_pages_state_only_catalog_prices_in_every_notation(self):
        known = known_prices()
        for url, lang in PAGES.items():
            text = visible(url)
            found = re.findall(r"(\d+[.,]\d\d)\s*(?:US-Dollar|\$\s*US|USD|ドル|美元|\$)|\$(\d+\.\d\d)|US\$\s*(\d+[.,]\d\d)", text)
            vals = {(a or b or c).replace(",", ".") for a, b, c in found}
            self.assertIn("19.99", vals, url)
            self.assertEqual(vals - known, set(), url)
        self.assertIn("19,99 US-Dollar", visible("/de/moderntex/"))
        self.assertRegex(visible("/fr/moderntex/"), r"19,99\s\$\sUS")
        self.assertRegex(visible("/pt-br/moderntex/"), r"US\$\s19,99")
        self.assertIn("19.99ドル", visible("/ja/moderntex/"))
        self.assertIn("19.99 美元", visible("/zh-cn/moderntex/"))

    def test_offer_is_usd_at_the_catalog_price_on_all_six(self):
        for url in PAGES:
            blocks = jsonld_blocks(page_of(url).read_text(encoding="utf-8"))
            offers = [d["offers"] for b in blocks for d in walk(b) if d.get("@type") == "SoftwareApplication"]
            self.assertEqual([(o["price"], o["priceCurrency"]) for o in offers], [("19.99", "USD")], url)

    def test_buy_button_carries_the_catalog_price(self):
        for url, price in {"/moderntex/": "$19.99", "/de/moderntex/": "19,99 US-Dollar", "/fr/moderntex/": "19,99\u00a0$\u00a0US", "/pt-br/moderntex/": "US$\u00a019,99"}.items():
            t = page_of(url).read_text(encoding="utf-8")
            self.assertRegex(t, r'id="checkout-btn"[^>]*>[^<]*%s' % re.escape(price), url)


class CurrencyNote(unittest.TestCase):
    def test_every_moderntex_page_says_checkout_shows_the_local_currency(self):
        for url, lang in PAGES.items():
            self.assertRegex(visible(url), CURRENCY_PHRASE[lang], url)

    def test_every_moderntex_page_has_a_faq_answer_about_paying_locally(self):
        for url, lang in PAGES.items():
            blocks = jsonld_blocks(page_of(url).read_text(encoding="utf-8"))
            answers = [q["acceptedAnswer"]["text"] for b in blocks for d in walk(b) if d.get("@type") == "FAQPage" for q in d["mainEntity"]]
            hits = [a for a in answers if re.search(CURRENCY_PHRASE[lang], a)]
            self.assertTrue(hits, url)
            # card and Link are the payment methods checkout offers; nothing else may be promised
            self.assertRegex(hits[0], r"Link", url)

    def test_no_page_promises_alipay_or_wechat_pay(self):
        # Checkout offers card and Link only. A page may say the others are not offered, never that they are.
        for url in PAGES:
            t = visible(url)
            self.assertNotRegex(t, r"(?<!不支持)支付宝|(?<!不支持支付宝和)微信支付", url)
            self.assertNotRegex(t, r"(?<!not )(?:Alipay|WeChat Pay)", url)

    def test_localized_pages_no_longer_just_say_the_price_is_in_dollars(self):
        self.assertNotIn("Der Preis gilt in US-Dollar", visible("/de/moderntex/"))
        self.assertNotIn("Le prix est en dollars américains.", visible("/fr/moderntex/"))
        self.assertNotIn("O preço é em dólares americanos.", visible("/pt-br/moderntex/"))
        self.assertNotIn("価格は米ドルで表示しています", visible("/ja/moderntex/"))
        self.assertNotIn("价格以美元标示", visible("/zh-cn/moderntex/"))

    def test_every_english_page_with_a_checkout_mjs_mac_app_button_carries_the_currency_line(self):
        # Vitae Plus is a subscription, which Adaptive Pricing does not cover; it is deliberately not listed.
        mac = "moderntex|keyfeel|tapefolio|panely|summonly|outbound-veil|legroom|app-suite"
        found = set()
        for f in sorted(SITE.rglob("index.html")):
            rel = f.relative_to(SITE).as_posix()
            if rel.startswith(("de/", "fr/", "pt-br/", "ja/", "zh-cn/")):
                continue
            t = f.read_text(encoding="utf-8")
            if re.search(r'class="[^"]*pr-checkout-btn[^"]*"[^>]*data-product="(?:%s)"' % mac, t):
                found.add("/" + rel[: -len("index.html")])
                m = re.search(r'<p class="buy-assurance">(.*?)</p>', t, re.S)
                self.assertTrue(m and "local currency" in m.group(1), rel)
        self.assertTrue(set(ENGLISH_BUY_PAGES) <= found, found)

    def test_english_buy_pages_carry_the_currency_line_by_the_buy_button(self):
        for url in ENGLISH_BUY_PAGES:
            t = page_of(url).read_text(encoding="utf-8")
            m = re.search(r'<p class="buy-assurance">(.*?)</p>', t, re.S)
            self.assertIsNotNone(m, url)
            self.assertIn("local currency", m.group(1), url)

    def test_pricing_page_answers_the_currency_question(self):
        t = page_of("/pricing/").read_text(encoding="utf-8")
        self.assertEqual(t.count("Can I pay in my own currency?"), 2)  # FAQ markup and FAQPage JSON-LD
        self.assertIn("US dollar prices", t)


class InterfaceClaimsFollowReleases(unittest.TestCase):
    """Interface languages shipped: English and German (beta). The Japanese and Chinese translations are in open
    pull requests (moderntex #117 and #118) and unreleased. When they ship, update the pages and then these
    expectations (docs/products/moderntex-intl.md)."""

    FORBIDDEN = {
        "ja": r"日本語(?:の)?(?:インターフェース|ユーザーインターフェース|UI)|日本語化|フランス語(?:の)?(?:インターフェース|画面|UI)|ポルトガル語(?:の)?(?:インターフェース|画面|UI)|日本語版アプリ|画面は日本語(?:で表示|に対応|です。)|(?:インターフェース|画面表示|表示言語)(?:は|が)日本語(?:に対応|で表示|です)",
        "zh-Hans": r"法语界面|法文界面|葡萄牙语界面|中文界面|简体中文界面|中文用户界面|汉化|界面(?:已|支持)(?:翻译|支持)?(?:简体)?中文|应用(?:界面)?(?:有|提供)中文",
        "de": r"(?:französische|portugiesische|japanische|chinesische)[rn]? (?:Oberfläche|Benutzeroberfläche)|Oberfläche (?:auf|in) (?:Französisch|Portugiesisch|Japanisch|Chinesisch)",
        "fr": r"interface\s+(?:de\s+l.(?:app|application)\s+)?(?:est\s+|sera\s+)?(?:disponible\s+|traduite\s+)?(?:en\s+français|française)|(?:menus|app(?:lication)?)\s+en\s+français|interface\s+(?:en\s+)?(?:japonais|chinois)",
        "pt-BR": r"interface\s+(?:do\s+app\s+)?(?:é\s+|será\s+)?(?:disponível\s+|traduzida\s+)?(?:em\s+português|portuguesa)|(?:menus|app)\s+em\s+português|interface\s+(?:em\s+)?(?:japonês|chinês|francês)",
        "en": r"(?:French|Portuguese|Brazilian Portuguese|Japanese|Chinese|Simplified Chinese) (?:interface|UI|translation of the app|localization)|interface (?:is |in |available in )?(?:French|Portuguese|Japanese|Chinese)|(?:Japanese|Chinese) (?:menus|language support in the app)",
    }

    def texts(self):
        out = {}
        for f in sorted(SITE.rglob("*.html")):
            rel = f.relative_to(SITE).as_posix()
            if rel.startswith(("blog/digest/", "changelog/")):
                continue
            first = rel.split("/")[0]
            lang = {"de": "de", "fr": "fr", "pt-br": "pt-BR", "ja": "ja", "zh-cn": "zh-Hans"}.get(first, "en")
            out[rel] = (lang, f.read_text(encoding="utf-8"))
        for rel in ("llms.txt", "llms-full.txt"):
            out[rel] = ("en", read_site(rel))
        return out

    def test_no_page_claims_a_japanese_or_chinese_interface(self):
        bad = []
        for rel, (lang, text) in self.texts().items():
            for m in re.finditer(self.FORBIDDEN[lang], re.sub(r"<[^>]+>", " ", text)):
                bad.append((rel, m.group(0)))
        self.assertEqual(bad, [])

    def test_the_guard_matches_the_claims_it_is_meant_to_catch(self):
        for lang, sample in {"ja": "日本語インターフェースに対応", "zh-Hans": "ModernTex 提供中文界面", "de": "mit japanischer Oberfläche",
                             "en": "the Japanese interface ships in 2.1",
                             "fr": "ModernTex propose une interface disponible en français",
                             "pt-BR": "O ModernTex tem interface disponível em português"}.items():
            self.assertRegex(sample, self.FORBIDDEN[lang])
        for lang, ok in {"ja": "アプリの画面表示は現在、英語です。日本語の文書は XeLaTeX でコンパイルできます。",
                         "zh-Hans": "应用界面目前是英文。可以编译中文文档。", "en": "Chinese and Japanese documents compile with XeLaTeX.",
                         "fr": "L’interface de l’application est en anglais. Le français n’est pas encore une langue d’interface. Les documents en français se compilent.",
                         "pt-BR": "A interface do app é em inglês. O português ainda não é um idioma de interface. Os documentos em português compilam."}.items():
            self.assertNotRegex(ok, self.FORBIDDEN[lang])

    def test_japanese_and_chinese_pages_say_the_interface_is_english(self):
        self.assertRegex(visible("/ja/moderntex/"), r"アプリの画面表示は現在、英語です")
        self.assertRegex(visible("/zh-cn/moderntex/"), r"应用界面目前是英文")

    def test_french_page_says_the_interface_is_english_with_german_beta_and_never_french(self):
        t = visible("/fr/moderntex/")
        self.assertRegex(t, r"L’interface de l’application est en anglais")
        self.assertRegex(t, r"allemand depuis la version 2\.0 \(bêta\)")
        self.assertRegex(t, r"le français n’est pas encore une langue d’interface")
        self.assertRegex(t, r"babel ou polyglossia, encodage T1 et csquotes")

    def test_portuguese_page_says_the_interface_is_english_with_german_beta_and_never_portuguese(self):
        t = visible("/pt-br/moderntex/")
        self.assertRegex(t, r"A interface do app é em inglês")
        self.assertRegex(t, r"alemão desde a versão 2\.0 \(beta\)")
        self.assertRegex(t, r"o português ainda não é um idioma de interface")
        self.assertRegex(t, r"babel ou polyglossia, codificação T1 e csquotes")

    def test_german_page_says_the_interface_can_be_german_and_is_a_beta(self):
        t = visible("/de/moderntex/")
        self.assertRegex(t, r"seit Version 2\.0 auf Deutsch anzeigen \(Beta")

    def test_english_page_says_english_and_german_beta(self):
        t = visible("/moderntex/")
        self.assertRegex(t, r"English and German \(beta\)")
        self.assertRegex(t, r"XeLaTeX \(ctex\) or LuaLaTeX \(luatexja, jlreq\)")
        self.assertNotRegex(t, r"upLaTeX")  # not released

    def test_app_interface_languages_in_json_ld(self):
        for url in PAGES:
            blocks = jsonld_blocks(page_of(url).read_text(encoding="utf-8"))
            apps = [d for b in blocks for d in walk(b) if d.get("@type") == "SoftwareApplication"]
            self.assertEqual(apps[0]["inLanguage"], ["en", "de"], url)

    def test_llms_files_state_languages_and_currency(self):
        for rel in ("llms.txt", "llms-full.txt"):
            t = read_site(rel)
            self.assertRegex(t, r"English and German \(German is a beta", rel)
            self.assertIn("local currency", t, rel)
            self.assertIn("2 to 4 percent", t, rel)
            for url in ("/de/moderntex/", "/fr/moderntex/", "/pt-br/moderntex/", "/ja/moderntex/", "/zh-cn/moderntex/"):
                self.assertIn(ORIGIN + url, t, f"{rel} {url}")


class LanguageLinksResolve(unittest.TestCase):
    def targets(self, text, container):
        m = re.search(container, text, re.S)
        self.assertIsNotNone(m, container)
        return re.findall(r'href="(/[^"#?]*)"', m.group(1))

    def test_switcher_and_languages_section_links_resolve(self):
        for url in PAGES:
            t = page_of(url).read_text(encoding="utf-8")
            hrefs = self.targets(t, r'<nav class="lang-switch"[^>]*>(.*?)</nav>')
            self.assertEqual(sorted(hrefs), sorted(PAGES), url)
            for h in hrefs:
                self.assertTrue(page_of(h).is_file(), f"{url} -> {h}")
        en = page_of("/moderntex/").read_text(encoding="utf-8")
        section = self.targets(en, r'<section class="specs-section" id="languages"(.*?)</section>')
        self.assertEqual(sorted(section), sorted(LOCALIZED_PAGES))

    def test_every_footer_links_the_five_localized_pages_and_they_resolve(self):
        for rel in ("index.html", "moderntex/index.html", "pricing/index.html", "guides/index.html"):
            t = (SITE / rel).read_text(encoding="utf-8")
            m = re.search(r'<p class="footer-langs">(.*?)</p>', t, re.S)
            self.assertIsNotNone(m, rel)
            hrefs = re.findall(r'href="([^"]+)"', m.group(1))
            self.assertEqual(hrefs, ["/de/moderntex/", "/fr/moderntex/", "/pt-br/moderntex/", "/ja/moderntex/", "/zh-cn/moderntex/"], rel)
            self.assertEqual(re.findall(r'hreflang="([^"]+)"', m.group(1)), ["de", "fr", "pt-BR", "ja", "zh-Hans"], rel)
            for h in hrefs:
                self.assertTrue(page_of(h).is_file(), h)

    def test_localized_footers_do_not_carry_the_english_language_line(self):
        for url in LOCALIZED_PAGES:
            self.assertNotIn("footer-langs", page_of(url).read_text(encoding="utf-8"), url)

    def test_stylesheet_styles_the_footer_language_line(self):
        self.assertIn(".footer-langs a", read_site("styles.css"))


class ZhCnStaysFreeOfGoogle(unittest.TestCase):
    def test_no_google_pay_or_google_url_on_any_zh_cn_page(self):
        for f in sorted((SITE / "zh-cn").rglob("*.html")):
            t = f.read_text(encoding="utf-8")
            self.assertNotIn("Google Pay", t, f.name)
            self.assertNotRegex(t, r"https?://[^\s\"']*(?:google|gstatic|doubleclick|googlesyndication)", f.name)
            self.assertNotIn("adsbygoogle", t, f.name)

    def test_footer_language_line_is_not_added_to_the_chinese_pages_as_a_google_dependency(self):
        # The line is plain links to this site; nothing in it points at Google.
        t = (SITE / "index.html").read_text(encoding="utf-8")
        m = re.search(r'<p class="footer-langs">(.*?)</p>', t, re.S)
        self.assertNotRegex(m.group(1), r"google|gstatic", )


class IndexingPicksUpTheLocalizedUrls(unittest.TestCase):
    def test_indexnow_script_reads_the_localized_urls_from_the_sitemap(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        try:
            import indexnow_ping
        finally:
            sys.path.pop(0)
        urls = set(indexnow_ping.urls_from_sitemap(only_today=False))
        for url in list(LOCALIZED_PAGES) + [
            "/de/guides/latex-auf-dem-mac-einrichten/", "/fr/guides/latex-en-francais-sur-mac/", "/pt-br/guides/latex-em-portugues-do-brasil-no-mac/", "/ja/guides/mac-nihongo-latex/",
            "/zh-cn/guides/mac-xelatex-ctex-zhongwen-lunwen/",
        ]:
            self.assertIn(ORIGIN + url, urls, url)

    def test_daily_job_filter_does_not_skip_language_prefixes(self):
        # ~/.purplelink/bin/daily-indexing.py takes every <loc> of the live sitemap; the repo has no path filter either.
        src = read("scripts/indexnow_ping.py")
        self.assertNotRegex(src, r"/(de|fr|pt-br|ja|zh-cn)/")


class UptimeWatchesTheLocalizedPages(unittest.TestCase):
    def test_checks_file_probes_the_six_moderntex_pages(self):
        checks = read("scripts/uptime-checks.txt")
        for url in PAGES:
            self.assertRegex(checks, r"(?m)^[a-z0-9-]+\|GET\|%s\|200$" % re.escape(ORIGIN + url))


if __name__ == "__main__":
    unittest.main()
