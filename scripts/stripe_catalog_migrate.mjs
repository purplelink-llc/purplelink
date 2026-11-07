#!/usr/bin/env node
// Recreates the Stripe catalog in the NEW, directly controlled Stripe account. Idempotent: every Price is looked up by
// lookup_key first and only created when it is missing, so a re-run creates nothing.
//
//   node scripts/stripe_catalog_migrate.mjs                 test mode (new account's test key)
//   node scripts/stripe_catalog_migrate.mjs --live          live mode (new account's live key)
//   add --dry-run to list what would be created without creating it
//   add --tax-codes to set the Managed Payments tax code (netlify/lib/managed-payments.mjs) on each created product
//
// What it makes, in the new account:
//   1. One Price per STRIPE_PRICE_* env var that netlify/functions/checkout.mjs reads (paper-review family, kits,
//      Outbound Veil, Legroom, Lenses, Vitae Plus ...). The definition (amount, currency, one-time or recurring, product
//      name) is read from the OLD account's live Price, read only; lookup_key is `pl_<env name, lower case>`.
//   2. The `addon_<slug>_25` add-on Prices from netlify/lib/addons.mjs, from the app prices in netlify/lib/bundles.mjs.
// Nothing is deleted or changed, and nothing is created in the old account. At the end it prints the
// `<ENV NAME>_NEW=price_...` lines to set in Netlify (price ids are not secret).
//
// Keys, never printed:
//   new account  STRIPE_SECRET_KEY_NEW in the environment, else the keychain (account purplelink): service
//                stripe-test-secret in test mode, stripe-live-secret-new with --live. Store the new account's keys there.
//   old account  only to read Price definitions: STRIPE_SECRET_KEY in the environment, else keychain stripe-live-secret,
//                else `netlify env:get STRIPE_SECRET_KEY --context production` from a linked checkout. Used for GET only.
//   Price ids    each STRIPE_PRICE_* value comes from the environment, else `netlify env:get <NAME> --context production`.
//
// Inline-priced products (ModernTex, the Mac apps, seat packs) need no Price: checkout sends the amount with the session.
// Subscriptions and customers do not move between accounts; see docs/products/stripe-migration-2026-11.md.
import { execFileSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { ADDON_SLUGS } from "../netlify/lib/bundles.mjs";
import { addonCents, addonLabel, addonLookupKey } from "../netlify/lib/addons.mjs";
import { MP_TAX_CODES } from "../netlify/lib/managed-payments.mjs";

const here = dirname(fileURLToPath(import.meta.url));
const live = process.argv.includes("--live");
const dry = process.argv.includes("--dry-run");
const withTax = process.argv.includes("--tax-codes");

function sh(cmd, args) {
  try { return execFileSync(cmd, args, { encoding: "utf8", stdio: ["ignore", "pipe", "ignore"] }).trim(); } catch { return ""; }
}
const keychain = (service) => sh("security", ["find-generic-password", "-a", "purplelink", "-s", service, "-w"]);

const newKey = process.env.STRIPE_SECRET_KEY_NEW || keychain(live ? "stripe-live-secret-new" : "stripe-test-secret");
const oldKey = process.env.STRIPE_SECRET_KEY || keychain("stripe-live-secret") || sh("netlify", ["env:get", "STRIPE_SECRET_KEY", "--context", "production"]);

if (!(live ? /^(sk|rk)_live_/ : /^(sk|rk)_test_/).test(newKey)) {
  console.error(`No ${live ? "live" : "test"} key for the new Stripe account found (or it is the wrong mode). Nothing was sent.`);
  process.exit(2);
}
if (newKey === oldKey) {
  console.error("The new-account key is the same as the old account's key. Stop: this script must run against the new account.");
  process.exit(2);
}
const oldOk = /^(sk|rk)_live_/.test(oldKey);

async function api(key, method, path, form) {
  const r = await fetch(`https://api.stripe.com/v1${path}`, {
    method,
    headers: { Authorization: `Bearer ${key}`, ...(form ? { "content-type": "application/x-www-form-urlencoded" } : {}) },
    body: form ? new URLSearchParams(form).toString() : undefined,
  });
  const j = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(`Stripe ${r.status} ${j?.error?.message || ""}`.trim());
  return j;
}
const readOld = (path) => api(oldKey, "GET", path); // the only call ever made with the old key

/** Every STRIPE_PRICE_* name checkout.mjs reads through an envKey. */
function catalogEnvKeys() {
  const src = readFileSync(join(here, "../netlify/functions/checkout.mjs"), "utf8");
  return [...new Set([...src.matchAll(/envKey:\s*"(STRIPE_PRICE_[A-Z0-9_]+)"/g)].map((m) => m[1]))].sort();
}
function oldPriceId(name) {
  return (process.env[name] || sh("netlify", ["env:get", name, "--context", "production"])).trim();
}

async function ensurePrice({ lookup, describe, create }) {
  const found = await api(newKey, "GET", `/prices?lookup_keys[]=${encodeURIComponent(lookup)}&active=true&limit=1`);
  const have = found.data?.[0];
  if (have) { console.log(`exists  ${lookup} ${have.id}`); return have; }
  if (dry) { console.log(`would create ${lookup}: ${describe}`); return null; }
  const made = await create();
  console.log(`created ${lookup} ${made.id}: ${describe}`);
  return made;
}

let failed = 0;
const mapping = [];

console.log(`New account, ${live ? "LIVE" : "test"} mode${dry ? " (dry run)" : ""}\n`);

if (!oldOk) {
  console.error("No live key for the old account found, so env Price definitions cannot be read. Skipping step 1; add-ons only.");
}
for (const name of oldOk ? catalogEnvKeys() : []) {
  const lookup = `pl_${name.toLowerCase()}`;
  try {
    const id = oldPriceId(name);
    if (!id.startsWith("price_")) { console.log(`skipped ${name}: not set in production`); continue; }
    const p = await readOld(`/prices/${id}?expand[]=product`);
    const prod = p.product || {};
    const rec = p.recurring;
    const describe = `${prod.name || name} ${(p.unit_amount ?? 0) / 100} ${p.currency}${rec ? ` per ${rec.interval}` : ""}`;
    // Old products often carry no metadata.product; the env name (STRIPE_PRICE_OUTBOUND_VEIL) maps to the same key.
    const envKey = name.replace(/^STRIPE_PRICE_/, "").toLowerCase().replace(/_/g, "-");
    const productKey = prod.metadata?.product || (Object.hasOwn(MP_TAX_CODES, envKey) ? envKey : "");
    const price = await ensurePrice({
      lookup, describe,
      create: () => {
        const f = {
          currency: p.currency,
          unit_amount: String(p.unit_amount),
          lookup_key: lookup,
          "metadata[migrated_from_env]": name,
          "product_data[name]": prod.name || name,
          "product_data[metadata][migrated_from_env]": name,
        };
        if (productKey) f["product_data[metadata][product]"] = productKey;
        if (p.tax_behavior && p.tax_behavior !== "unspecified") f.tax_behavior = p.tax_behavior;
        if (rec) { f["recurring[interval]"] = rec.interval; f["recurring[interval_count]"] = String(rec.interval_count || 1); }
        if (withTax && MP_TAX_CODES[productKey]) f["product_data[tax_code]"] = MP_TAX_CODES[productKey];
        return api(newKey, "POST", "/prices", f);
      },
    });
    if (price) mapping.push(`${name}_NEW=${price.id}`);
    // Stripe rejects product_data[description] on a Price, so the description is set on the Product afterwards.
    if (price && !dry && prod.description && typeof price.product === "string") {
      const prodNow = await api(newKey, "GET", `/products/${price.product}`);
      if (!prodNow.description) await api(newKey, "POST", `/products/${price.product}`, { description: prod.description });
    }
    if (price && withTax && MP_TAX_CODES[productKey] && typeof price.product === "string") {
      const prodNow = await api(newKey, "GET", `/products/${price.product}`);
      if (prodNow.tax_code !== MP_TAX_CODES[productKey] && !dry) {
        await api(newKey, "POST", `/products/${price.product}`, { tax_code: MP_TAX_CODES[productKey] });
        console.log(`tax code ${MP_TAX_CODES[productKey]} set on ${price.product}`);
      }
    }
  } catch (e) {
    failed++;
    console.error(`FAILED ${name}: ${e.message}`);
  }
}

for (const slug of ADDON_SLUGS) {
  const lookup = addonLookupKey(slug);
  const cents = addonCents(slug);
  try {
    const have = await ensurePrice({
      lookup, describe: `${cents}`,
      create: () => api(newKey, "POST", "/prices", {
        currency: "usd",
        unit_amount: String(cents),
        lookup_key: lookup,
        "metadata[addon_slug]": slug,
        "product_data[name]": `${addonLabel(slug)}, 25% off`,
        "product_data[metadata][addon_slug]": slug,
        ...(withTax && MP_TAX_CODES[slug] ? { "product_data[tax_code]": MP_TAX_CODES[slug] } : {}),
      }),
    });
    if (have && (have.unit_amount !== cents || have.currency !== "usd" || have.type !== "one_time")) {
      failed++;
      console.error(`MISMATCH ${lookup}: expected ${cents} usd one_time`);
    }
  } catch (e) {
    failed++;
    console.error(`FAILED ${lookup}: ${e.message}`);
  }
}

if (mapping.length) {
  console.log("\nSet these in Netlify (production) when the new account goes live; they are read only while STRIPE_NEW_ACCOUNT is on:");
  for (const m of mapping) console.log(m);
}
process.exit(failed ? 1 : 0);
