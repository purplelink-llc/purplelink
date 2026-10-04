# Fact table: best PII redaction tools for ChatGPT and AI chats

Checked 2026-10-04 for `site/guides/best-pii-redaction-tools-for-chatgpt/index.html`. Method: `competitive-landscape-research`.
Tiers: 1 = vendor's own page, store listing, project repo, or the legal text itself; 2 = named independent source;
3 = aggregator or search summary (never stated flatly in the article).

Reading notes:

- WebFetch returns a model-written summary of a page, not the page. Rows marked "fetch summary" were read that way and the
  article words them conservatively.
- `help.openai.com`, `openai.com`, and `hhs.gov` returned HTTP 403 to every automated fetch, and the Browser pane was denied.
  OpenAI rows therefore rest on the text of those pages as quoted in search excerpts (marked "excerpt"). The article names
  OpenAI's pages as the source but does not quote them and does not state numbers beyond the 30-day temporary-chat figure.
- Prices were read on the vendor page on 2026-10-04 unless a row says otherwise. Prices change.

## Outbound Veil (Purplelink, own product)

| Fact | Value | Tier | Source | Checked | Conflicts |
|---|---|---|---|---|---|
| Price | $29 one-time, 7-day free trial, no account, updates included | 1 | `site/outbound-veil/index.html` | 2026-10-04 | none |
| Platform | macOS 14 or later, Apple silicon and Intel, Mac only | 1 | same | 2026-10-04 | none |
| Where checking runs | On the Mac; nothing typed is stored or sent; no analytics; network only for update check and buyer download | 1 | same | 2026-10-04 | none |
| What it reads | The focused text field, via macOS Accessibility; Input Monitoring only if send hold is turned on | 1 | same | 2026-10-04 | none |
| What it does | Badge with count, highlights, per-finding Ignore, Redact all, optional send hold in apps you choose | 1 | same | 2026-10-04 | none |
| Placeholders | Labelled placeholders such as [SSN_1], [EMAIL_1] | 1 | same | 2026-10-04 | none |
| Tested apps | TextEdit, Notes, Word (word-by-word highlight); Messages (badge, Redact all, send hold example); Chrome text areas (word by word in plain area; whole-field outline in ChatGPT and claude.ai prompts) | 1 | same | 2026-10-04 | none |
| Not tested | Safari, Slack, VS Code, ChatGPT or Claude desktop apps (findings), a real password field | internal | `OutboundVeil/docs/compatibility.md` | 2026-10-03 | product page says only "tested with the apps below" |
| Mail | Compose body could not be read in testing (web area with no text) | internal | `OutboundVeil/docs/compatibility.md` | 2026-10-03 | product page says generally that some apps are unreadable |
| Terminal | Off by default | internal | same | 2026-10-03 | not on product page; not used in article |
| Names | Latin script only | 1 | product page Limits | 2026-10-04 | none |
| Public figures | Flagged too; Ignore exists | 1 | product page Limits | 2026-10-04 | none |
| Accuracy | Will miss some things and can flag things that are not personal information | 1 | product page Limits | 2026-10-04 | none |
| Compliance | Not a compliance product | 1 | product page Limits and FAQ | 2026-10-04 | none |
| Model | Rampart (National Design Studio), CC BY 4.0; Purplelink ported processing to Swift, added rules for date of birth, medical record number, IBAN; model file unchanged | 1 | product page Credit; `OutboundVeil/NOTICE.md` | 2026-10-04 | none |
| Original values after Redact all | Held in memory only, dropped when focus moves to another field; the app does not put them back into a reply | internal | design spec section 7 | 2026-10-03 | not stated on product page; article says "does not restore" and says v1.0.0 |
| City, state, ZIP | Classified then dropped by default; a street line is reported | internal | design spec section 4.5 | 2026-10-03 | not on product page |
| Release | 1.0.0 | 1 | product page | 2026-10-04 | none |

## Rampart (the detector Outbound Veil uses)

