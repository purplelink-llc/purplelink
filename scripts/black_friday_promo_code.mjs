#!/usr/bin/env node
// Black Friday 2026: promotion code BLACKFRIDAY26, 25% off any single Mac app, through Monday 2026-11-30
// (it stops at 03:00 ET on 12-01, so a buyer on the West Coast still has the whole Monday evening).
//
//   node scripts/black_friday_promo_code.mjs --dry-run           test mode, create nothing
//   node scripts/black_friday_promo_code.mjs                     test mode (keychain stripe-test-secret)
//   node scripts/black_friday_promo_code.mjs --live --dry-run    live mode, check only
//   node scripts/black_friday_promo_code.mjs --live              live mode, run from a Netlify-linked checkout
//
// Live mode follows checkout (netlify/lib/stripe-account.mjs): while STRIPE_NEW_ACCOUNT is on, everything is made on
// the new account (STRIPE_SECRET_KEY_NEW, keychain stripe-live-secret-new, Netlify) with the `_NEW` Price ids.
//
// What it makes, each step skipped when it already exists and matches:
//   1. One product per inline-priced app (netlify/lib/app-products.mjs: ModernTex, Keyfeel, Tapefolio, Lenscrib,
//      Née, Panely, Summonly), tax code txcd_10202000, and one Price on it with lookup_key `app_<slug>` at the app's
//      catalog amount. Checkout then names that product, so the coupon can apply to it.
//   2. Coupon BLACKFRIDAY26_25: 25% off once, applies_to those products plus the env-Price apps' products (Outbound
//      Veil, Legroom, Lenses). Bundles, the Suite, seat packs and every non-app product are left out, so the code is
//      refused there. A coupon's product list cannot change later; a mismatch stops the script.
//   3. Promotion code BLACKFRIDAY26 on that coupon, expiring with it.
// The key is never printed.
import { execFileSync } from "node:child_process";
import { APP_PRODUCT_SLUGS, appLookupKey } from "../netlify/lib/app-products.mjs";

const argv = process.argv.slice(2);
const live = argv.includes("--live");
const dry = argv.includes("--dry-run");

const CODE = "BLACKFRIDAY26";
const COUPON_ID = "BLACKFRIDAY26_25";
const PERCENT = 25;
const PURPOSE = "black-friday-2026";
const ENDS = Math.floor(Date.parse("2026-12-01T03:00:00-05:00") / 1000);
const TAX_CODE = "txcd_10202000";
// Catalog amounts and names (netlify/functions/checkout.mjs PRODUCT_CATALOG); checked against the catalog below.
const APPS = {
  moderntex: ["ModernTex for macOS", 1999], keyfeel: ["Keyfeel for macOS", 999], tapefolio: ["Tapefolio for macOS", 2999],
  lenscrib: ["Lenscrib for macOS", 1999], nee: ["Née for macOS", 1499], panely: ["Panely for macOS", 999], summonly: ["Summonly for macOS", 999],
};
const ENV_PRICE_APPS = ["STRIPE_PRICE_OUTBOUND_VEIL", "STRIPE_PRICE_LEGROOM", "STRIPE_PRICE_LENSES"];

function sh(cmd, args) {
  try { return execFileSync(cmd, args, { encoding: "utf8", stdio: ["ignore", "pipe", "ignore"] }).trim(); } catch { return ""; }
}
const netlifyEnv = (name) => sh("netlify", ["env:get", name, "--context", "production"]);
const keychain = (service) => sh("security", ["find-generic-password", "-a", "purplelink", "-s", service, "-w"]);
const real = (value, shape) => (shape.test(value) ? value : "");
const FLAG_ON = new Set(["on", "1", "true", "all", "yes"]);
const newAccount = live && FLAG_ON.has((process.env.STRIPE_NEW_ACCOUNT || netlifyEnv("STRIPE_NEW_ACCOUNT")).trim().toLowerCase());
const KEY_SHAPE = /^(sk|rk)_(live|test)_/;
function findKey() {
  if (!live) return keychain("stripe-test-secret");
  if (newAccount) {
    return real(process.env.STRIPE_SECRET_KEY_NEW || "", KEY_SHAPE)
      || real(keychain("stripe-live-secret-new"), KEY_SHAPE)
      || real(netlifyEnv("STRIPE_SECRET_KEY_NEW"), KEY_SHAPE);
  }
  return real(process.env.STRIPE_SECRET_KEY || "", KEY_SHAPE)
    || real(keychain("stripe-live-secret"), KEY_SHAPE)
    || real(netlifyEnv("STRIPE_SECRET_KEY"), KEY_SHAPE);
}
function priceId(base) {
  const name = newAccount ? `${base}_NEW` : base;
  return { name, id: real((process.env[name] || (live ? netlifyEnv(name) : "")).trim(), /^price_/) };
}

