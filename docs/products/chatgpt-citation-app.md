# Citation checker app (ChatGPT app and Claude connector)

One MCP server, three read-only tools, built on the BibTeX validator, the Retraction Checker and the DOI-to-BibTeX
builder that already run on purplelink.llc. Nothing is deployed or submitted yet: this PR is the build, for review.

Why it can pass review: ChatGPT cannot reliably check that a reference exists, and this app does, against Crossref and
Semantic Scholar, with retraction status from Crossref (which carries Retraction Watch data). It is not a thin wrapper
around anything ChatGPT does natively.

## What is where

| Piece | Path |
| --- | --- |
| Parsing, matching, retraction logic, lookups (no MCP import) | `backend/latextools/citation_check.py` |
| MCP surface: tools, schemas, annotations, rate-limit hook, result text | `backend/latextools/citation_server.py` |
| Modal app (separate from `app.py`) | `backend/citation_mcp_app.py` |
| Run it locally on 127.0.0.1 | `backend/scripts/citation_mcp_local.py` |
| Tests (mocked HTTP) | `backend/tests/test_citation_app.py` |
| Privacy policy section | `site/privacy/index.html`, `#citation-app` |

**Endpoint (after deploy):** `https://ben-ampel--purplelink-citation-mcp-web.modal.run/mcp` (streamable HTTP, stateless,
JSON responses). `/health` returns `{"ok": true}`. `/.well-known/openai-apps-challenge` serves the verification token once
`OPENAI_APPS_CHALLENGE` in `citation_mcp_app.py` is filled in.

**Why a separate Modal app, not a mount on `app.py`:** the main web function runs on the TeX Live image (several GB, slow
cold start) with 6 containers shared by every free tool. A chat client waits on a tool call, and a burst of chat traffic
would compete with the site's tools. The MCP SDK also needs its session-manager lifespan, which is awkward to mount inside
that FastAPI app. The new image is slim Python with `mcp==1.27.2`, `httpx==0.27.2`, `bibtexparser` pinned, and shares the
`latextools-rate` Dict (own bucket `mcp-citations`) and the `latextools` package. **Deploy command differs from the
site backend:** `cd backend && python3 -m modal deploy citation_mcp_app.py`. `scripts/deploy.sh --backend` does not deploy it.

