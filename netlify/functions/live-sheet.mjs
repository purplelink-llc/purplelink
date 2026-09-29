/**
 * Netlify Function — live-data spreadsheets (/sheets/live/).
 *
 *   GET  ?session_id=cs_…                 -> { product, configured, config, feeds }
 *   POST { session_id, config }           -> { product, config, feeds }  (set up or change)
 *   GET  ?k=<feed key>&tab=<tab>          -> text/csv for IMPORTDATA / Excel From Web
 *
 * A subscriber pays through checkout.mjs (live-scholar, live-funding: yearly,
 * 7-day trial) and lands on /sheets/live/setup/ with the session id. Setup
 * checks the session with Stripe, stores what the feed should track (an ORCID
 * iD or OpenAlex author id; or funding keywords), and returns a private feed
 * key. The key goes in the sheet's IMPORTDATA formula; every refresh checks
 * the subscription is still active or trialing (re-asked of Stripe at most
 * every 12 hours) and serves data cached for 6 hours, so a sheet refreshing
 * hourly costs the public APIs four calls a day.
 *
 * Data: OpenAlex (CC0), grants.gov search2, NSF Award Search, NIH RePORTER —
 * all public, no keys. Nothing personal is stored: the subscription id, the
 * feed settings and the key. The key is a bearer token for public data only.
 *
 * Env: STRIPE_SECRET_KEY.
 */
import { randomBytes } from "node:crypto";
import { getStore } from "@netlify/blobs";

const STRIPE_API = "https://api.stripe.com/v1";
const STORE = "live-sheets";
const FEED_BASE = "https://purplelink.llc/.netlify/functions/live-sheet";
const CACHE_MS = 6 * 3600 * 1000;
const STATUS_MS = 12 * 3600 * 1000;
const LIVE_STATUSES = new Set(["active", "trialing", "past_due"]);
const UA = "Purplelink live sheets (ben@purplelink.llc)";

const TABS = {
  "live-scholar": [
    ["works", "Your works"],
    ["summary", "Summary and citations by year"],
    ["coauthors", "Coauthors"],
    ["venues", "Venues"],
  ],
  "live-funding": [
    ["opportunities", "Open and forecasted opportunities (grants.gov)"],
    ["nsf-awards", "Recent NSF awards on your topics"],
    ["nih-projects", "Recent NIH projects on your topics"],
  ],
};

// ------------------------------------------------------------------ helpers
function json(status, body) {
  return new Response(JSON.stringify(body), {
    status, headers: { "Content-Type": "application/json", "Cache-Control": "private, no-store" },
  });
}