| Fact | Value | Tier | Source | Checked | Conflicts |
|---|---|---|---|---|---|
| License | CC BY 4.0; training data OpenPII 1.5M also CC BY 4.0 | 1 | https://github.com/nationaldesignstudio/rampart (fetch summary) | 2026-10-04 | none |
| Model | 14.7 MB Q4 ONNX token classifier plus pattern rules; runs client-side | 1 | same | 2026-10-04 | none |
| Languages | Seven Latin-script languages about 98% recall; names in non-Latin scripts about 14% recall in aggregate (Russian 2%, Arabic 5%, Hindi 6%, Han Chinese 9%, Korean 15%, Japanese 46%) | 1 | same | 2026-10-04 | matches Outbound Veil spec |
| Self-description | "harm reduction, not perfect protection"; adversarial inputs bypass; indirect identifiers unaddressed | 1 | same | 2026-10-04 | none |

## Predact

| Fact | Value | Tier | Source | Checked | Conflicts |
|---|---|---|---|---|---|
| Price | Free, no card; unlimited documents and redactions; email address needed to get the download link | 1 | https://predact.app | 2026-10-04 | none |
| Platform | Mac (macOS Sonoma 14 or later recommended, Apple silicon supported) and Windows | 1 | same | 2026-10-04 | none |
| Inputs | PDFs, Word, text files, email clippings, images, pasted clipboard text and screenshots | 1 | same | 2026-10-04 | none |
| Processing | Local; Safe Mode connects only when you export to an online LLM; Fully Offline Mode blocks all network and disables built-in browser | 1 | same | 2026-10-04 | none |
| Typing in other apps | Page does not describe monitoring typing in other apps or browsers | 1 (absence) | same | 2026-10-04 | none |
| Extras | "Persona filtering" substitutes consistent alternatives; built-in browser export to ChatGPT, Claude, Gemini, Perplexity; 67 MB | 1 | same | 2026-10-04 | none |

## PrivacyScrubber

| Fact | Value | Tier | Source | Checked | Conflicts |
|---|---|---|---|---|---|
| Plans | Free: 15,000 characters per scrub; Pro $15/month or $110 lifetime; Teams $99/month; SDK $299/month | 1 | https://privacyscrubber.com | 2026-10-04 | matches 2026-10-03 analysis |
| Platforms | Web app, Chrome extension (Manifest V3), MCP server (Cursor, Claude Desktop), Node.js SDK | 1 | same | 2026-10-04 | none |
| Extension sites | 12 platforms including ChatGPT, Claude, Gemini, Copilot, Grok, DeepSeek, Perplexity, Notion, Slack | 1 | https://privacyscrubber.com/features/chrome-extension/ | 2026-10-04 | store excerpt also says 12 |
| How it runs | Shield button in the chat box or Alt+Shift+X triggers local tokenizing; "Reveal Original Data" restores in the reply | 1 | same | 2026-10-04 | none |
| Processing | Claims 100% local in the browser tab, works with network off | 1 (vendor claim) | same | 2026-10-04 | not independently verified |

## Presidio

| Fact | Value | Tier | Source | Checked | Conflicts |
|---|---|---|---|---|---|
| What | Open-source framework to identify and anonymize PII in text, images, structured data; NER, regex, rules, checksums | 1 | https://presidio.dataprivacystack.org/ (fetch summary) | 2026-10-04 | none |
| License | MIT; 11.2k stars | 1 | https://github.com/microsoft/presidio (redirects to data-privacy-stack org) | 2026-10-04 | none |
| Deployment | Python library, PySpark, Docker, Kubernetes; processes data locally without external services | 1 | docs site | 2026-10-04 | none |
| Caveat | "there is no guarantee that Presidio will find all sensitive information" | 1 | GitHub README | 2026-10-04 | none |
| Stewardship | Moved from Microsoft's GitHub org to Data Privacy Stack; docs say "transitioning to a community-owned project" | 1 | docs site and GitHub redirect | 2026-10-04 | old microsoft.github.io page now redirects |

## Provider controls (OpenAI / ChatGPT)

