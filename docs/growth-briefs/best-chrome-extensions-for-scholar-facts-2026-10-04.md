# Fact table: best Chrome extensions for Google Scholar (guide)

Date checked: October 4, 2026. Method: competitive-landscape-research skill. Tier 1 = the Chrome Web Store (CWS) listing fetched live, the vendor's own site or official docs. Tier 2 = independent named source. Tier 3 = aggregator or search snippet (never used alone for a load-bearing fact).
Store pages were fetched with curl (page HTML, version, updated, users, rating) and with WebFetch (description, privacy labels). A CWS URL for a removed or unknown item redirects to a slug of `empty-title`; that was used as the "listing not found" test.
"Privacy label" = the developer's own self-declaration on the CWS Privacy practices tab, not an audit.

Article: `site/guides/best-chrome-extensions-for-google-scholar/index.html`

## Corrections to the brief

| Brief said | Found | Handling |
|---|---|---|
| Open Access Button | OA.Works discontinued it on 2025-11-18 and points users to Unpaywall (openaccessbutton.org). An old CWS listing (v oabutton_5.0.0, Oct 6, 2025) still resolves. A separate listing, "Open Research Button" by PaperPanda (v2.3.0, Aug 6, 2026), also resolves; its relationship to OA.Works was not established. | Dropped from the tool list. One hedged line in the guide. |
| CORE Discovery / CORE Reader | CWS id ockidfiihjhkngdalfnbeeepgfbmkmlh redirects to `empty-title` (not found). core.ac.uk/services/discovery returned HTTP 403. | Dropped. Stated in the guide that I could not confirm a live listing. |
| Semantic Scholar extension | The extension FAQ (semanticscholar.org/faq/browser-extension) links CWS id kboocjlbbkedggcpllfoigfnhieejebk, which redirects to `empty-title`. | Dropped. Stated in the guide. |
| RetractOMatic | CWS id afopanbkaaojicelmcniljbdphjagpie redirects to `empty-title`. | Dropped (not mentioned). |
| Citicious (retraction + fake-citation checker) | GitHub repo only found; no CWS listing confirmed. | Dropped (not mentioned). |
| Papers Without Borders | Nothing found under that name. | Dropped (not mentioned). |
| Consensus, Elicit, Connected Papers, ResearchRabbit as extensions | No CWS extension confirmed for Consensus, Connected Papers or ResearchRabbit (ResearchRabbit homepage mentions no extension). Elicit does have a CWS extension, but it is for institutional full-text retrieval inside Elicit systematic reviews. | Described as web apps. Elicit extension described for what its listing says. |
| Scholar Utility Belt page: "ranking lists focus on ABDC, FT50, UTD24, SJR" | The CWS listing says ABDC, FT50, UTD24 and CORE are bundled; the GitHub README lists FT50, UTD24, ABDC, VHB, CORE/ICORE, CCF, SCImago, ERA (also ABS, Norwegian register, venue h5). The site page names SJR; the CWS listing does not name SJR in the free-features line. | Guide says ABDC, FT50, UTD24, CORE on the store listing; README lists more. Weakness stated as: strongest for business, information systems and computing venues; outside those, mostly SJR quartiles. |
| Scholar Utility Belt "does not find full text" | The source has a PDF action (publisher PDF, arXiv/SSRN link, else search) and an Unpaywall-based open-access flag/filter and OA PDF link. The CWS listing says "lookup PDFs and DOIs". | Guide says it opens the best PDF link it can find and flags open access, but does not know your library subscriptions and is not a full-text finder. |
| Scholar Utility Belt "does not manage references" | It has a local library with notes, tags, collections, import/export, and BibTeX export. No citing in a word processor. | Guide says it is a saved-paper list, not a reference manager. |
| Site page GitHub link `github.com/purplelink-llc` | The repo the CWS listing and the local checkout use is `github.com/BenAmpel/ScholarUtilityBelt` (ISC, v0.6.2, 82 commits per page, 2 stars). The org URL returns 200 but the repo is not confirmed there. | Guide links the BenAmpel repo. Flagged to owner: site page link may be stale. |
| Published version | CWS: 0.6.2, updated October 2, 2026. Local source at /Volumes/Extreme SSD/Chrome Scholar Extension is 0.7.0 (unpublished; adds a 14-day trial and an opt-in App Pass unlock via joinapppass.com). | Guide describes 0.6.2 behavior only. 0.7.0 features not mentioned. Flagged to owner. |

## Scholar Utility Belt (ours)

