# Sports games: SEO, GEO and marketing plan (2026-10-05)

Readings taken today from the live site, the Google Search Console API and Bing Webmaster Tools. Web research is from searches the same day, so treat the market claims as secondary sources.

## Where the site stands

**Technical SEO is in good shape.** All 265 sitemap URLs return 200 with a self-pointing canonical and no `noindex`. All 636 internal link targets resolve. Every page has a unique title and description, one H1, a viewport tag, a language and image alt text. Structured data parses on every page that has it (Article, FAQPage, HowTo, WebApplication, BreadcrumbList, Product and others). Old game URLs 301 to the new ones. robots.txt welcomes GPTBot, ChatGPT-User, OAI-SearchBot, ClaudeBot, PerplexityBot, Google-Extended and the others, and `llms.txt` and `llms-full.txt` exist.

**Indexing is the problem, and it is mostly authority, not mistakes.** Google reports 78 of 265 sitemap URLs indexed:

| Google status | Pages |
|---|---|
| Submitted and indexed | 78 |
| URL is unknown to Google | 124 |
| Discovered, currently not indexed | 48 |
| Crawled, currently not indexed | 15 |

- "Unknown" is mostly new: all 29 games pages, 43 photography pages, 18 reference-format pages and 13 LaTeX-error pages. Google's last sitemap read before today was Oct 1, when the sitemap had 144 URLs. I resubmitted both sitemaps today.
- "Discovered, not indexed" means Google found the page and chose not to crawl it yet, which is what a site with few inbound links looks like (14 guides, 7 blog posts, 7 sheets, 6 tools, 5 templates).
- "Crawled, not indexed" (7 tools, 4 guides, 3 blog posts) is a quality or duplication signal: Google read the page and passed.
- Bing has 265 URLs discovered after today's submit (251 before) and no sitemap errors.

**Fixed today (live):** a footer link to the sports hub on every page (it was reachable only from the games hub), Organization `sameAs` (YouTube and GitHub), Article schema with dates on the four teammate-chain pages, `og:image` on the 27 reference-format pages that had none, both sitemaps resubmitted in Google and Bing, and an IndexNow ping of all URLs.

**Left as is, on purpose:** 128 titles are over 60 characters and 107 descriptions over 160, which means truncated snippets but not an indexing problem. Fixing them is a bulk rewrite I would only do with your say-so.

## What I need from you (browser steps I cannot do)

1. **Request indexing in Google Search Console** for these 12 URLs (URL Inspection, then Request Indexing; about 10 a day is the limit): /games/ , /games/sports/ , /games/lockerlink/ , /games/gridlink/ , /games/under-the-cap/ , the four /games/sports/<league>-teammate-chains/ pages, /games/linkle/ , /games/quadlink/.
2. **Add your LinkedIn page** (and any other real profile) to the Organization `sameAs`. I only added the two I know exist. Entity signals are the cheapest GEO lever.
3. **Look at Search Console, Links and Bing, Backlinks.** The API does not expose inbound links, and I cannot check "backlinking" from outside beyond the internal links, which are clean.

## GEO (appearing in AI answers)

Already done: AI crawlers allowed; question-style headings and an answer-first lede on every game page; FAQPage on every game page; `llms.txt`. ChatGPT search leans on Bing's index, so the Bing submit and IndexNow matter more than they look.

To do next:
- **Measure first.** Run 30 real queries (for example "Immaculate Grid alternatives", "NBA teammate chain game", "82-0 game", "how many degrees of separation in the NBA") through ChatGPT, Perplexity, Gemini and Claude; record who is cited. Repeat monthly. I can script the Perplexity and Bing half.
- **Own the facts.** AI answers quote specific numbers. The teammate-chain pages carry ones nobody else has (2.7 links on average among 45 NBA stars; Otto Graham to Patrick Mahomes in 6). Add the same pattern to each game page: one stat, one definition, one comparison.
- **Entity and author signals.** A named author on the blog and chain pages, the `sameAs` list, a consistent company description everywhere (press page, About, directories).

## Marketing: what the research says

- **Immaculate Grid's growth was one Reddit post and one Twitter account.** It launched Apr 4, 2023; for the first month it was friends and family. It took off after a post on the baseball subreddit and then @FoolishBB on Twitter on June 13, and passed 100,000 daily players within about 100 days. Lesson: find the one community account that already reaches your people.
- **Short video works for sports trivia.** GeoSports has about 1.8 million TikTok followers and 1.4 million YouTube subscribers. We already have a faceless TikTok, YouTube and Instagram pipeline (TikTokPipeline). A "chain of the day" clip is a natural fit: two players, the chain appearing link by link, the answer, a link in the bio.
- **Prior art for the chain pages.** The Harvard Sports Analysis Collective's "six degrees of NBA separation" (1949 to 2010; maximum eight), Slate's "Six degrees of Kevin Garnett" across four leagues, plus pieces in NBC Sports, The Ringer and SI. Journalists already like this angle. Ours extends it to 2025 and four leagues, and each league's longest chain is a quotable fact. Pitch it as a data story, not as a game.
- **Daily-game directories accept submissions:** Listdle (listdle.com, Submit a game), Dailydle (dailydle.org, send a link and a note), LikeWordle (likewordle.com) and AlternativeTo (alternativeto.net). These are the cheapest backlinks available; hand submission only.
- **Journalist-request platforms** (Qwoted, Featured, Source of Sources, the #journorequest tag on X) and turning unlinked mentions into links are the cheapest ways to a few strong backlinks. A one-line expert answer on sports data or game design is enough.
- **Sports subreddits mostly ban self-promotion** and each sets its own rules, so read the sidebar and message the mods first. A fact post ("five links from Russell to Brown") is more likely to be allowed than a game post.
- **Do not pay for ads.** The product screen already says daily games are a vitamin, not a painkiller (docs/growth-briefs/product-screen.md).

## Ranked plan

1. This week: the 12 indexing requests, the four directory submissions (drafts in sports-launch-kit-2026-10-05.md), the games-subreddit post.
2. Next: build the "chain of the day" short-video generator on the TikTok pipeline, from the data we already publish each week. It is the one automated channel and the one the research supports most.
3. Pitch the degrees pages to two or three sports-data writers, with the numbers from the pages.
4. Run the GEO query benchmark and repeat it monthly.
5. Later: an iOS wrapper. Several competitors are in the App Store; this is the biggest build and the least urgent.