The OpenAI domain-verification file must be served from the MCP host. The Modal host is not purplelink.llc, so the token
route lives in the app. If OpenAI insists on the purplelink.llc domain, add a Netlify rewrite from
`purplelink.llc/mcp/citations` to the Modal URL (not built: unverified without a deploy, and Netlify proxies time out
at about 26 s, close to the tools' 24 s budget).

## Tools

All three: `readOnlyHint: true`, `destructiveHint: false`, `idempotentHint: true`, `openWorldHint: true` (calls Crossref and
Semantic Scholar), a `title`, an `outputSchema`, and `_meta.securitySchemes = [{"type": "noauth"}]`.

| Tool | Input | Output (structuredContent) |
| --- | --- | --- |
| `check_references` | `references`: string, 1 to 200,000 chars; BibTeX or a plain-text list; first 100 entries checked | `summary`, `results[]` (status `found`/`needs_review`/`likely_hallucinated`/`not_found`/`lookup_failed`/`lookup_incomplete`, matched DOI and title, `mismatches` for year/authors/venue, `retraction_status`, notices), `notes` |
| `check_retractions` | `dois`: up to 100 strings, and/or `references` (extracts DOIs; up to 25 no-DOI references matched by title) | `summary`, `dois[]` (status `retracted`/`expression_of_concern`/`corrected`/`none`/`not_in_crossref`/`lookup_failed`, notice links), `references_without_doi`, `notes` |
| `doi_to_bibtex` | `dois`: 1 to 50 strings, bare or doi.org links | `entries[]`, joined `bibtex`, `notes` |

Every result's text ends with one line: `Full free tool: https://purplelink.llc/tools/<tool>/?utm_source=chatgpt-app&utm_medium=app&utm_campaign=citations`.
A ModernTex or Paper Review line is built but **off by default** (`CITATION_APP_PRODUCT_NOTES=1` turns it on): OpenAI's
guidelines prohibit upgrade prompts and advertising in apps and Anthropic rejects promotion in tool text. Leave it off for
the listing; decide after approval.

Behaviour worth knowing:

- Same lookup order as the site validator: Crossref (by DOI, then title search), Semantic Scholar if Crossref has no good
  match. Thresholds are the validator's: title similarity 0.85 is a match, below 0.50 is poor. For pasted lists, which have no
  title field, a found title also counts as matched when it appears whole in the reference text.
- A middling title match (0.50 to 0.85) is `needs_review`, but becomes `likely_hallucinated` when no cited author matches.
  Author check differs from the validator on purpose: it counts only cited surnames missing from the real author list, so
  "and others" or a shortened list is not a mismatch.
- A DOI that is not registered with Crossref and has no title match is `likely_hallucinated`.
- Budget: 3 concurrent Crossref calls (its polite pool), 1 for Semantic Scholar, 24 s for the whole call. Entries still
  waiting at the deadline come back as `lookup_incomplete`; the rest are returned.
- Rate limit: 600 tool calls per IP per day by default (`CITATION_MCP_DAILY_CALLS`). ChatGPT and Claude call from shared
  addresses, so this is an abuse guard, not a per-user quota. If it trips for everyone, raise it.
- No storage. Logs hold counts only (`check_references entries=3 found=2 flagged=1`); httpx's request logging is set to
  WARNING because its URLs carry reference text. Titles from Crossref and Semantic Scholar are untrusted text: control
  characters are stripped and length is capped.

## Requirements followed (read 2026-10-15)

OpenAI (ChatGPT apps; the docs now call them plugins in places):

- Submission guidelines, https://developers.openai.com/apps-sdk/app-submission-guidelines: explicit boolean `readOnlyHint`,
  `destructiveHint`, `openWorldHint`; read-only tools use true / false / true for open-ended public data; each tool needs a
  non-empty description matching its behavior and a specific verb name; each tool works alone and does not direct the model to
  another plugin; inputs related to the purpose, no chat history; responses carry only relevant data; published privacy policy
  (data categories, purposes, recipients, retention, user controls); support contact; no advertising, no upgrade prompts, no
  digital-goods commerce; no PHI, government IDs or credentials collected; no "MCP" or "Plugin" appended to the name; no
  pricing or promotions in descriptions; public anonymous read-only apps are allowed.
- Build an MCP server, https://developers.openai.com/apps-sdk/build/mcp-server: streamable HTTP, usually at `/mcp`; `name`,
  `title`, `description`, `inputSchema`, `outputSchema`, `annotations`; `structuredContent` plus `content`; a widget is not required.
- Authentication, https://developers.openai.com/apps-sdk/build/auth: no auth is allowed for anonymous read-only servers;
  declare `securitySchemes` per tool (`noauth`).
- Security and privacy, https://developers.openai.com/apps-sdk/guides/security-privacy: validate inputs server-side, redact or
  avoid raw prompt text in logs, assume prompt injection, use timeouts on outbound calls, least privilege.
- Plan tools, https://developers.openai.com/apps-sdk/plan/tools: action-oriented names, descriptions say when to use, limits
  in schemas, reads separate from writes.
- Submission steps, https://developers.openai.com/apps-sdk/deploy/submission: see "Submit to OpenAI" below.
- Not stated in the docs read: any cap on response size, CORS rules, whether stateless is required. The server is stateless and
  keeps results small (flagged entries only in the text, up to 60 lines).

Anthropic (Claude connectors directory):

- Submit a connector, https://claude.com/docs/connectors/building/submission, and review criteria,
  https://claude.com/docs/connectors/building/review-criteria, and authentication,
  https://claude.com/docs/connectors/building/authentication: remote server over HTTPS; `none` is a supported auth type for
  public data; every tool has a `title` and a `readOnlyHint` or `destructiveHint`; tool names 64 characters or fewer; narrow,
  accurate descriptions with no promotion of products and no instructions to call other tools; actionable error messages,
  reasonably sized responses; do not collect conversation data beyond what the tool needs; privacy policy URL, documentation
  URL, support contact, icon; a test account (none needed here); seven policy acknowledgments in the portal; the server must
  call first-party or legitimately proxied APIs (these are public APIs used within their terms). Claude's egress range is
  160.79.104.0/21 if anything ever needs allow-listing.
- The older support article "remote MCP server submission guide" returned 404; the claude.com pages above are current.

Tool descriptions in this server say what the tool does and when to use it, and mention no product. Output text points to the
free tool only.

## Test it before anything is deployed

1. Unit tests: `cd backend && python3 -m pytest -q tests/test_citation_app.py` (mocked HTTP, no network).
2. Local server: `cd backend && python3 scripts/citation_mcp_local.py` serves `http://127.0.0.1:8765/mcp` and calls the real
   Crossref and Semantic Scholar APIs. Inspect with `npx @modelcontextprotocol/inspector --cli http://127.0.0.1:8765/mcp --transport http --method tools/list`.
   Never use `modal serve` (it publishes a temporary public URL).

After Ben deploys:

3. **ChatGPT:** per the connect guide (https://developers.openai.com/apps-sdk/deploy/connect-chatgpt), open chatgpt.com/plugins, plus
   button, Add custom MCP server, name it, enter the endpoint URL with `/mcp`, choose no authentication, continue, Create. Check the
   discovered tools, then in a new chat try the example prompts below. After changes: deploy, open the connection, Refresh, start a
   new chat. (The page still describes this flow as plugins; "developer mode" is the older name, so the labels may differ.)
4. **Claude:** Customize > Connectors > add custom connector by URL (https://claude.com/docs/connectors/building/testing), paste the
   endpoint, confirm Connected and that all three tools list under Tool permissions, then in a chat turn it on from + > Connectors and
   call each tool.

## Submit to OpenAI (Ben)

Source: https://developers.openai.com/apps-sdk/deploy/submission (read 2026-10-15). The flow is now a plugin package ZIP.

1. Organization settings: complete individual or business verification (Purplelink LLC). Owner role, or Apps Management Write.
2. Deploy the Modal app (command above). Confirm `/health` and `/mcp`.
3. Build the plugin ZIP with an `mcp.json` that declares exactly one remote server, the endpoint URL, with empty headers. Follow the
   plugin package guide linked from the submission page; it was not fetched for this PR, so check it for the ZIP layout.
4. Domain verification: the portal shows a challenge token. Paste it into `OPENAI_APPS_CHALLENGE` in `backend/citation_mcp_app.py`,
   redeploy, check `https://ben-ampel--purplelink-citation-mcp-web.modal.run/.well-known/openai-apps-challenge` returns only the token.
5. Connect the server in the portal, authorize, wait for the tool scan, fix findings.
6. Fill the listing from the text below. Privacy policy URL `https://purplelink.llc/privacy/#citation-app`, support URL
   `https://purplelink.llc/about/` (or a page with ben@purplelink.llc; confirm), website `https://purplelink.llc/tools/bib-validator/`,
   terms of service URL (needs a page; check whether one exists), icons (square, 48 px or more), demo video URL.
7. Five positive test cases and three negative ones (below). Run each in ChatGPT first.
8. Save, choose Submit for review, make the policy attestations. Feedback arrives by email. After approval, press Publish plugin.

## Submit to Claude (Ben)

Source: https://claude.com/docs/connectors/building/submission. Portal: https://claude.ai/directory/manage, Submit new, MCP connector.
Any paid Claude plan can submit. Steps: Connection (paste the `https://` endpoint), Tools (all three should show as read-only with
titles), Listing (name up to 100 chars, one-liner up to 200, description up to 2,000, 1 to 5 categories, documentation URL, privacy
URL, support contact, icon, slug), Use cases (reads data, writes none), Company, Authentication (none), Data handling (public APIs
of third parties, used under their terms; no health data), Test and launch (confirm each tool was run; no test account needed),
Compliance (seven acknowledgments). Public documentation is required by the publish date: link the guide or this tool's page.
Escalations: mcp-review@anthropic.com.

## Listing text

- **Name** (30 chars max for OpenAI): `Reference Checker`. Do not append "MCP" or "Plugin". Stable identifier: `purplelink-reference-checker`.
- **Subtitle** (30): `Check that citations are real`
- **One-liner (Claude, 200):** Checks that academic references exist, match the published record, and have not been retracted, using
  Crossref and Semantic Scholar. Also turns DOIs into BibTeX.
- **Description (4,000 OpenAI / 2,000 Claude):**
  Paste a BibTeX file or a reference list and get back, for each entry, whether a matching published paper was found in Crossref or
  Semantic Scholar. Entries with no match, or only a weak title match, are marked likely hallucinated, so invented citations stand out.
  You also see mismatches in year, authors and venue, the matched DOI and title, and whether Crossref records the paper as retracted,
  corrected, or under an expression of concern, with a link to the notice. A second tool checks DOIs for retractions only. A third turns
  DOIs into BibTeX entries.
  Limits: up to 100 references or 50 to 100 DOIs per call. A match means a paper with that title exists, not that it supports the claim
  it is cited for. A clear retraction result is not a guarantee: very recent retractions may not be in Crossref yet. Books, theses and
  web pages are often absent from Crossref, so "not found" means check by hand. References you send go to Crossref and Semantic Scholar;
  Purplelink stores nothing. For users: researchers, students and editors who need to check a bibliography before submitting.
- **Category:** Education or Research (OpenAI: the closest of Productivity, Education, Research; Claude: Research and Education).
- **Example prompts (3, 128 chars max, no @mentions):**
  1. `Check these references and tell me which ones might not exist: [paste BibTeX]`
  2. `Has this paper been retracted? doi 10.1016/S0140-6736(97)11096-0`
  3. `Give me BibTeX for these DOIs: 10.1038/nature14539, 10.1126/science.1059487`
- **Positive test cases:** (1) a bib with one invented entry: `check_references`, invented entry flagged `likely_hallucinated` or
  `not_found`; (2) a plain list with a numbered style and DOIs: `check_references`, entries found; (3) the Wakefield 1998 DOI:
  `check_retractions`, status `retracted` with a notice link; (4) two DOIs, one fake: `doi_to_bibtex`, one entry plus a "No BibTeX for" note;
  (5) a bib containing a corrected paper: `check_references`, `corrected` flagged.
- **Negative test cases:** (1) "Write a literature review on diabetes": the app does not act; (2) "Summarize this PDF": no call; (3) "Is this
  claim true?": no call (the app checks references, not claims).

## Stop rule

Count visits to purplelink.llc with `utm_source=chatgpt-app` in the first 6 weeks after the listing goes live. Under 10 visits: stop
maintaining it (leave it published or unpublish; do not spend more time on it). The traffic source is `chatgpt-app` for both directories;
the same tag is on the links in every result. Log the listing date with `log_change.py` so the count has a start date.

## Follow-ups, not built

- A results-table widget (OpenAI UI component) would help for long lists; not required.
- Netlify rewrite to serve the endpoint from purplelink.llc (see above).
- Semantic Scholar throttles unauthenticated clients (HTTP 429 is common): an API key in a Modal secret would make the fallback reliable.
- DataCite lookup, so arXiv and Zenodo DOIs are not reported as "not in Crossref".
