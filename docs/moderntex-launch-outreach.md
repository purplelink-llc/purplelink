# ModernTex launch outreach pack

Prepared 2026-09-11, updated the same day once the trial shipped. Extends `purplelink-tool-distribution-kit.md`, which covers the
free tools; this one is specifically for ModernTex ($10, macOS 14+, v1.0.2, free 7-day trial).

The point of all of this is links and real humans. purplelink.llc has close to zero
external links, which is the standing ceiling on every ranking the site has. Six
ModernTex sales came from organic search in thirty hours with no promotion at all;
outreach is how that channel gets bigger.

## Read this first

- **Every post and email below is sent by you, from your accounts, in your voice.**
  Nothing here can be automated or scheduled the way the MuscleOnGLP TikTok pipeline
  is. Automated or templated posting in these communities is a permanent ban, and
  templated pitches are what TidBITS calls "basically spamming."
- **One community per week, not all at once.** A burst of new links from many places
  in one day is the pattern search engines flag. Space them.
- **Read the live rules before each post.** Reddit rules could not be fetched for this
  pack; the sub sections below carry the long-standing norms, but open the sidebar
  first. If a sub has a weekly self-promo or showcase thread, post there, not as a
  standalone.
- **Disclose that you built it, every time, in the first line.** This is both the rule
  in every community below and the thing that makes people forgive a maker post.
- **Answer every comment for 48 hours after each post.** The post is not the outreach;
  the replies are.
- **Every draft below has been written without the tics that get pitches binned.**
  When you edit them, keep it that way: no "honestly," "genuinely," "real" as
  intensifiers; no "it's important to note," "at its core," "here's the thing"; no
  "not just X, but Y"; say each thing once. That list comes from the TidBITS editor
  and applies everywhere.

Facts to keep consistent across every post: native Mac LaTeX editor for researchers ·
free 7-day trial, the complete app, no account · $10 once to keep, updates included ·
macOS 14 or later, Apple silicon and Intel · needs a TeX distribution such as MacTeX or
TinyTeX · version 1.0.2 · built by an academic who writes papers in LaTeX. Trial link:
https://purplelink.llc/moderntex/ (the download button is the first thing on the page). Features: multi-file manuscript navigation,
synchronized PDF preview, BibTeX completion that searches your whole .bib by author or
title, plain-language compile diagnostics, submission-readiness checks, anonymized
submission export, version snapshots, three compile modes.

## Prerequisites

### 1. The trial: done (2026-09-11)

ModernTex 1.0.2 ships as two editions from one codebase. The trial is the complete app
for seven days from first launch, no account, and it cannot update itself into the paid
app. It is the first button on https://purplelink.llc/moderntex/ and is served from
`/.netlify/functions/moderntex-download?trial=1`. This unlocks Show HN (below) and
gives every post a "try it" link, which is what turns "tell me what's missing" from a
request into something people can actually do.

### 2. Reviews from the six buyers

Real reviews are the only social proof the site is allowed to show (the homepage
schema has a comment refusing ratings without them), and they unlock the directory
listings and the blogger pitches. Send this from your own inbox, not the system
address, to each of the six ModernTex buyers, one at a time, first names if you have
them.

> **Subject:** One question about ModernTex
>
> Hi [name],
>
> You bought ModernTex on [date]. I'm the person who built it, and you're one of the
> first people to use it, so I'd like to ask you one thing.
>
> Has it done anything for you yet, or has it got in the way? Either answer is useful.
> A sentence is plenty.
>
> If it has helped and you're willing, I'd like to quote you on the site, with your
> first name or initials and your field, nothing more. Say so and I will; say nothing
> and I won't.
>
> If something is broken or missing, tell me and I'll fix it. Replies come to me.
>
> Ben

When a quote comes back with permission, it goes on `/moderntex/` and in the
"ModernTex" section of `/guides/best-mac-latex-editors/` with the buyer's initials and
field, and into Product schema only as a verifiable review.

## Tier 1: durable listings (this week, spaced over 3 to 4 days)

Each of these is a permanent page that ranks for "[competitor] alternative" searches
and carries a link. They matter more than any single post because they keep paying.
Submit under your own account. Where a field asks for a category or comparison,
position ModernTex against TeXShop, Texifier, TeXstudio and Overleaf.

