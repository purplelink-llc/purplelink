#!/usr/bin/env node
// Makes one single-use Stripe promotion code worth one free Paper Review, for a lab that replied to outreach.
//
//   node scripts/paper_review_promo_code.mjs --for capps              test mode (keychain stripe-test-secret)
//   node scripts/paper_review_promo_code.mjs --for capps --live       live mode, run from a Netlify-linked checkout
//
// Live mode follows checkout (netlify/lib/stripe-account.mjs): while STRIPE_NEW_ACCOUNT is on, the code is made on
// the new account (STRIPE_SECRET_KEY_NEW, else keychain stripe-live-secret-new, else Netlify) against the `_NEW`
// Price ids; otherwise on the old account (STRIPE_SECRET_KEY, keychain stripe-live-secret, Netlify). A code made
// on the wrong account would be rejected at checkout, so this must match where sessions are created.
//   --days N      days until the code expires (default 30)
//   --dry-run     check the key, prices and coupon, create nothing
//   --list        list the codes made by this script and whether each was used
//
// The code is 100% off one Standard, Journal or Deep review (not lab packs or plans), redeemable once, and the
// buyer types it in the promotion-code box on Stripe Checkout (checkout.mjs sets allow_promotion_codes). A $0
// session completes as "no_payment_required" and stripe-webhook.mjs delivers it like a paid order.
//
// All codes hang off one coupon, LAB_FREE_REVIEW, created on first use. A coupon's product list cannot be changed
// later, so if the Paper Review prices move to new products, the script stops and says so. The key is never printed.
import { execFileSync } from "node:child_process";
import { randomInt } from "node:crypto";

const argv = process.argv.slice(2);
const flag = (name) => argv.includes(name);
function opt(name) {
  const i = argv.indexOf(name);
  return i >= 0 && i + 1 < argv.length ? argv[i + 1] : "";
}
const live = flag("--live");
const dry = flag("--dry-run");
const list = flag("--list");
const forLabel = opt("--for").trim();
const days = Number(opt("--days") || 30);

const COUPON_ID = "LAB_FREE_REVIEW";
const PURPOSE = "lab-outreach-free-review";
const PRICE_ENV = [
  "STRIPE_PRICE_PAPER_REVIEW_STANDARD_V2",
  "STRIPE_PRICE_PAPER_REVIEW_JOURNAL_V2",
  "STRIPE_PRICE_PAPER_REVIEW_DEEP_V2",
];

if (!list && !forLabel) {
  console.error("Say who the code is for: --for <surname or label>. Nothing was sent.");
  process.exit(2);
}
if (!Number.isInteger(days) || days < 1 || days > 365) {
  console.error("--days must be a whole number from 1 to 365. Nothing was sent.");
  process.exit(2);
}

function sh(cmd, args) {
  try { return execFileSync(cmd, args, { encoding: "utf8", stdio: ["ignore", "pipe", "ignore"] }).trim(); } catch { return ""; }
}
const netlifyEnv = (name) => sh("netlify", ["env:get", name, "--context", "production"]);
const keychain = (service) => sh("security", ["find-generic-password", "-a", "purplelink", "-s", service, "-w"]);
// `netlify env:get` prints a sentence, not an error, when a variable is unset; accept only a real id.
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
// Price ids come from the environment; in live mode a missing one is read from Netlify production.
function priceId(base) {
  const name = newAccount ? `${base}_NEW` : base;
  return { name, id: real((process.env[name] || (live ? netlifyEnv(name) : "")).trim(), /^price_/) };
}

