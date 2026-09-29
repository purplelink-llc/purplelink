# Scholar Utility Belt: Chrome Web Store update text (v0.6.x Pro tier)

Paste-ready text for the Chrome Web Store developer dashboard. Every claim
below is grounded in the extension repo (`/Volumes/Extreme SSD/Chrome Scholar
Extension`, read-only): `src/sw.js`, `src/common/extpay.js` (ExtPay SDK),
`src/common/entitlement.js`, `manifest.json`, README, and
`docs/superpowers/specs/2026-09-20-freemium-monetization-design.md`.
Update the store listing in the same release that ships the Pro tier; the
public page at https://purplelink.llc/scholar-utility-belt/ already says the
same things.

## What the code actually does (basis for every answer)

- `EXTPAY_ID = "scholar-utility-belt"`; `extpay.startBackground()` runs at
  service-worker start. Constructing ExtPay makes no request.
- `getEntitlementStatus` (sw.js): if `chrome.storage.local.grandfathered` is
  true, it answers locally and never calls ExtPay. Otherwise it calls
  `extpay.getUser()`.
- `getUser()` (extpay.js `fetch_user`): if no ExtPay API key is stored, it
  returns `paid: false` locally with no request. So a free, non-grandfathered
  install that never clicks Unlock or "Already purchased" makes no request to
  extensionpay.com.
- Keys are created only in `openPaymentPage` / `openLoginPage` (extpay.js
  `create_key`): `POST https://extensionpay.com/extension/scholar-utility-belt/api/new-key`
  with an empty JSON body (`{"development": true}` only for unpacked dev
  builds). The returned key is stored as `extensionpay_api_key` in
  `chrome.storage.sync` (falls back to local). Chrome Sync can therefore copy
  it to the user's other browsers.
- Once a key exists, every non-grandfathered entitlement check does
  `GET https://extensionpay.com/extension/scholar-utility-belt/api/v2/user?api_key=<key>`
  and caches the response as `extensionpay_user` in `chrome.storage.sync`.
  The extension code reads `paid` and `plan.nickname` from it. It also stores
  `extensionpay_installed_at` (a local timestamp) in sync storage.
- After a payment, a content script (`dist/common/extpay.js`, matches
  `https://extensionpay.com/*`) relays a message so the background polls the
  user endpoint for up to 2 minutes, once per second.
- Grandfathering (`onInstalled`, sw.js, `decideGrandfathered`): any reason
  other than `"install"` sets `grandfathered = true` once and never changes it.
  `"install"` sets false. Local storage is wiped on uninstall, so a
  reinstall is a new install and is not grandfathered.
- The extension makes no request to purplelink.llc or any Purplelink server.
  Other network use is the optional public-API lookups (host permissions:
  api.crossref.org, api.openalex.org, api.unpaywall.org, api.datacite.org,
  opencitations.net, export.arxiv.org, www.ebi.ac.uk, eutils.ncbi.nlm.nih.gov,
  api.ror.org, dblp.org, sparql.dblp.org, api.semanticscholar.org,
  icite.od.nih.gov, www.scimagojr.com) plus optional `<all_urls>` host access.
- License in the repo is ISC (LICENSE, README), not MIT.

## Short description (132 characters max)

```
Journal rankings (ABDC, FT50, UTD24), citation analytics, author metrics and lineage trees on Google Scholar. Free core, optional Pro.
```

## Detailed description

```
Scholar Utility Belt adds journal quality badges, citation analytics, author metrics, academic lineage trees and research trend tracking to Google Scholar results and author profiles.

FREE, FOREVER
- Journal quality badges: ABDC, FT50, UTD24, VHB, SJR quartile, ERA, ABS, CORE, CCF, Norwegian Register, FNEGE, and impact factor quartiles, from lists bundled with the extension.
- Citation velocity and an "Emerging" signal for recent papers.
- Author profile summary metrics: h-index, m-index, L-index, g-index, h5-index and open-access share.
- Search-result actions: save, BibTeX export, abstract preview, PDF and DOI lookup.
- A local library with notes, tags and collections, with import and export.
- Query trend tracker, retraction alerts, tortured-phrase warnings and related works.
- Dark mode.

PRO (optional)
Pro adds workflow tools: author compare, citation lineage, extended bibliometrics (p-index, FWCI, Relative Citation Ratio, influential citations), narrative CV, the systematic-review workspace, the citation-graph overlay, and the Publish-or-Perish report.
Prices: $40 once, or $3 a month, or $20 a year.
If you installed before version 0.6.0, every feature you had stays free permanently. A fresh install, including reinstalling after removing the extension, counts as a new install.

PRIVACY AND NETWORK CALLS
- No account, no analytics, and no Purplelink server. Your library and settings stay in the extension's storage in your browser. Nothing about your searches or reading is sent to the developer.
- Optional lookups go directly from your browser to public scholarly services (OpenAlex, Crossref, Unpaywall, OpenCitations, Semantic Scholar, DBLP, NIH iCite, PubMed, Europe PMC, ROR). A request carries what the lookup needs, such as a DOI, a title, an author name or a search term.
- Pro licensing uses ExtensionPay (extensionpay.com), with Stripe for payment. If you never open the payment or sign-in page, the extension makes no request to ExtensionPay. When you click Unlock or "Already purchased", it requests a random per-install key and stores it in extension storage, which Chrome may sync through your Google account. After that, each Pro status check sends that key to extensionpay.com and receives your plan and paid status. Installs updated from a version before 0.6.0 skip the license check entirely.
- Privacy policy: https://purplelink.llc/privacy/#scholar-utility-belt

Works on Google Scholar country domains. Open source under the ISC license.
```