function csvCell(v) {
  if (v === null || v === undefined) return "";
  let s = String(v).replace(/\r?\n/g, " ").trim();
  // A value a spreadsheet would read as a formula must stay text.
  if (/^[=+@]/.test(s)) s = " " + s;
  return /[",]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

function csv(rows) {
  return rows.map((r) => r.map(csvCell).join(",")).join("\n") + "\n";
}

function csvResponse(body) {
  return new Response(body, {
    status: 200,
    headers: { "Content-Type": "text/csv; charset=utf-8", "Cache-Control": "private, max-age=600" },
  });
}

async function getJSON(url, init = {}) {
  const resp = await fetch(url, {
    ...init,
    headers: { "User-Agent": UA, Accept: "application/json", ...(init.headers || {}) },
    signal: AbortSignal.timeout(8000),
  });
  if (!resp.ok) throw new Error(`${new URL(url).host} ${resp.status}`);
  return resp.json();
}

async function stripe(path) {
  const key = Netlify.env.get("STRIPE_SECRET_KEY");
  if (!key) throw new Error("STRIPE_SECRET_KEY not set");
  const resp = await fetch(`${STRIPE_API}${path}`, { headers: { Authorization: `Bearer ${key}` } });
  if (!resp.ok) return null;
  return resp.json();
}

async function stripePost(path, params) {
  const key = Netlify.env.get("STRIPE_SECRET_KEY");
  const resp = await fetch(`${STRIPE_API}${path}`, {
    method: "POST",
    headers: { Authorization: `Bearer ${key}`, "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams(params).toString(),
  });
  return resp.ok ? resp.json() : null;
}

function feedsFor(product, key) {
  return (TABS[product] || []).map(([tab, label]) => ({
    tab, label, url: `${FEED_BASE}?k=${key}&tab=${tab}`,
  }));
}

// ------------------------------------------------------------------ config
const ORCID_RE = /^(\d{4}-){3}\d{3}[\dX]$/;
const OPENALEX_RE = /^A\d{5,12}$/;

// ORCID's last character is an ISO 7064 MOD 11-2 check digit, so a typo is
// caught here instead of pointing the sheet at a stranger (OpenAlex even holds a
// record for the invalid 0000-0000-0000-0000).
function orcidChecksumOk(id) {
  const digits = id.replace(/-/g, "");
  let total = 0;
  for (const ch of digits.slice(0, 15)) total = (total + Number(ch)) * 2;
  const r = (12 - (total % 11)) % 11;
  return digits[15] === (r === 10 ? "X" : String(r));
}

function cleanConfig(product, raw) {
  raw = raw && typeof raw === "object" ? raw : {};
  if (product === "live-scholar") {
    let id = String(raw.author || "").trim()
      .replace(/^https?:\/\/(www\.)?(orcid\.org|openalex\.org)\//i, "").toUpperCase();
    if (ORCID_RE.test(id)) {
      if (!orcidChecksumOk(id)) return { error: "That ORCID iD has a typo: its last character doesn't match. Copy it from your ORCID record." };
      return { config: { author: id, kind: "orcid" } };
    }
    if (OPENALEX_RE.test(id)) return { config: { author: id, kind: "openalex" } };
    return { error: "Enter an ORCID iD (0000-0000-0000-0000) or an OpenAlex author id (A followed by digits)." };
  }
  if (product === "live-funding") {
    const list = Array.isArray(raw.keywords) ? raw.keywords : String(raw.keywords || "").split(/[\n,;]+/);
    const keywords = [...new Set(list.map((k) => String(k).replace(/[^\w\s\-&/.]/g, "").replace(/\s+/g, " ").trim().slice(0, 60))
      .filter((k) => k.length >= 3))].slice(0, 5);
    if (!keywords.length) return { error: "Enter one to five topics, for example: phishing, large language models." };
    const agencies = (Array.isArray(raw.agencies) ? raw.agencies : [])
      .filter((a) => /^[A-Z0-9-]{2,20}$/.test(a)).slice(0, 10);
    return { config: { keywords, agencies } };
  }
  return { error: "Unknown product." };
}

// ------------------------------------------------------------------ session / records
async function liveSession(sessionId) {
  if (!/^cs_[A-Za-z0-9_]{10,200}$/.test(sessionId || "")) return { error: json(400, { error: "bad_session_id" }) };
  const s = await stripe(`/checkout/sessions/${sessionId}?expand[]=subscription`);
  if (!s) return { error: json(403, { error: "session_not_found", detail: "That link is not valid for this store." }) };
  const product = s.metadata?.product || "";
  if (!TABS[product]) return { error: json(403, { error: "not_a_live_sheet", detail: "This order is not a live-data sheet." }) };
  const sub = s.subscription && typeof s.subscription === "object" ? s.subscription : null;
  if (s.status !== "complete" || !sub) return { error: json(403, { error: "not_complete", detail: "Checkout was not completed." }) };
  if (!LIVE_STATUSES.has(sub.status)) {
    return { error: json(403, { error: "inactive", detail: "This subscription is no longer active. Subscribe again from purplelink.llc/sheets/live/." }) };
  }
  return { product, sub };
}

// ------------------------------------------------------------------ OpenAlex (citation dashboard)
function openalexAuthorUrl(cfg) {
  return cfg.kind === "orcid"
    ? `https://api.openalex.org/authors/orcid:${cfg.author}`
    : `https://api.openalex.org/authors/${cfg.author}`;
}

async function openalexAuthor(cfg) {
  return getJSON(openalexAuthorUrl(cfg) + "?mailto=ben@purplelink.llc");
}

async function openalexWorks(authorId) {
  const short = authorId.replace("https://openalex.org/", "");
  const out = [];
  let cursor = "*";
  for (let page = 0; page < 5 && cursor; page++) {
    const url = `https://api.openalex.org/works?filter=authorships.author.id:${short}&per-page=200&cursor=${encodeURIComponent(cursor)}` +
      "&select=id,doi,display_name,publication_year,type,cited_by_count,counts_by_year,primary_location,authorships,open_access" +
      "&mailto=ben@purplelink.llc";
    const data = await getJSON(url);
    out.push(...(data.results || []));
    cursor = data.meta?.next_cursor || null;
  }
  return out;
}

async function scholarTab(tab, cfg) {
  const author = await openalexAuthor(cfg);
  const year = new Date().getUTCFullYear();
  if (tab === "summary") {
    const st = author.summary_stats || {};
    const rows = [
      ["Metric", "Value"],
      ["Name", author.display_name],
      ["OpenAlex id", author.id],
      ["ORCID", author.orcid || ""],
      ["Works", author.works_count],
      ["Citations", author.cited_by_count],
      ["h-index", st.h_index],
      ["i10-index", st.i10_index],
      ["2-year mean citedness", st["2yr_mean_citedness"] != null ? Number(st["2yr_mean_citedness"]).toFixed(2) : ""],
      ["Institution (last known)", (author.last_known_institutions || [])[0]?.display_name || ""],
      ["Updated", new Date().toISOString().slice(0, 10)],
      [],
      ["Year", "Works", "Citations"],
    ];
    for (const c of (author.counts_by_year || []).slice().sort((a, b) => b.year - a.year)) {
      rows.push([c.year, c.works_count, c.cited_by_count]);
    }
    return rows;
  }
  const works = await openalexWorks(author.id);
  if (tab === "works") {
    const rows = [["Year", "Title", "Venue", "Type", "Citations", `Citations ${year - 1}`, `Citations ${year}`,
      "Authors", "Your position", "Open access", "DOI", "OpenAlex"]];
    works.sort((a, b) => (b.publication_year || 0) - (a.publication_year || 0) || (b.cited_by_count || 0) - (a.cited_by_count || 0));
    for (const w of works) {
      const by = Object.fromEntries((w.counts_by_year || []).map((c) => [c.year, c.cited_by_count]));
      const auths = w.authorships || [];
      const pos = auths.findIndex((a) => a.author?.id === author.id);
      rows.push([w.publication_year, w.display_name, w.primary_location?.source?.display_name || "", w.type,
        w.cited_by_count || 0, by[year - 1] || 0, by[year] || 0, auths.length, pos >= 0 ? pos + 1 : "",
        w.open_access?.oa_status || "", w.doi || "", w.id]);
    }
    return rows;
  }
  if (tab === "coauthors") {
    const co = new Map();
    for (const w of works) {
      for (const a of w.authorships || []) {
        const id = a.author?.id;
        if (!id || id === author.id) continue;
        const e = co.get(id) || { name: a.author.display_name, n: 0, last: 0, cites: 0, inst: "" };
        e.n += 1;
        e.cites += w.cited_by_count || 0;
        if ((w.publication_year || 0) >= e.last) {
          e.last = w.publication_year || 0;
          e.inst = (a.institutions || [])[0]?.display_name || e.inst;
        }
        co.set(id, e);
      }
    }
    const rows = [["Coauthor", "Joint works", "Most recent year", "Citations of joint works", "Institution (on the latest joint work)"]];
    [...co.values()].sort((a, b) => b.n - a.n || b.last - a.last).slice(0, 300)
      .forEach((e) => rows.push([e.name, e.n, e.last || "", e.cites, e.inst]));
    return rows;
  }
  if (tab === "venues") {
    const v = new Map();
    for (const w of works) {
      const name = w.primary_location?.source?.display_name;
      if (!name) continue;
      const e = v.get(name) || { n: 0, cites: 0, last: 0 };
      e.n += 1; e.cites += w.cited_by_count || 0; e.last = Math.max(e.last, w.publication_year || 0);
      v.set(name, e);
    }
    const rows = [["Venue", "Works", "Citations", "Most recent year"]];
    [...v.entries()].sort((a, b) => b[1].n - a[1].n || b[1].cites - a[1].cites)
      .forEach(([name, e]) => rows.push([name, e.n, e.cites, e.last || ""]));
    return rows;
  }
  throw new Error("unknown tab");
}

// ------------------------------------------------------------------ funding feed
function mdyToIso(s) {
  const m = /^(\d{2})\/(\d{2})\/(\d{4})$/.exec(s || "");
  return m ? `${m[3]}-${m[1]}-${m[2]}` : "";
}

async function fundingTab(tab, cfg) {
  const today = new Date();
  const iso = (d) => d.toISOString().slice(0, 10);
  if (tab === "opportunities") {
    const hits = new Map();
    for (const kw of cfg.keywords) {
      // Multi-word topics are sent as exact phrases: unquoted, grants.gov matches any
      // word ("cybersecurity education" returned 510 hits, quoted it returns the 1 that fits).
      const body = { keyword: kw.includes(" ") ? `"${kw}"` : kw, oppStatuses: "forecasted|posted", rows: 100 };
      if (cfg.agencies?.length) body.agencies = cfg.agencies.join("|");
      const data = await getJSON("https://api.grants.gov/v1/api/search2", {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
      });
      for (const h of data.data?.oppHits || []) {
        const e = hits.get(h.id) || { ...h, matched: [] };
        e.matched.push(kw);
        hits.set(h.id, e);
      }
    }
    const rows = [["Close date", "Days left", "Title", "Agency", "Opportunity number", "Status", "Posted", "Matched topics", "Matched in", "Link"]];
    // Deadlines are US Eastern; a UTC date runs a day ahead of a US evening.
    const todayIso = today.toLocaleDateString("en-CA", { timeZone: "America/New_York" });
    // grants.gov searches the whole announcement, and many 2026 announcements
    // carry boilerplate about AI use and cybersecurity, so a broad topic also
    // hits unrelated calls. Say where it matched and put title matches first.
    const list = [...hits.values()].map((h) => {
      const t = (h.title || "").toLowerCase();
      return { ...h, close: mdyToIso(h.closeDate), inTitle: h.matched.some((k) => t.includes(k.toLowerCase())) };
    }).filter((h) => !h.close || h.close >= todayIso);   // grants.gov still lists some that already closed
    list.sort((a, b) => (b.inTitle - a.inTitle) || ((a.close || "9999") < (b.close || "9999") ? -1 : (a.close || "9999") > (b.close || "9999") ? 1 : 0));
    for (const h of list) {
      const days = h.close ? Math.round((Date.parse(h.close) - Date.parse(todayIso)) / 86400000) : "";
      rows.push([h.close, days, h.title, h.agency || h.agencyCode, h.number, h.oppStatus, mdyToIso(h.openDate),
        h.matched.join("; "), h.inTitle ? "title" : "full text", `https://www.grants.gov/search-results-detail/${h.id}`]);
    }
    return rows;
  }
  if (tab === "nsf-awards") {
    const since = new Date(today.getTime() - 548 * 86400000);
    const mdy = `${String(since.getUTCMonth() + 1).padStart(2, "0")}/${String(since.getUTCDate()).padStart(2, "0")}/${since.getUTCFullYear()}`;
    const seen = new Map();
    for (const kw of cfg.keywords) {
      const url = "https://api.nsf.gov/services/v1/awards.json?" + new URLSearchParams({
        keyword: `"${kw}"`, dateStart: mdy, rpp: "25",
        printFields: "id,title,piFirstName,piLastName,awardeeName,fundsObligatedAmt,estimatedTotalAmt,startDate,expDate,fundProgramName",
      });
      const data = await getJSON(url);
      for (const a of data.response?.award || []) {
        const e = seen.get(a.id) || { ...a, matched: [] };
        e.matched.push(kw);
        seen.set(a.id, e);
      }
    }
    const rows = [["Start date", "Title", "PI", "Institution", "Total amount", "Program", "Ends", "Matched topics", "Link"]];
    [...seen.values()].sort((a, b) => mdyToIso(b.startDate).localeCompare(mdyToIso(a.startDate))).forEach((a) =>
      rows.push([mdyToIso(a.startDate), a.title, `${a.piFirstName || ""} ${a.piLastName || ""}`.trim(), a.awardeeName,
        Number(a.estimatedTotalAmt || a.fundsObligatedAmt || 0), a.fundProgramName || "", mdyToIso(a.expDate),
        a.matched.join("; "), `https://www.nsf.gov/awardsearch/showAward?AWD_ID=${a.id}`]));
    return rows;
  }
  if (tab === "nih-projects") {
    const fy = today.getUTCMonth() >= 9 ? today.getUTCFullYear() + 1 : today.getUTCFullYear();
    // One request for all topics (RePORTER asks for at most one request a second).
    const data = await getJSON("https://api.reporter.nih.gov/v2/projects/search", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        criteria: { advanced_text_search: { operator: "advanced", search_field: "projecttitle,abstracttext",
            search_text: cfg.keywords.map((k) => `"${k}"`).join(" OR ") },
          fiscal_years: [fy, fy - 1], newly_added_projects_only: false },
        include_fields: ["ApplId", "ProjectNum", "ProjectTitle", "PrincipalInvestigators", "Organization",
          "AwardAmount", "FiscalYear", "AgencyIcAdmin", "ActivityCode", "ProjectStartDate"],
        offset: 0, limit: 200, sort_field: "project_start_date", sort_order: "desc",
      }),
    });
    const seen = new Map();
    for (const p of data.results || []) {
      const title = (p.project_title || "").toLowerCase();
      const hit = cfg.keywords.filter((k) => title.includes(k.toLowerCase()));
      seen.set(p.appl_id, { ...p, matched: hit.length ? hit : ["(in abstract)"] });
    }
    const rows = [["Fiscal year", "Title", "PI", "Organization", "Award amount", "Institute", "Activity", "Project number", "Matched topics", "Link"]];
    const inTitle = (p) => (p.matched[0] === "(in abstract)" ? 1 : 0);
    [...seen.values()].sort((a, b) => inTitle(a) - inTitle(b) || (b.fiscal_year || 0) - (a.fiscal_year || 0) || (b.award_amount || 0) - (a.award_amount || 0))
      .forEach((p) => rows.push([p.fiscal_year, p.project_title,
        (p.principal_investigators || []).map((x) => x.full_name).join("; "), p.organization?.org_name || "",
        p.award_amount || 0, p.agency_ic_admin?.abbreviation || "", p.activity_code || "", p.project_num || "",
        p.matched.join("; "), `https://reporter.nih.gov/project-details/${p.appl_id}`]));
    return rows;
  }
  throw new Error("unknown tab");
}

// ------------------------------------------------------------------ feed
async function serveFeed(key, tab) {
  if (!/^[A-Za-z0-9_-]{20,64}$/.test(key || "")) return csvResponse(csv([["This feed key is not valid. Copy the formula again from your setup page."]]));
  const store = getStore(STORE);
  const rec = await store.get(`key/${key}`, { type: "json" });
  if (!rec) return csvResponse(csv([["This feed key is not recognized. Copy the formula again from your setup page."]]));
  if (!(TABS[rec.product] || []).some(([t]) => t === tab)) {
    return csvResponse(csv([[`Unknown tab "${tab}". Available: ${(TABS[rec.product] || []).map(([t]) => t).join(", ")}`]]));
  }
  if (Date.now() - (rec.checkedAt || 0) > STATUS_MS) {
    const sub = await stripe(`/subscriptions/${rec.sub}`).catch(() => null);
    if (sub) {
      rec.status = sub.status;
      rec.checkedAt = Date.now();
      await store.setJSON(`key/${key}`, rec);
    }
  }
  if (!LIVE_STATUSES.has(rec.status)) {
    return csvResponse(csv([["Your subscription has ended, so this feed is paused. Renew at https://purplelink.llc/sheets/live/ and the data returns on the next refresh."]]));
  }
  const cacheKey = `cache/${key}/${tab}`;
  const cached = await store.getWithMetadata(cacheKey, { type: "text" }).catch(() => null);
  if (cached && Date.now() - (cached.metadata?.at || 0) < CACHE_MS) return csvResponse(cached.data);
  try {
    const rows = rec.product === "live-scholar" ? await scholarTab(tab, rec.config) : await fundingTab(tab, rec.config);
    const body = csv(rows);
    await store.set(cacheKey, body, { metadata: { at: Date.now() } });
    return csvResponse(body);
  } catch (err) {
    console.warn("live-sheet: fetch failed", rec.product, tab, String(err));
    if (cached?.data) return csvResponse(cached.data);  // stale beats empty
    return csvResponse(csv([["The data source did not answer just now. The sheet will try again on its next refresh."]]));
  }
}

// ------------------------------------------------------------------ handler
export default async function handler(request) {
  const url = new URL(request.url);
  if (request.method === "GET" && url.searchParams.get("k")) {
    return serveFeed(url.searchParams.get("k"), url.searchParams.get("tab") || "");
  }
  const store = getStore(STORE);

  if (request.method === "GET") {
    const { product, sub, error } = await liveSession(url.searchParams.get("session_id"));
    if (error) return error;
    const rec = await store.get(`sub/${sub.id}`, { type: "json" });
    return json(200, {
      product, status: sub.status, configured: !!rec,
      config: rec?.config || null, feeds: rec ? feedsFor(product, rec.key) : [],
    });
  }

  if (request.method === "POST") {
    let body;
    try { body = await request.json(); } catch (_) { return json(400, { error: "bad_json" }); }
    if (body?.action === "portal") {
      // Manage or cancel: Stripe's hosted customer portal. Allowed whatever the
      // subscription's state, so an ended trial can still update its card.
      const sid = body.session_id;
      if (!/^cs_[A-Za-z0-9_]{10,200}$/.test(sid || "")) return json(400, { error: "bad_session_id" });
      const s = await stripe(`/checkout/sessions/${sid}`);
      if (!s || !TABS[s.metadata?.product || ""] || !s.customer) return json(403, { error: "session_not_found" });
      const portal = await stripePost("/billing_portal/sessions", {
        customer: s.customer,
        return_url: `https://purplelink.llc/sheets/live/setup/?session_id=${sid}`,
      });
      if (!portal?.url) return json(502, { error: "portal_unavailable", detail: "Stripe could not open the billing page. Email ben@purplelink.llc and we will cancel it for you." });
      return json(200, { url: portal.url });
    }
    const { product, sub, error } = await liveSession(body?.session_id);
    if (error) return error;
    const { config, error: cfgErr } = cleanConfig(product, body?.config);
    if (cfgErr) return json(400, { error: "bad_config", detail: cfgErr });
    if (product === "live-scholar") {
      // Resolve the author now so a typo fails here, not silently in the sheet.
      try {
        const a = await openalexAuthor(config);
        config.name = String(a.display_name || "").slice(0, 120);
      } catch (_) {
        return json(400, { error: "author_not_found", detail: "OpenAlex has no author with that id. Check the ORCID iD, or find your OpenAlex id at openalex.org." });
      }
    }
    const existing = await store.get(`sub/${sub.id}`, { type: "json" });
    const key = existing?.key || randomBytes(24).toString("base64url");
    const now = Date.now();
    await store.setJSON(`sub/${sub.id}`, { key, product, config, created: existing?.created || now, updated: now });
    await store.setJSON(`key/${key}`, { sub: sub.id, product, config, status: sub.status, checkedAt: now });
    // New settings mean new data: drop cached tabs.
    for (const [tab] of TABS[product]) await store.delete(`cache/${key}/${tab}`).catch(() => {});
    return json(200, { product, config, feeds: feedsFor(product, key) });
  }

  return json(405, { error: "method_not_allowed" });
}