const key = findKey();
const mode = live ? (newAccount ? "live, new account" : "live, old account") : "test";
if (!(live ? /^(sk|rk)_live_/ : /^(sk|rk)_test_/).test(key)) {
  console.error(`No ${live ? "live" : "test"} Stripe key found for ${mode}. Nothing was sent.`);
  process.exit(2);
}

async function api(method, path, form) {
  const r = await fetch(`https://api.stripe.com/v1${path}`, {
    method,
    headers: { Authorization: `Bearer ${key}`, ...(form ? { "content-type": "application/x-www-form-urlencoded" } : {}) },
    body: form ? new URLSearchParams(form).toString() : undefined,
  });
  const j = await r.json().catch(() => ({}));
  if (!r.ok) {
    const err = new Error(`Stripe ${r.status} ${j?.error?.message || ""}`.trim());
    err.status = r.status;
    err.param = j?.error?.param || "";
    throw err;
  }
  return j;
}
const productOf = (price) => (typeof price.product === "string" ? price.product : price.product?.id);

async function main() {
  console.log(`mode: ${mode}${dry ? " (dry run)" : ""}`);
  if (Date.now() / 1000 >= ENDS) throw new Error("The Black Friday window has ended; nothing to make.");

  // The names and amounts here must match the checkout catalog, or checkout would refuse the fixed products.
  globalThis.Netlify ??= { env: { get: () => "" } };
  const { PRODUCT_CATALOG } = await import("../netlify/functions/checkout.mjs");
  for (const slug of APP_PRODUCT_SLUGS) {
    const e = PRODUCT_CATALOG[slug];
    if (!APPS[slug] || !e || e.amount !== APPS[slug][1] || e.name !== APPS[slug][0]) {
      throw new Error(`${slug}: script says ${JSON.stringify(APPS[slug])}, catalog says ${e?.name} ${e?.amount}. Fix the script.`);
    }
  }

  // 1. Fixed products and their lookup Prices.
  const q = new URLSearchParams();
  for (const slug of APP_PRODUCT_SLUGS) q.append("lookup_keys[]", appLookupKey(slug));
  q.set("limit", "20");
  const existing = {};
  for (const p of (await api("GET", `/prices?${q}`)).data || []) existing[p.lookup_key] = p;
  const products = [];
  for (const slug of APP_PRODUCT_SLUGS) {
    const [name, cents] = APPS[slug];
    const have = existing[appLookupKey(slug)];
    if (have) {
      if (!have.active || have.unit_amount !== cents || have.currency !== "usd" || have.type !== "one_time") {
        throw new Error(`Price ${have.id} (${appLookupKey(slug)}) does not match ${cents} USD one-time. Fix it in Stripe first.`);
      }
      products.push(productOf(have));
      console.log(`${slug}: product ${productOf(have)} (exists)`);
      continue;
    }
    if (dry) { console.log(`${slug}: would create product "${name}" (${TAX_CODE}) and Price ${appLookupKey(slug)} at ${cents}`); continue; }
    const product = await api("POST", "/products", {
      name, tax_code: TAX_CODE, "metadata[app_slug]": slug, "metadata[purpose]": "fixed-app-product",
    });
    const price = await api("POST", "/prices", {
      product: product.id, currency: "usd", unit_amount: String(cents), lookup_key: appLookupKey(slug),
      "metadata[app_slug]": slug,
    });
    products.push(product.id);
    console.log(`${slug}: created product ${product.id}, price ${price.id}`);
  }

  // Apps that already sell through an env Price keep that Price's product.
  for (const base of ENV_PRICE_APPS) {
    const { name, id } = priceId(base);
    if (!id) {
      if (!live) { console.log(`${name}: not set in test mode, left out of the test coupon`); continue; }
      throw new Error(`${name} is not set in Netlify production.`);
    }
    const price = await api("GET", `/prices/${encodeURIComponent(id)}`);
    if (!price.active || !productOf(price)) throw new Error(`${name} (${id}) is inactive or has no product.`);
    products.push(productOf(price));
    console.log(`${name}: product ${productOf(price)}`);
  }
  const wanted = [...new Set(products)].sort();
  // A coupon with no product list applies to everything (bundles, Paper Review), so never make one.
  const expected = APP_PRODUCT_SLUGS.length + (live ? ENV_PRICE_APPS.length : 0);
  if (!dry && wanted.length !== expected) throw new Error(`Found ${wanted.length} app products, expected ${expected}. Nothing more was made.`);

  // 2. The coupon.
  let coupon = null;
  try { coupon = await api("GET", `/coupons/${COUPON_ID}?expand[]=applies_to`); } catch (e) { if (e.status !== 404) throw e; }
  if (coupon) {
    const have = [...(coupon.applies_to?.products || [])].sort();
    const same = have.length === wanted.length && have.every((p, i) => p === wanted[i]);
    if (!coupon.valid || coupon.percent_off !== PERCENT || !same) {
      throw new Error(`Coupon ${COUPON_ID} exists but does not match (valid ${coupon.valid}, ${coupon.percent_off}%, ` +
        `products ${have.join(",") || "none"}, want ${wanted.join(",")}). Delete it in Stripe and run again.`);
    }
    console.log(`coupon ${COUPON_ID}: exists and matches`);
  } else if (dry) {
    console.log(`would create coupon ${COUPON_ID}: ${PERCENT}% off once, redeem_by ${new Date(ENDS * 1000).toISOString()}, ${wanted.length} products`);
  } else {
    const form = {
      id: COUPON_ID, name: "Black Friday, 25% off", percent_off: String(PERCENT), duration: "once",
      redeem_by: String(ENDS), "metadata[purpose]": PURPOSE,
    };
    wanted.forEach((p, i) => { form[`applies_to[products][${i}]`] = p; });
    coupon = await api("POST", "/coupons", form);
    console.log(`created coupon ${COUPON_ID}`);
  }

  // 3. The promotion code.
  const found = (await api("GET", `/promotion_codes?code=${CODE}&limit=10`)).data || [];
  const couponOf = (p) => p.coupon?.id || p.promotion?.coupon?.id || p.promotion?.coupon || p.coupon;
  let active = found.find((p) => p.active);
  if (active && couponOf(active) !== COUPON_ID) {
    // The 20% site-wide code made on 2026-11-09 (coupon blackfriday26). Swap only once checkout names the fixed app
    // products on the live site, or ModernTex buyers would see the code refused in between.
    if (!argv.includes("--replace-old")) {
      throw new Error(`An active ${CODE} code (${active.id}) is on coupon ${couponOf(active)}, not ${COUPON_ID}. ` +
        "Run again with --replace-old once the checkout change is live.");
    }
    if (dry) { console.log(`would deactivate ${active.id} (coupon ${couponOf(active)})`); active = null; }
    else {
      await api("POST", `/promotion_codes/${active.id}`, { active: "false" });
      console.log(`deactivated old ${CODE} code ${active.id} (coupon ${couponOf(active)}); reactivate it in Stripe to undo`);
      active = null;
    }
  }
  if (active) {
    console.log(`promotion code ${CODE}: exists (${active.id}), expires ${new Date((active.expires_at || 0) * 1000).toISOString()}`);
    return;
  }
  if (dry) { console.log(`would create promotion code ${CODE}, expires ${new Date(ENDS * 1000).toISOString()}`); return; }
  const base = { code: CODE, expires_at: String(ENDS), "metadata[purpose]": PURPOSE };
  let made;
  try {
    made = await api("POST", "/promotion_codes", { ...base, "promotion[type]": "coupon", "promotion[coupon]": COUPON_ID });
  } catch (e) {
    if (e.status !== 400 || !/promotion/.test(e.param + e.message)) throw e;
    made = await api("POST", "/promotion_codes", { ...base, coupon: COUPON_ID });
  }
  console.log(`created promotion code ${made.code} (${made.id}), expires ${new Date(made.expires_at * 1000).toISOString()}`);
}

main().catch((e) => { console.error(e.message); process.exit(1); });
