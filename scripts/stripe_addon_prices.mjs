#!/usr/bin/env node
// Creates the one-time "25% off second app" Stripe Prices used by netlify/lib/addons.mjs. Idempotent: a Price is looked
// up by lookup_key `addon_<slug>_25` first and only created when it is missing, so a re-run creates nothing.
//
//   node scripts/stripe_addon_prices.mjs            test mode (keychain service stripe-test-secret, account purplelink)
//   node scripts/stripe_addon_prices.mjs --live     live mode (STRIPE_SECRET_KEY in the environment, else the
//                                                   keychain service stripe-live-secret, else `netlify env:get --context production`, run from a linked checkout)
//   add --dry-run to list what would be created without creating it
//
// The key is never printed. Each Price is USD, one-time, unit_amount = round(75% of the app's price), with
// metadata.addon_slug. It creates nothing else in Stripe (each Price carries its own inline product, named "<App>, 25% off").
import { execFileSync } from "node:child_process";
import { ADDON_SLUGS } from "../netlify/lib/bundles.mjs";
import { addonCents, addonLabel, addonLookupKey } from "../netlify/lib/addons.mjs";

const live = process.argv.includes("--live");
const dry = process.argv.includes("--dry-run");

function sh(cmd, args) {
  try { return execFileSync(cmd, args, { encoding: "utf8", stdio: ["ignore", "pipe", "ignore"] }).trim(); } catch { return ""; }
}
function findKey() {
  if (!live) return sh("security", ["find-generic-password", "-a", "purplelink", "-s", "stripe-test-secret", "-w"]);
  return process.env.STRIPE_SECRET_KEY
    || sh("security", ["find-generic-password", "-a", "purplelink", "-s", "stripe-live-secret", "-w"])
    || sh("netlify", ["env:get", "STRIPE_SECRET_KEY", "--context", "production"]);
}
const key = findKey();
const want = live ? /^(sk|rk)_live_/ : /^(sk|rk)_test_/;
if (!want.test(key)) {
  console.error(`No ${live ? "live" : "test"} Stripe key found (or it is the wrong mode). Nothing was sent.`);
  process.exit(2);
}

async function api(method, path, form) {
  const r = await fetch(`https://api.stripe.com/v1${path}`, {
    method,
    headers: { Authorization: `Bearer ${key}`, ...(form ? { "content-type": "application/x-www-form-urlencoded" } : {}) },
    body: form ? new URLSearchParams(form).toString() : undefined,
  });
  const j = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(`Stripe ${r.status} ${j?.error?.message || ""}`.trim());
  return j;
}

let failed = 0;
for (const slug of ADDON_SLUGS) {
  const lookup = addonLookupKey(slug);
  const cents = addonCents(slug);
  try {
    const found = await api("GET", `/prices?lookup_keys[]=${encodeURIComponent(lookup)}&active=true&limit=1`);
    const have = found.data?.[0];
    if (have) {
      const ok = have.unit_amount === cents && have.currency === "usd" && have.type === "one_time";
      console.log(`${ok ? "exists " : "MISMATCH"} ${lookup} ${have.id} ${have.unit_amount}${ok ? "" : ` (expected ${cents})`}`);
      if (!ok) failed++;
      continue;
    }
    if (dry) { console.log(`would create ${lookup} ${cents}`); continue; }
    const made = await api("POST", "/prices", {
      currency: "usd",
      unit_amount: String(cents),
      lookup_key: lookup,
      "metadata[addon_slug]": slug,
      "product_data[name]": `${addonLabel(slug)}, 25% off`,
      "product_data[metadata][addon_slug]": slug,
    });
    console.log(`created ${lookup} ${made.id} ${cents}`);
  } catch (e) {
    failed++;
    console.error(`FAILED ${lookup}: ${e.message}`);
  }
}
process.exit(failed ? 1 : 0);