const key = findKey();
const mode = live ? (newAccount ? "live, new account" : "live, old account") : "test";
const want = live ? /^(sk|rk)_live_/ : /^(sk|rk)_test_/;
if (!want.test(key)) {
  console.error(`No ${live ? `live ${newAccount ? "new-account" : "old-account"}` : "test"} Stripe key found (or it is the wrong mode). Nothing was sent.`);
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

// Stripe allows only letters and digits in a promotion code. Skip 0/O and 1/I/L so it reads back cleanly.
const ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789";
function makeCode(label) {
  const stem = label.normalize("NFKD").replace(/[^A-Za-z]/g, "").toUpperCase().slice(0, 10) || "LAB";
  let tail = "";
  for (let i = 0; i < 4; i++) tail += ALPHABET[randomInt(ALPHABET.length)];
  return `REVIEW${stem}${tail}`;
}
const day = (unix) => new Date(unix * 1000).toISOString().slice(0, 10);

async function listCodes() {
  const out = [];
  let after = "";
  for (;;) {
    const page = await api("GET", `/promotion_codes?limit=100${after ? `&starting_after=${after}` : ""}`);
    for (const p of page.data || []) {
      const coupon = p.coupon?.id || p.promotion?.coupon?.id || p.promotion?.coupon || p.coupon;
      if (coupon === COUPON_ID || p.metadata?.purpose === PURPOSE) out.push(p);
    }
    if (!page.has_more || !page.data?.length) break;
    after = page.data[page.data.length - 1].id;
  }
  return out;
}

async function main() {
  if (list) {
    const codes = await listCodes();
    if (!codes.length) { console.log("No lab review codes yet."); return; }
    for (const p of codes) {
      const state = p.times_redeemed > 0 ? "used" : !p.active ? "inactive" : p.expires_at && p.expires_at < Date.now() / 1000 ? "expired" : "open";
      console.log(`${p.code}  ${state.padEnd(8)}  for ${p.metadata?.for || "?"}  made ${day(p.created)}${p.expires_at ? `  expires ${day(p.expires_at)}` : ""}`);
    }
    return;
  }

  // 1. The three single-review products, from their live (or test) prices.
  const products = [];
  for (const base of PRICE_ENV) {
    const { name, id } = priceId(base);
    if (!id) throw new Error(`${name} is not set${live ? " in Netlify production" : " (export it with a test-mode price ID)"}.`);
    const price = await api("GET", `/prices/${encodeURIComponent(id)}`);
    const product = typeof price.product === "string" ? price.product : price.product?.id;
    if (!price.active || !product) throw new Error(`${name} (${id}) is inactive or has no product.`);
    products.push(product);
  }
  const wanted = [...new Set(products)].sort();

  // 2. The shared coupon: reuse it, or create it.
  let coupon = null;
  try {
    coupon = await api("GET", `/coupons/${COUPON_ID}?expand[]=applies_to`);
  } catch (e) {
    if (e.status !== 404) throw e;
  }
  if (coupon) {
    const have = [...(coupon.applies_to?.products || [])].sort();
    const same = have.length === wanted.length && have.every((p, i) => p === wanted[i]);
    if (!coupon.valid || coupon.percent_off !== 100 || !same) {
      throw new Error(`Coupon ${COUPON_ID} no longer matches the Paper Review products (valid ${coupon.valid}, ` +
        `products ${have.join(",") || "none"}, want ${wanted.join(",")}). Delete it in the Stripe dashboard and run again.`);
    }
  } else if (dry) {
    console.log(`would create coupon ${COUPON_ID}: 100% off once, products ${wanted.join(",")}`);
  } else {
    const form = {
      id: COUPON_ID,
      name: "Free Paper Review (lab outreach)",
      percent_off: "100",
      duration: "once",
      "metadata[purpose]": PURPOSE,
    };
    wanted.forEach((p, i) => { form[`applies_to[products][${i}]`] = p; });
    coupon = await api("POST", "/coupons", form);
    console.log(`created coupon ${COUPON_ID}`);
  }

  // 3. The single-use code.
  const expires = Math.floor(Date.now() / 1000) + days * 86400;
  const code = makeCode(forLabel);
  if (dry) {
    console.log(`would create code like ${code} for ${forLabel}, one use, expires ${day(expires)} (${mode})`);
    return;
  }
  const base = {
    code,
    max_redemptions: "1",
    expires_at: String(expires),
    "metadata[for]": forLabel.slice(0, 200),
    "metadata[purpose]": PURPOSE,
  };
  let made;
  try {
    // API 2025-09-30 and later name the coupon under promotion[...]; older versions take coupon=.
    made = await api("POST", "/promotion_codes", { ...base, "promotion[type]": "coupon", "promotion[coupon]": COUPON_ID });
  } catch (e) {
    if (e.status !== 400 || !/promotion/.test(e.param + e.message)) throw e;
    made = await api("POST", "/promotion_codes", { ...base, coupon: COUPON_ID });
  }
  console.log(`${made.code}  one free Paper Review for ${forLabel}, one use, expires ${day(made.expires_at)} (${mode})`);
}

main().catch((e) => {
  console.error(`FAILED: ${e.message}`);
  process.exit(1);
});
