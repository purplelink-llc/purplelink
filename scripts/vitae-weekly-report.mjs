// Weekly Vitae report: downloads and updates, Vitae Plus subscriptions, and live endpoint checks.
// Prints Markdown. Run with the site's environment injected, so no key is ever typed or printed:
//
//   netlify dev:exec --context production node scripts/vitae-weekly-report.mjs
//
// Reads STRIPE_SECRET_KEY, VITAE_STATS_TOKEN and SALES_EXCLUDE_EMAILS (your own test purchases).
const SITE = "https://purplelink.llc";
const DAY = 86400;
const now = Math.floor(Date.now() / 1000);
const weekAgo = now - 7 * DAY;
const exclude = new Set((process.env.SALES_EXCLUDE_EMAILS || "").split(",").map((s) => s.trim().toLowerCase()).filter(Boolean));
const out = [];
const say = (s = "") => out.push(s);
const fmtDate = (t) => new Date(t * 1000).toISOString().slice(0, 10);

say(`# Vitae weekly report, ${fmtDate(now)}`);
say();

// --- Downloads and updates -------------------------------------------------------------
try {
  const r = await fetch(`${SITE}/.netlify/functions/vitae-download?stats=1`, {
    headers: { "X-Vitae-Stats": process.env.VITAE_STATS_TOKEN || "" },
  });
  const s = await r.json();
  const sumDays = (map, from) => Object.entries(map || {}).filter(([d]) => d >= from).reduce((a, [, n]) => a + n, 0);
  const from = fmtDate(weekAgo);
  const flat = (o) => Object.fromEntries(Object.entries(o || {}).filter(([, v]) => typeof v === "number"));
  const days = s.byDay || {};
  const updDays = s.updatesByDay || {};
  say("## Downloads");
  if (!r.ok) {
    say(`Stats unavailable (HTTP ${r.status}).`);
  } else {
    say(`- New downloads, last 7 days: **${sumDays(days, from)}**`);
    say(`- Update downloads (in-app updater), last 7 days: **${sumDays(updDays, from)}**`);
    const files = flat(s.downloads || {});
    if (Object.keys(files).length) say(`- All-time by file: ${Object.entries(files).map(([k, v]) => `${k} ${v}`).join(", ")}`);
    const updates = flat(s.updates || {});
    if (Object.keys(updates).length) say(`- All-time updates by file: ${Object.entries(updates).map(([k, v]) => `${k} ${v}`).join(", ")}`);
  }
} catch (e) {
  say("## Downloads");
  say(`Stats unavailable (${e.message}).`);
}
say();

// --- Vitae Plus -------------------------------------------------------------------------
const key = process.env.STRIPE_SECRET_KEY;
async function stripe(path) {
  const r = await fetch(`https://api.stripe.com/v1${path}`, { headers: { Authorization: `Bearer ${key}` } });
  if (!r.ok) throw new Error(`Stripe ${r.status}`);
  return r.json();
}
say("## Vitae Plus");
try {
  let subs = [];
  for (const product of ["vitae-plus-monthly", "vitae-plus-annual"]) {
    let page = null;
    do {
      const q = encodeURIComponent(`metadata['product']:'${product}'`);
      const res = await stripe(`/subscriptions/search?query=${q}&limit=100&expand[]=data.customer${page ? `&page=${page}` : ""}`);
      subs = subs.concat(res.data || []);
      page = res.has_more ? res.next_page : null;
    } while (page);
  }
  const mine = (s) => exclude.has(String(s.customer?.email || "").toLowerCase());
  const real = subs.filter((s) => !mine(s));
  const by = (st) => real.filter((s) => s.status === st);
  const monthly = (s) => s.items?.data?.[0]?.price?.recurring?.interval === "month";
  const paying = by("active");
  const mrr = paying.reduce((a, s) => a + (monthly(s) ? 3 : 2), 0);
  say(`- Paying: **${paying.length}** (${paying.filter(monthly).length} monthly, ${paying.filter((s) => !monthly(s)).length} annual), about **$${mrr}/month**`);
  say(`- In trial: **${by("trialing").length}**`);
  say(`- Past due: ${by("past_due").length}`);
  say(`- New subscriptions in the last 7 days: **${real.filter((s) => s.created >= weekAgo).length}**`);
  const canceled = real.filter((s) => s.canceled_at && s.canceled_at >= weekAgo);
  say(`- Cancelled in the last 7 days: ${canceled.length}${canceled.length ? ` (${canceled.filter((s) => s.trial_end && s.canceled_at <= s.trial_end).length} during the trial)` : ""}`);
  const endingTrials = by("trialing").filter((s) => s.trial_end && s.trial_end <= now + 7 * DAY);
  if (endingTrials.length) say(`- Trials converting in the next 7 days: ${endingTrials.length}`);
  if (subs.length !== real.length) say(`- (${subs.length - real.length} of your own test subscriptions left out)`);
} catch (e) {
  say(`Stripe unavailable (${e.message}).`);
}
say();

// --- Live checks ------------------------------------------------------------------------
say("## Live checks");
const checks = [
  ["Download button", `${SITE}/vitae/download`, (r) => r.ok && (r.headers.get("content-type") || "").includes("diskimage")],
  ["Update feed", `${SITE}/.netlify/functions/vitae-download?feed=1`, async (r) => r.ok && (await r.text()).includes("sparkle:edSignature")],
  ["License service", `${SITE}/.netlify/functions/vitae-license?refresh=0000000000000000`, async (r) => r.status === 404],
  ["Rate list", `${SITE}/vitae/venue_rates.json`, (r) => r.ok],
  ["Plus page", `${SITE}/vitae/plus/`, (r) => r.ok],
];
let problems = 0;
for (const [name, url, ok] of checks) {
  try {
    const r = await fetch(url, { method: name === "Download button" ? "HEAD" : "GET", redirect: "follow" });
    const good = await ok(r);
    if (!good) problems++;
    say(`- ${good ? "OK" : "PROBLEM"}: ${name} (HTTP ${r.status})`);
  } catch (e) {
    problems++;
    say(`- PROBLEM: ${name} (${e.message})`);
  }
}
say();
say(problems ? `**${problems} problem(s) need a look.**` : "All live checks passed.");
console.log(out.join("\n"));