**Reusable listing copy** (adjust length to the field):

> Tagline: Native Mac LaTeX editor for academic manuscripts. Free 7-day trial, $10 once.
>
> Short: ModernTex is a native macOS LaTeX editor built for writing journal articles
> and dissertation chapters. Multi-file manuscript navigation, synchronized PDF
> preview, BibTeX completion that searches your whole bibliography by author or title,
> compile errors explained in plain language, submission-readiness checks and an
> anonymized export for review. Free 7-day trial with no account, then $10 one-time
> with updates included. Requires macOS 14
> and a TeX distribution such as MacTeX.
>
> Long (add to short): It is not a general text editor with a LaTeX mode and not a
> browser app. It is narrower than Texifier on purpose: the workflow of getting a
> manuscript from outline to camera-ready on a Mac. It does not bundle a TeX
> distribution, so MacTeX or TinyTeX must be installed first.

| Where | What to do | Notes |
|---|---|---|
| **AlternativeTo** (alternativeto.net) | Create the app entry; list it as an alternative to TeXShop, Texifier, TeXstudio, Overleaf. | Editorially reviewed; developer submissions are normal. Use the short copy. Add screenshots. |
| **MacUpdate** (macupdate.com, developer submission) | Submit the app with the Sparkle appcast URL if the form accepts one. | Old, high-authority domain. |
| **Product Hunt** | Launch Tuesday to Thursday, early US morning. Tagline plus long copy, four screenshots, and a maker comment (below). | Rally the six buyers and your own network in the first hours; do not buy upvotes. |
| **SaaSHub** | Add under LaTeX editors. | Dofollow. |
| **Launching Next**, **Fazier**, **Uneed** | Standard launch listings. | Free tiers give a dofollow link. Five to fifteen minutes each. |
| **GitHub: awesome-LaTeX** (github.com/danphilps/awesome-LaTeX) | Open a PR adding one line under editors. | The single highest-authority link on this list. Follow the list's format exactly; one line, no adjectives. |

**awesome-LaTeX PR line:**