| Fact | Value | Tier | Source | Checked | Conflicts |
|---|---|---|---|---|---|
| Temporary Chat | Not in history, no memory created or updated, not used to improve models while temporary; may be kept up to 30 days for safety | 1 (excerpt; page 403 to fetch) | https://help.openai.com/en/articles/8914046-temporary-chat-faq | 2026-10-04 | consistent across several search excerpts |
| Model-improvement setting | Settings > Data Controls > "Improve the model for everyone"; on by default for personal accounts per excerpts | 1/2 (excerpt) | https://help.openai.com/en/articles/7730893-data-controls-faq | 2026-10-04 | article says "check the setting" rather than asserting default |
| Business plans | ChatGPT Business, Enterprise, Edu and the API platform: business data not used for training by default unless the customer opts in | 1 (excerpt) | https://openai.com/business-data/ | 2026-10-04 | none seen |
| Business Associate Agreement | Addendum PDF defines Eligible Services as "Services that are part of the OpenAI API and comply with the default usage policies by endpoint" | 1 | https://cdn.openai.com/osa/healthcare-addendum.pdf (version dated 111124 in header) | 2026-10-04 | aggregators say Enterprise and a healthcare product can also be covered, and that Business and consumer plans are not; not stated flatly in article |
| 2025 preservation order | May 13, 2025 order in NYT v. OpenAI to preserve output logs including deleted chats; ended Sept 26, 2025; earlier preserved data still held for some accounts | 3 (news and legal blogs via search) | search results (Malwarebytes, Gizmodo, llms-for-lawyers) | 2026-10-04 | article says "reported", names no numbers beyond 2025 |
| API retention | Up to 30 days for abuse monitoring; zero retention for qualifying customers | 3 (search summary) | search results | 2026-10-04 | NOT used in the article |

## Local models

| Fact | Value | Tier | Source | Checked | Conflicts |
|---|---|---|---|---|---|
| Ollama platforms | macOS, Linux, Windows | 1 | https://ollama.com/download | 2026-10-04 | none |
| Ollama cloud | Offers cloud models that run on Ollama's servers (names end `:cloud`); docs: "Ollama processes cloud prompts and responses"; "We do not use them to train models"; cloud features can be disabled | 1 | https://docs.ollama.com/cloud | 2026-10-04 | home page says "locally or in the cloud" |
| Ollama price | Download page lists none; not stated in the article | 1 (absence) | https://ollama.com/download | 2026-10-04 | none |
| LM Studio platforms | macOS, Windows, Linux; docs mention Apple silicon Macs | 1 | https://lmstudio.ai/download and docs | 2026-10-04 | Intel Mac support not confirmed; not stated |
| LM Studio price | $0 in the page's structured data | 1 (fetch summary of schema data) | https://lmstudio.ai/download | 2026-10-04 | not confirmed on a pricing page; article says "free to download" |
| LM Studio offline | "can operate entirely offline" once models are downloaded | 1 | https://lmstudio.ai/docs/app | 2026-10-04 | none |
| LM Studio privacy | Messages, chat histories and documents not transmitted when running locally; update checks send app version, OS and IP address | 1 | https://lmstudio.ai/privacy | 2026-10-04 | none |

## Further tools