## Privacy policy URL

```
https://purplelink.llc/privacy/#scholar-utility-belt
```

(The anchor is `id="scholar-utility-belt"` on the Scholar Utility Belt
paragraph in the "What we collect" section of `site/privacy/index.html`.)

## Single purpose statement

```
Adds journal quality rankings, citation and author metrics, and research tools to Google Scholar search results and author profiles. The optional Pro license check exists only to unlock the paid tools within that same purpose.
```

## Permission justifications (unchanged, plus the ExtensionPay host)

- `storage`, `unlimitedStorage`: saved papers, notes, settings, caches, and the
  ExtensionPay key and license status.
- `downloads`: smart-rename of PDFs and exports.
- Google Scholar hosts: inject badges and tools into Scholar pages.
- Scholarly API hosts: optional lookups for citations, retractions, open
  access and trends.
- Content script on `https://extensionpay.com/*`: passes payment confirmation
  from the ExtensionPay checkout page back to the extension. Reads nothing
  from the page beyond ExtensionPay's own message.

## Privacy practices tab

Chrome's tab asks which user data is collected (transmitted off the device).

| Data type | Check? | Justification |
|---|---|---|
| Website content | Yes | Paper titles, DOIs, author names or search terms from the Scholar page are sent to the public scholarly APIs listed above to fetch citation, retraction, open-access and trend data. Not sent to the developer. |
| Authentication info | Yes (recommended) | The random per-install ExtensionPay key is a license credential sent to extensionpay.com to verify Pro status. |
| Web history | Decide (see open questions) | Search terms and visited-paper identifiers are sent to the APIs only as lookup parameters; nothing is logged or sent to the developer. |
| Personally identifiable info | No (see open questions) | The extension does not read or send a name or email. Checkout details are entered on ExtensionPay's and Stripe's hosted pages. |
| Financial and payment info | No (see open questions) | Card details are entered only on Stripe's hosted checkout via ExtensionPay; the extension never sees them. |
| Health, personal communications, location, user activity | No | Not collected. |

Use justifications for each checked type: "App functionality" only. Do not
tick advertising, analytics or personalization.

Certifications (all can be ticked):
- I do not sell or transfer user data to third parties, outside of the approved
  use cases (the lookups and license check above serve the single purpose).
- I do not use or transfer user data for purposes unrelated to the item's
  single purpose.
- I do not use or transfer user data to determine creditworthiness or for
  lending purposes.

## Open questions for the owner

1. License mismatch: the repo (LICENSE, README badge) is ISC. The site said
   MIT; the site now says ISC. If MIT was intended, change the repo instead.
2. Whether "Web history", "Financial and payment info" and "Personally
   identifiable info" should be checked is a judgment call. The code sends
   no email or card data, but ExtensionPay's response object is not
   inspectable from the SDK (it may include the checkout email); confirm in
   the ExtensionPay dashboard or by logging one real response.
3. Confirm what ExtensionPay's `api/v2/user` response contains (email,
   plan, dates) before finalizing the "receives your plan and paid status"
   wording.
4. Confirm what the optional lookups send exactly per feature (Query Trend
   Tracker sends the search terms to OpenAlex; author features send author
   names or profile ids). The disclosure lists "a DOI, a title, an author
   name or a search term" from the README, not from a per-feature audit.
5. The listing's Homepage/Support URL points to `github.com/bampel/ScholarUtilityBelt`,
   the README points to `github.com/BenAmpel/ScholarUtilityBelt`, and the site
   links `github.com/purplelink-llc`. Pick one.
6. `STORE_LISTING.md` in the extension repo still describes v0.4.0 with no
   privacy URL; update it to match this file.
7. Who receives ExtensionPay purchase emails and how long ExtensionPay keeps
   data is not in the repo; the privacy page defers to their policy.
8. Grandfathering is per install profile: a user who removes and reinstalls
   loses free access to Pro features. The page states this; decide whether
   you want that policy.