> - [ModernTex](https://purplelink.llc/moderntex/) - Native macOS editor for academic manuscripts: multi-file navigation, synced PDF preview, BibTeX completion, plain-language compile errors, submission checks. $10, one-time.

**Product Hunt maker comment:**

> I write papers in LaTeX and I built the editor I kept wishing I had. Three things
> drove it: compile errors that tell you what to fix instead of quoting a log,
> BibTeX completion that finds a reference by author or title across the whole
> .bib, and a set of checks that catch what a journal will bounce before you upload.
> There's a free 7-day trial with no account, then it's $10 once. macOS only, and it
> needs MacTeX installed. It is one week old, so
> the state of it is: it works, it has no track record yet, and I'd rather hear
> what's missing than what's nice.

## Tier 2: communities, one per week, in this order

### Show HN (once, a weekday between 8 and 10am Eastern, after the directories are up)

HN's rules require something people can try; the trial satisfies that. One shot. Be
in the comments for the whole day, answer everything, concede real points. The title
is the whole pitch on HN: no adjectives, say what it is.

> **Title:** Show HN: ModernTex – a native macOS LaTeX editor for writing papers
>
> **URL:** https://purplelink.llc/moderntex/
>
> **First comment (post it yourself, immediately):**
> I write papers in LaTeX and built the editor I kept wishing I had. It is macOS-only,
> native (SwiftUI, not Electron), and narrower than TeXShop or Texifier on purpose:
> the workflow of getting a journal article or dissertation chapter from outline to
> submission.
>
> The parts that made me build it rather than keep using TeXShop: compile errors
> rewritten into plain language with the line that caused them (BibTeX's are the
> worst offenders); BibTeX completion that searches the whole .bib by author or
> title; multi-file navigation across a manuscript; checks for what journals bounce
> on; and an anonymized export for double-blind review.
>
> It needs MacTeX or TinyTeX installed; it does not bundle a distribution. Free
> 7-day trial with no account, then $10 once. It is a week old, so it has no track
> record, and I would rather hear what is missing than what is nice. The obvious
> comparison is Texifier, which bundles its own TeX and has years on this; if you
> already own it you probably do not need ModernTex.

### Week 1: the MacOSX-TeX mailing list

This is the best fit on the whole list and almost nobody thinks of it. It is the TeX
Users Group's Mac list (archives at email.esm.psu.edu/pipermail/macosx-tex/), the
people who maintain and use MacTeX, and new Mac editors have been announced there for
twenty years. Plain-text email, no HTML. Join first, read a week of threads, then:

> **Subject:** New editor: ModernTex, native macOS, aimed at manuscript writing
>
> I've released a native macOS LaTeX editor called ModernTex and wanted to mention it
> here, since this list is where most of the people who'd care are.
>
> It is built around the workflow of writing a journal article or dissertation
> chapter rather than general LaTeX use: multi-file navigation across a manuscript,
> synchronized PDF preview, BibTeX completion by author or title across the .bib,
> compile errors rewritten into plain language with the offending line, checks for
> the things journals reject on, and an anonymized export for review. It uses the
> MacTeX (or TinyTeX) you already have; it doesn't bundle a distribution.
>
> macOS 14 or later, Apple silicon and Intel. There is a free 7-day trial with no
> account, then $10 one-time. It is version 1.0.2 and a week old, so I'd value bug
> reports and missing-feature notes more than anything.
> https://purplelink.llc/moderntex/
>
> Ben Ampel

### Week 2: r/LaTeX

Read the sidebar and check for a showcase or self-promo thread first. One post, flair
it as a tool or project if the sub has such a flair, disclose in line one.

> **Title:** I built a native Mac LaTeX editor for writing papers. Here's what it does and doesn't do.
>
> I'm the developer, so read this as a maker post.
>
> ModernTex is a macOS-only LaTeX editor built around manuscript writing. The things
> that made me build it instead of using TeXShop or Texifier: compile errors explained
> in plain language with the line that caused them; BibTeX completion that searches
> the whole .bib by author or title; multi-file navigation across a paper's chapters;
> and checks for the things journals bounce on, plus an anonymized export for review.
>
> What it doesn't do: bundle a TeX distribution (you need MacTeX or TinyTeX), run on
> Windows or Linux, or have a track record. It's 1.0.2 and a week old.
>
> Free 7-day trial, no account, then $10 once with updates included. If the rules
> allow a link I'll put it in a comment. Mostly I'd like to know what a room full of
> LaTeX users thinks is missing, and what you'd want in the next update.

### Week 3: r/macapps

This sub expects developer posts and usually requires a specific flair for them and
a disclosure. Check the sidebar for the flair name and whether promo codes are
allowed; a handful of free licenses for commenters tends to be welcomed there.

> **Title:** ModernTex, a native LaTeX editor for academics writing papers ($10, one-time)
>
> Developer here. ModernTex is a LaTeX editor for macOS built for people writing
> journal articles and dissertations. Native app, not Electron, not a web wrapper.
>
> Compared with TeXShop (free, ships with MacTeX) it adds multi-file manuscript
> navigation, BibTeX completion by author or title, compile errors in plain language,
> and journal submission checks. Compared with Texifier it is narrower on purpose and
> a third of the price. It needs MacTeX or TinyTeX installed; it doesn't bundle one.
>
> macOS 14+, Apple silicon and Intel. Free 7-day trial, no account, then $10 once
> with updates included. v1.0.2. Try it and tell me what's wrong with it; feature
> requests from people who actually write in LaTeX decide what 1.1 gets.

### Week 4: Mac Power Users forum (talk.macpowerusers.com)

A forum, not Reddit, with a large academic contingent and long-running threads about
writing workflows. Search first for existing LaTeX or academic-writing threads and
reply there with the app as one option among several; if none is current, a short
post in the software category, same disclosure, same shape as the r/LaTeX draft but
shorter and without the "rules" hedging.

### Also, but only as answers: TeX StackExchange and LaTeX.org

Never a post. If a question is about Mac editors, plain-language error messages, or
BibTeX workflow and ModernTex is one of two or three fair options, answer the question
properly and mention it as one option with the disclosure. One good answer is worth
more than any post above; a promotional one is removed and remembered.

## Tier 3: curators and bloggers (one pitch each, spaced over the two weeks)

These are people who maintain "apps for academics" lists. They are far more reachable
than press and the lists rank. Offer a license, expect nothing.

**Pitch template** (personal email, plain text, edit the first line for each):

> **Subject:** PITCH: ModernTex – Mac LaTeX editor for academic manuscripts
>
> Hi [name],
>
> [One line that shows you read their list: which entry is closest, e.g. "Your
> researchers' list has Texifier and Overleaf under writing."]
>
> I built ModernTex, a native Mac LaTeX editor for writing papers and dissertations,
> because the existing editors treat a manuscript as a text file. It navigates a
> multi-file paper, completes BibTeX by author or title across the whole
> bibliography, explains compile errors in plain language, and checks the things
> journals reject on before you upload. Free 7-day trial, then $10 once. macOS 14+,
> needs MacTeX.
>
> I'm an academic; it started as the editor I wanted for my own papers. If it fits
> your list I'd be glad to send a license so you can form your own view. If it
> doesn't, no reply needed.
>
> Ben Ampel
> https://purplelink.llc/moderntex/

Targets, in order of fit:

| Target | Why | Route |
|---|---|---|
| SupaSidebar, "Best Mac Apps for Researchers and Academics in 2026" | Exactly the list; Mac-specific | Contact via the site |
| Adam DJ Brett, "Apps and Tools for Research and Writing" | Academic, maintains a curated tools page | adamdjbrett.com contact |
| ella yvonne, "MacBook apps for productivity in grad school" | Grad-school audience, Mac | ellayvonne.com contact |
| Exordo, "The 10 best productivity apps for academics" | Academic conference software blog, high authority | Editorial contact on site |
| University LibGuides with a LaTeX page (Harvard's guides.library.harvard.edu/overleaf/latex is one; search "libguides latex" for others) | .edu links; librarians curate tool lists | Subject-librarian email template in the distribution kit |
| Recapio, CraftNote "apps for researchers" posts | Lower fit, content-marketing blogs | Only if the above go well |

**MacStories and TidBITS:** low fit. TidBITS' own pitching guide (July 2026)
says they don't cover "highly specialized professional tools because too few of our
readers would care," and warns against pitches that don't state the competition. A
LaTeX editor is that tool. If you pitch anyway, use the template above exactly: their
required subject format is `PITCH: AppName – function with no adjectives`, they want
the competition named (TeXShop, Texifier, Overleaf), the backstory, and an answer to
how much of the code was written with AI. Expect a no.

## Tier 4: your own channels (free, do them first)

- **LinkedIn founder post.** The LinkedIn drafts cron already runs; give it the
  launch. Founder-voice posts about a product's origin do well there and the profile
  link counts. Lead with the problem (compile errors nobody can read), not the app.
- **Bluesky and Mastodon** (mathstodon.xyz, fediscience.org): one short post each,
  same disclosure. Academic Mastodon is small and kind to maker posts that are plain.
- **The site's own guide** already covers it. When the first review arrives, add it.

## Calendar

| Day | Do |
|---|---|
| Day 1 | LinkedIn post, Bluesky, Mastodon: the trial is the news. |
| Day 2 | AlternativeTo, awesome-LaTeX PR. |
| Day 3 | MacUpdate, SaaSHub. |
| Day 4 | Join MacOSX-TeX list and Mac Power Users; read, don't post. |
| Day 5 | Launching Next, Fazier, Uneed. Bluesky, Mastodon. |
| Day 8 | Show HN (weekday, 8–10am ET). |
| Day 9 | MacOSX-TeX announcement. First two blogger pitches. |
| Day 10 | Product Hunt (Tue–Thu). |
| Day 15 | r/LaTeX. Two more blogger pitches. |
| Day 22 | r/macapps. LibGuides emails. |
| Day 29 | Mac Power Users. |

## Measurement

- Search Console → Links: external links should start appearing within two to four
  weeks of the directory listings.
- `/stats/` referrers: each community shows up by hostname the day you post.
- `sales.mjs` in the daily dashboard: ModernTex orders by day, against the calendar.
- The guide's near-miss queries: links are what move "latex editor mac" off page two.

## Do not

- Post the same text in two places. Every draft above is deliberately different.
- Buy upvotes, use an upvote pod, or ask the six buyers to upvote anything but
  Product Hunt (where it is normal).
- Submit to mass-directory services or anything that "syndicates" a listing.
- Reply to criticism with marketing. Reply with a fix or a "you're right."