| Tool | Fact | Value | Tier | Source | Checked | Conflicts |
|---|---|---|---|---|---|---|
| Veil (helloveil.com) | Price | $8/month, 14-day free trial, no account | 1 | https://helloveil.com | 2026-10-04 | matches 2026-10-03 analysis |
| Veil | Platform | macOS 14+, Windows 10+ | 1 | same | 2026-10-04 | none |
| Veil | What the app is | Records meetings, on-device transcription, AI summaries via Claude Haiku, searchable history; changelog (v3.1.0 March 1, 2026; 3.3.0 March 28, 2026) lists no clipboard or cross-app redaction | 1 (fetch summary) | https://helloveil.com and /changelog | 2026-10-04 | page says data does not leave device and also lists Haiku summaries; article does not characterise the data flow |
| Veil | SDK | VeilPhantom, Python, Apache 2.0, free; regex-only mode available; 19 entity types | 1 | https://helloveil.com/sdk/ | 2026-10-04 | none |
| RedactDesk | Facts | Free, MIT, macOS 14+, PDFs only, runs locally, uses OpenAI's open-source privacy-filter model, permanent redaction, made by the Elephas team | 1 | https://redactdesk.app | 2026-10-04 | 2026-10-03 table had tier 3; now tier 1 |
| BlurData | Price | Personal $79/year; personal lifetime $149; team $199/year for 5 Macs; team lifetime $349; 14-day money-back; no free tier mentioned | 1 | https://blurdata.app | 2026-10-04 | not retrieved on 2026-10-03; now retrieved |
| BlurData | Platform and inputs | macOS 13+, iOS version; JPG, PNG, PDF; on-device; 8 PII categories plus custom regex | 1 | same | 2026-10-04 | page says "GDPR and HIPAA-compliant"; NOT repeated |
| Caviard | Plans | Free: up to 10 protected values per document; lifetime $9 (listed as regularly $15.30, early discount); org pricing by email | 1 | https://caviard.ai/pricing | 2026-10-04 | 2026-10-03 note said paid tiers not shown; now shown |
| Caviard | Sites and processing | Chrome extension; ChatGPT and DeepSeek; masking on the device; detection described as regex patterns; Alt+R toggles original and redacted | 1 | https://caviard.ai | 2026-10-04 | none |
| ChatGPT Privacy Shield (redact.tools) | Plans | Free; Pro $9/month and Team $49/month both waitlist | 1 | https://redact.tools | 2026-10-04 | matches 2026-10-03 |
| ChatGPT Privacy Shield | Sites and processing | ChatGPT only; others "coming soon"; scanning in the browser; 14+ categories; optional unmask | 1 | same | 2026-10-04 | none |
| Rescriber | Facts | Chrome extension, free, MIT, ChatGPT only, runs the openai/privacy-filter model in the browser via Transformers.js, downloads model (about 30-50 MB) from Hugging Face on first use, Chrome 113+, CHI '25 paper from Northeastern's PEACH lab; 9 users listed on store | 1 | Chrome Web Store listing; https://github.com/PEACH-Research-Lab/Rescriber | 2026-10-04 | none |
| PII Scrubber (Microforge) | Facts | Chrome extension, ChatGPT; free 5 uses/day and 1,000 characters per use; Pro $7/month; 11 types; local; 9 users listed; updated May 9, 2026 | 1 | Chrome Web Store listing | 2026-10-04 | 2026-10-03 table said 10 users |
| Paste Redactor | Facts | Extension for Chrome, Edge, Firefox, Opera; free 100 redactions/month, $1/month or $9/year; MiniLM-L6 model, MIT weights on Hugging Face; developer warns it may miss PII; 7 users listed on Chrome store | 1 | https://redactor.negativestarinnovators.com/ ; Chrome Web Store | 2026-10-04 | vendor says 50+ types, store says 55; article says "about 50" |
| Nightfall | Pricing | Per-user, per-year, two editions (Foundation, Premier); no prices on page; contact sales or 7-day proof of value; coverage of browsers, endpoints, SaaS, AI apps | 1 | https://www.nightfall.ai/pricing | 2026-10-04 | directories report small deployments at $5,000-$15,000/year and one snippet a $10/user/month browser plan; unconfirmed and conflicting, NOT used |
| Microsoft Purview | Capability | Endpoint DLP can block paste and upload of sensitive info to AI app websites on managed devices; Browser Data Security in Edge inspects typed or pasted prompts to consumer AI apps including ChatGPT, Copilot, DeepSeek, Gemini; Network Data Security for other browsers | 1 | https://learn.microsoft.com/en-us/purview/deploymentmodels/depmod-data-leak-shadow-ai-step3 (ms.date 2026-03-31) | 2026-10-04 | licensing not stated on page; article does not state it |

## Added after a second search for Mac peers (found after the first draft; "only Mac app" claim dropped)