| Fact | Value | Tier | Source | Conflicts |
|---|---|---|---|---|
| Users | 1,000 | 1 | CWS listing (curl, 2026-10-04) | Site page says "about 1,000", matches |
| Rating | 4.5 from 16 ratings | 1 | CWS listing | matches site page |
| Version / updated | 0.6.2, October 2, 2026 | 1 | CWS listing | local source is 0.7.0 |
| Price | Free core; Pro $40 once, $3/month, $20/year | 1 | CWS listing + Purplelink site page | none |
| Pro features | Author compare, citation lineage, extended bibliometrics (p-index, FWCI, RCR, influential citations), narrative CV, systematic-review workspace, citation-graph overlay, Publish-or-Perish report | 1 | CWS listing, README | none |
| Pre-0.6.0 installs keep features free | yes | 1 | CWS listing, README, site page | none |
| License | ISC | 1 | GitHub page, LICENSE file | none |
| Free features | Quality badges, citation velocity, "Emerging" signal, author metrics (h, m, L, g, h5, OA %), search actions (save, BibTeX, abstract preview, PDF/DOI lookup), local library with notes/tags/collections, trend tracking, retraction alerts, tortured-phrase warnings, related works, dark mode | 1 | CWS listing | site page omits PDF lookup |
| Rankings shipped inside the extension | yes; badges need no network request | 1 | CWS listing, README, source (src/data/*.csv) | none |
| Retraction check | Bundled Retraction Watch-derived list (bloom filter, src/data/retraction_bloom.json); if that list is not loaded, falls back to a Crossref lookup per DOI (`updated-by` field) | 1 | source (data-loader.js, content.js); v0.6.1 tag also has both | README says only "retraction-watch screening badges" |
| Optional lookups | OpenAlex, Crossref, Unpaywall, OpenCitations, Semantic Scholar, DBLP, NIH iCite, PubMed, Europe PMC, ROR (manifest also lists DataCite, arXiv, SCImago) | 1 | site page, README, manifest.json | manifest host list is slightly longer than the site list (DataCite, arXiv, scimagojr.com) |
| Pro license check | extensionpay.com; key sent on each status check once the user has opened the payment/sign-in flow; no request if never opened; pre-0.6.0 installs skip it | 1 | site page, README | none |
| Analytics / Purplelink server | none | 1 | CWS privacy text "No account, no analytics, and no Purplelink server", site page, privacy page | none |
| Optional broad permission | Options page has a button requesting `<all_urls>` optional host permission; not requested unless clicked | 1 | source (options.js), manifest.json | not on the site page; guide mentions it briefly |
| CWS privacy label | Authentication information, website content | 1 | CWS listing | none |
| Browsers | Chrome only | 1 | site page FAQ, CWS | none |

## Other tools

| Tool | Fact | Value | Tier | Source | Conflicts |
|---|---|---|---|---|---|
| Rapid Journal Quality Check | CWS | v4.1.4, May 21, 2026; 200,000 users; 4.3 (66); free; developer jrk.devgit | 1 | CWS listing | none |
| | Lists | SJR, ABDC, ABS, VHB, FT50, CORE, CCF, BFI, CNRS, FNEGE, HCERES, SCImago country rank | 1 | CWS listing | search snippet omitted some |
| | Other | open source (GitHub JuRaKlWi/Rapid-Journal-Quality-Check); journal-name search bar; privacy label "will not collect or use your data" | 1 | CWS listing | none |
| ExCITATION | CWS | v1.4.1, Aug 3, 2026; 200,000 users; 4.5 (108); free, "no premium tier required for any feature" | 1 | CWS listing | none |
| | Lists/features | SJR (32,000+ journals), ABS AJG 2024, ABDC 2025; predatory-journal flag; sort by citations; abstract preview | 1 | CWS listing | none |
| | Privacy label | PII, user activity, website content | 1 | CWS listing | none |
| Scholar H-Index Calculator | CWS | v4.4.1, Sep 2, 2026; 10,000 users; 4.3 (54); free; developer Agelin Bee | 1 | CWS listing | none |
| | Features | computes common bibliometric indices on Scholar pages, custom formulas, removes self- and ghost-citations, completes truncated author lists, clusters homonyms; runs in the browser with no backend; optional "refine" visits publisher pages | 1 | CWS listing | none |
| Google Scholar Button | CWS | v3.6, May 16, 2024; 3,000,000 users; 4.6 (1.4K); free; Google Ireland | 1 | CWS listing | none |
| | Features | find full text on the web or via your library; send a web query to Scholar; formatted citations; save to Scholar library; library proxy; US case law | 1 | CWS listing | none |
| | Privacy label | declares PII handling | 1 | CWS listing | none |
| Google Scholar PDF Reader | CWS | v0.5.2, Jun 5, 2026; 2,000,000 users; 4.1 (713); free; Google Ireland | 1 | CWS listing | none |
| | Features | reference previews, outline, figure jumps, highlighting, cite and save | 1 | CWS listing | none |
| Google Scholar Alerts / My library / Cite export | Alerts via the envelope icon, no Google account needed; Save to library with labels, private unless profile public; Cite offers BibTeX, EndNote, RefMan, RefWorks | 1 | scholar.google.com/intl/en/scholar/help.html | none |
| Zotero Connector | CWS | v5.0.217, Oct 1, 2026; 8,000,000 users; 4.0 (2.5K); free; Corporation for Digital Scholarship; label "will not collect or use your data" | 1 | CWS listing | none |
| | Zotero | 300 MB free storage; 2 GB $20/yr, 6 GB $60/yr, unlimited $120/yr | 1 | zotero.org/storage | page does not say the software is free; Zotero is widely known as free, hedged as "free software, paid storage" |
| | Scholar behavior | multiple-result save button; in Google Scholar first star items to My Library, then export | 1 | zotero.org/support/adding_items_to_zotero | none |
| | Retraction alerts | Retraction Watch partnership, announced June 14, 2019, Zotero 5.0.67; DOI or PMID items only (about 75% of RW data) as of that post; warns when citing | 1 | zotero.org/blog/retracted-item-notifications | 2019 post, limits may have changed |
| | Data source | Crossref acquired the Retraction Watch database in September 2023 and made it public | 1 | crossref.org/documentation/retrieve-metadata/retraction-watch | none |
| Paperpile Extension | CWS | v1.5.1188, Sep 28, 2026; 300,000 users; 4.6 (194); extension free but needs a Paperpile account; label PII, web history, user activity, website content | 1 | CWS listing | none |
| | Pricing | annual billing only; 30-day trial; 50% academic discount listed; Regular and Expert tiers; figures read as $4.15 and $5.75 per month | 1 | paperpile.com/pricing | page text ambiguous whether those are list or academic-discounted rates (it also printed "$8.30 annual"); hedged, no figure in guide |
| Mendeley Web Importer | CWS | v3.3.49, Mar 31, 2026; 3,000,000 users; 2.3 (3.1K); free; Elsevier; label: authentication info, location, web history, user activity, website content | 1 | CWS listing | none |
| Unpaywall | CWS | v3.99, Jan 8, 2025; 1,000,000+ users; 4.0 (283); free; label: location, website content | 1 | CWS listing | none |
| | Claim | index of about 20 million free legal PDFs (listing wording) | 1 | CWS listing | figure may be stale; guide says "its listing says" |
| LibKey Nomad | CWS | v1.60.0, Sep 22, 2026; 1,000,000+ users; 4.5 (17); free; Third Iron; supported by 2,000+ libraries in 35+ countries; label: location | 1 | CWS listing | thirdiron.com says "40+ countries" |
| | Needs library | extension asks you to pick your institution; links only for what your library subscribes to or open access | 2 | library guides (search results) + CWS description ("from your institution's subscriptions") | thirdiron.com page did not state subscription requirement |
| | Retraction flags | LibKey services alert on retracted articles using Retraction Watch data; Nomad buttons reported by library guides | 1 (Third Iron press release, Feb 14, 2022: "via our LibKey services, when researchers find a retracted article in a database or on a website") and 2 | prnewswire.com release; library guides | release does not name Nomad; hedged "reported as" |
| Lean Library | CWS | version differs between fetches (2026.10.0 seen in a snippet, 2026.11.0 on the fetched page); updated Oct 1, 2026; 200,000 users; 3.4 (142); free; label "will not collect or use your data" | 1 | CWS listing | version not stated in guide |
| | Features | institution's resources, reference saving, highlighting, annotation, journal alerts, article retraction alerts and trust ratings; institution selection needed; "Lean Library Open" for people without an institution | 1 | CWS listing | none |
| EndNote Click | CWS | v3.5.0, May 28, 2025; 6,000,000 users; 4.0 (379); free; Clarivate; label: PII, authentication, location, web history, user activity, website content | 1 | CWS listing | none |
| | Features | one-click PDF access via library subscriptions and open access; works with Web of Science, PubMed, arXiv, Scopus; integrates with Mendeley, EndNote, Dropbox, Zotero | 1 | CWS listing | none |
| scite | CWS | v1.40.0, Jul 1, 2026; 100,000 users; 4.1 (40); free; Scite Inc.; label "will not collect or use your data" | 1 | CWS listing | none |
| | Features | Smart Citation counts (supporting, contrasting, mentioning) on Google Scholar, PubMed and journal sites | 1 | CWS listing | none |
| | Pricing | scite.ai/pricing: 7-day trial; Basic $20/month "full platform access including ... Smart Citation reports"; Pro $50; Team $250. Page does not say whether the extension itself is free or what is free beyond the trial; CWS lists the extension as free. | 1 | scite.ai/pricing | extension free (CWS) vs reports in paid plan (pricing page): the guide says the extension is free and that full reports may sit behind a plan, check before relying on it |
| PubPeer | CWS | v1.7.1, Nov 29, 2024; 40,000 users; 3.7 (37); free; The PubPeer Foundation; label "will not collect or use your data" | 1 | CWS listing | none |
| | Features | shows links to existing PubPeer comments; silent unless the article has comments | 1 | CWS listing | none |
| Scholarcy extension | CWS | v5.4.0, Mar 14, 2026; 80,000 users; 4.0 (39); free extension, premium via Scholarcy Library subscription; label: location, website content | 1 | CWS listing | scholarcy.com/pricing returned 403; no price stated |
| | Features | summary flashcard, key points, links to open-access versions of references | 1 | CWS listing | none |
| Elicit extension | CWS | v1.5, Sep 4, 2026; 30,000 users; 4.5 (11); Elicit Research PBC | 1 | CWS listing | none |
| | Purpose | gets full-text papers for Elicit systematic reviews through your institutional access; credentials stay on your device (per listing/support page) | 1 | CWS listing, support.elicit.com | none |
| Elicit pricing | Basic free; Pro $49/month or $588/year; Scale $169/month | 1 | elicit.com/pricing | none |
| Consensus | pricing page returned no plan data (loaded without prices); no CWS extension confirmed | n/a | consensus.app/pricing | guide gives no price |
| Connected Papers | no extension confirmed; about page returned no pricing | n/a | connectedpapers.com/about | guide treats as web app, no price |
| ResearchRabbit | homepage: free to sign up; operated by Litmap Limited; no extension mentioned | 1 | researchrabbit.ai | search snippet said an extension exists; unconfirmed |
| Scholar Inbox | meta description: free personal paper recommender; indexes arXiv, bioRxiv, medRxiv, ChemRxiv, open-access CS proceedings; no extension found | 1 | scholar-inbox.com (curl) | none |
| Publish or Perish | free to download; Windows, macOS, Linux via emulator; version 8 (Nov 1, 2021) per page; sources: Crossref, Google Scholar, Google Scholar Profile (login required since April 2025), Lens, OpenAlex, PubMed, Scopus (free API key), Semantic Scholar (free API key), Web of Science (paid), external import; "We cannot guarantee the continued availability of any of these data sources" | 1 | harzing.com/resources/publish-or-perish and /manual/using/data-sources | page's version text looks old; hedged |
| LitRank | v1.6.0, Aug 9, 2026; 128 users; free, "no paid tier and none is planned"; quartiles, SJR, h-index, OA flag, filters; data ships inside the extension | 1 | CWS listing | none |
| Journal List | v1.3.0, Aug 16, 2026; 184 users; free; ABS, ABDC, FT50, UTD24, FMS, CCF, JCR | 1 | CWS listing | none |
| Journal Check (journal-check.com) | vendor site says SJR, ABDC, CORE, FT50 on Scholar, PubMed, arXiv, Semantic Scholar; "DOI and ISSN" sent to its servers; planned $4.99/month tier. No CWS listing confirmed (a "DZ Journal Check" listing for Algerian lists is a different tool). | 1 (vendor) | journal-check.com | CWS unconfirmed, so dropped |
| Open Research Button | v2.3.0, Aug 6, 2026; 30,000 users; 4.4 (59); free; PaperPanda | 1 | CWS listing | relationship to OA.Works unknown |
| Sci-Hub-style tools | not covered; not recommended | n/a | n/a | n/a |

## Facts stated in the guide with hedging
- Store privacy labels are the developer's own declaration; not audited.
- Whether the rival extensions have retraction or tortured-phrase warnings was not established; the guide says I did not see them listed, not that they lack them.
- Stacking several Scholar-injecting extensions: not tested; the guide says so.
- No other tool was installed or tested; everything is from listings and vendor pages. Scholar Utility Belt behavior comes from reading its source and listing.
