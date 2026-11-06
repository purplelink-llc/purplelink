// Two Stripe accounts during the move off the Buy Me a Coffee-controlled account.
//
// The old account keeps every past buyer: their sessions, charges, subscriptions and refunds only exist there, so the old
// key (STRIPE_SECRET_KEY) stays set. The new, directly controlled account (the one Managed Payments can run on) is added
// beside it through three env vars, all unset today:
//
//   STRIPE_SECRET_KEY_NEW      sk_… of the new account
//   STRIPE_WEBHOOK_SECRET_NEW  whsec_… of the new account's webhook endpoint
//   STRIPE_NEW_ACCOUNT         on / 1 / true / all: new Checkout Sessions are created on the new account
//
// With STRIPE_SECRET_KEY_NEW unset every helper here returns exactly what the code did before: the old key alone.
// Reading an old session through a new key (or the reverse) is a 404 from Stripe, which is how lookups fall through.
//
// Netlify Prices are per account, so while the flag is on a product reads `<envKey>_NEW` (for example
// STRIPE_PRICE_LEGROOM_NEW) and never the old account's Price id.

import { AsyncLocalStorage } from "node:async_hooks";

export const OLD_KEY_ENV = "STRIPE_SECRET_KEY";
export const NEW_KEY_ENV = "STRIPE_SECRET_KEY_NEW";
export const OLD_WEBHOOK_ENV = "STRIPE_WEBHOOK_SECRET";
export const NEW_WEBHOOK_ENV = "STRIPE_WEBHOOK_SECRET_NEW";
export const FLAG_ENV = "STRIPE_NEW_ACCOUNT";

const ON = new Set(["on", "1", "true", "all", "yes"]);

function env(name) {
  return (globalThis.Netlify?.env?.get(name) || "").trim();
}

/** True when new Checkout Sessions go to the new account: the flag is on and the new key is present. */
export function newAccountActive() {
  return ON.has(env(FLAG_ENV).toLowerCase()) && Boolean(env(NEW_KEY_ENV));
}

/** The key that creates new Checkout Sessions. Unchanged (old key) unless the new account is active. */
export function checkoutSecretKey() {
  return newAccountActive() ? env(NEW_KEY_ENV) : env(OLD_KEY_ENV);
}

/** Name of the env var holding a product's Price id: the `_NEW` twin while the new account is active. */
export function priceEnvName(envKey) {
  return envKey && newAccountActive() ? `${envKey}_NEW` : envKey;
}

/** Every key that may know a given object, newest account first. Just the old key while no new key is set. */
export function lookupKeys() {
  const keys = [env(NEW_KEY_ENV), env(OLD_KEY_ENV)].filter(Boolean);
  return [...new Set(keys)];
}

/**
 * fetch() for a Stripe URL that tries each account's key until one answers ok. Drop-in for the per-function
 * `fetch(url, { headers: { Authorization: Bearer … } })`: the Authorization header is replaced per key. A 404 (the
 * object lives in the other account) or a key the account rejects falls through to the next key; the last response is
 * returned when none succeed, and a network error is thrown only when every attempt threw.
 */
export async function stripeFetchAny(url, init = {}) {
  const keys = lookupKeys();
  if (keys.length === 0) throw new Error("no Stripe key is set");
  let last = null;
  let lastErr = null;
  for (const key of keys) {
    try {
      const resp = await fetch(url, { ...init, headers: { ...(init.headers || {}), Authorization: `Bearer ${key}` } });
      if (resp.ok) return resp;
      last = resp;
      if (![401, 403, 404].includes(resp.status)) return resp;
    } catch (err) {
      lastErr = err;
    }
  }
  if (last) return last;
  throw lastErr;
}

/** Both signing secrets, old first (the live endpoint today). Empty strings are dropped. */
export function webhookSecrets() {
  return [
    { account: "legacy", secret: env(OLD_WEBHOOK_ENV) },
    { account: "new", secret: env(NEW_WEBHOOK_ENV) },
  ].filter((s) => s.secret);
}

// The webhook handler runs for one account at a time; its helpers read the key through this per-request store.
const requestAccount = new AsyncLocalStorage();

/** Run fn with the webhook's account recorded, so currentSecretKey() returns the matching key. */
export function runWithAccount(fn) {
  return requestAccount.run({ account: "legacy" }, fn);
}

/** Record which account's signing secret verified the event being handled. */
export function setRequestAccount(account) {
  const store = requestAccount.getStore();
  if (store) store.account = account;
}

/** The secret key for the account of the event being handled; the old key outside a webhook request. */
export function currentSecretKey() {
  const account = requestAccount.getStore()?.account;
  return account === "new" ? env(NEW_KEY_ENV) : env(OLD_KEY_ENV);
}