| Tool | Fact | Value | Tier | Source | Checked | Conflicts |
|---|---|---|---|---|---|---|
| ClipScrub | Price | $29 one-time, 14-day free trial | 1 (fetch summary) | https://clipscrub.com/ | 2026-10-04 | none |
| ClipScrub | Platform | macOS 15 or later; Apple silicon needed for AI-enhanced detection | 1 | same | 2026-10-04 | none |
| ClipScrub | Inputs and processing | PDFs, Word, screenshots, screen recordings (MP4/MOV), JSON, CSV, XML, PNG, JPG, clipboard text; on-device, no internet needed (vendor claim); started by a keyboard shortcut; does not monitor typing | 1 | same | 2026-10-04 | none |
| ClipScrub | Self-description | "not a compliance service, does not guarantee complete de-identification"; targets HIPAA Safe Harbor direct identifiers | 1 | same | 2026-10-04 | none |
| Clipmask | Price and platform | Free, no time limit; Apple silicon Macs only (M1-M5), macOS 14+ | 1 | https://predact.app/clipmask/ | 2026-10-04 | none |
| Clipmask | How it works | Copy as usual; Option+Space offers a redacted version to paste; detection on-device (vendor claim); only server contact is a licensed-version check; made by the Predact company | 1 | same | 2026-10-04 | none |
| PIIGuardAI | What | Open-source (MIT) Mac menu-bar local proxy; blocks requests to LLM provider domains containing PII patterns; regex only; trusts a self-signed root CA; 1 star, 4 commits at check | 1 | https://github.com/fujahgabriel/PIIGuardAI (fetch summary) | 2026-10-04 | none |
| Maskbase | What | Open-source (MIT) Mac app for PDF, DOCX, CSV, XLSX; on-device small language models; 4 stars, 10 commits at check; no typing monitoring | 1 | https://github.com/straightbackward/maskbase (fetch summary) | 2026-10-04 | none |
| Others seen, not covered | Redactify, secretshot, stream-guard, ClipRedactor, PasteSecure | Mentioned in search results only; not checked | 3 | search | 2026-10-04 | not used |
| "Watches typing" claim | Article says "I found no other that watches the typing itself, but I may have missed one" | hedge | n/a | searches on 2026-10-04 | 2026-10-04 | Veil, Predact, RedactDesk, BlurData, ClipScrub, Clipmask, Maskbase all act on pasted, copied or dropped input |

Article structure note: Veil (helloveil.com), ChatGPT Privacy Shield, Rescriber, PII Scrubber, Paste Redactor, PIIGuardAI and Maskbase appear in one "narrower options" paragraph rather than as headed sections, to keep the page near 40 KB.

## Regulation and professional-duty context

| Fact | Value | Tier | Source | Checked | Conflicts |
|---|---|---|---|---|---|
| HIPAA de-identification | 45 CFR 164.514(b): expert determination, or removal of listed identifiers (about 18 types, including names, geographic detail, dates, contact numbers, record and account numbers) with no actual knowledge the rest could identify the person | 1 (legal text via Cornell LII) | https://www.law.cornell.edu/cfr/text/45/164.514 | 2026-10-04 | hhs.gov page 403 |
| FERPA | Gives parents, and students once 18 or in postsecondary school, rights over personally identifiable information from education records | 1 | https://studentprivacy.ed.gov/faq/what-ferpa | 2026-10-04 | none |
| ABA Formal Opinion 512 | July 29, 2024; lawyers' confidentiality duty (Model Rule 1.6) applies to generative AI tools; informed consent needed for tools that train on inputs | 2/3 (bar association summaries) | https://www.americanbar.org/groups/business_law/resources/business-law-today/2024-october/aba-ethics-opinion-generative-ai-offers-useful-framework/ | 2026-10-04 | page itself not fetched; article states it in one hedged sentence |

## Not verified at tier 1 (and what the article does)

- OpenAI help and policy pages (403): rows above rest on excerpts. Article cites the pages by name, states only what excerpts agree on.
- Whether a given ChatGPT plan can be covered by a BAA: dropped; article says ask OpenAI.
- OpenAI API retention period: dropped.
- 2025 preservation order: hedged as "reported".
- Nightfall prices: dropped; "by quote".
- Microsoft Purview licensing: dropped.
- LM Studio licence terms for work use: not checked; article says "free to download".
- Ollama price: not stated.
- ABA Opinion 512 text itself: one hedged sentence.
- Vendor claims of local processing (PrivacyScrubber, Caviard, Privacy Shield, Paste Redactor, Predact, BlurData): worded as "says", not independently tested.
- Install counts (7 to 9 users on store listings for several extensions): stated as listed on 2026-10-04.
