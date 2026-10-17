/**
 * Adds a confirmed Daily Digest subscriber. Called by confirm-signup.mjs once the address has clicked the
 * link in its confirmation email (double opt-in). Paid subscriptions created by Stripe checkout do not come
 * through here: payment is their consent, and stripe-webhook.mjs writes those records itself.
 *
 * Referral: every subscriber gets a stable referral code (HMAC of their email, namespaced separately from the
 * unsubscribe token, so sharing one can never derive the other). If `ref` matches a known code, a credit is
 * recorded in "referral-credits", keyed `${refCode}:${referredEmail}`: one event per referred email rather
 * than a counter on the referrer's record, because @netlify/blobs has no compare-and-swap write. It is a plain
 * recommendation mechanic; no rewards are promised.
 */
import { getStore } from "@netlify/blobs"
import { createHmac } from "node:crypto"

export function referralCode(email, secret) {
  return createHmac("sha256", secret).update(`ref:${email}`).digest("hex").slice(0, 10)
}

/** Idempotent. Returns the person's referral code. */
export async function addDigestSubscriber(email, refCode, secret) {
  const token = createHmac("sha256", secret).update(email).digest("hex")
  const myRefCode = referralCode(email, secret)
  const store = getStore("subscribers")
  const refIndex = getStore("referral-index")

  const existing = await store.get(email)
  if (existing) return myRefCode

  await store.set(email, JSON.stringify({
    email,
    token,
    tier: "free",
    referralCode: myRefCode,
    referredBy: refCode || null,
    subscribedAt: new Date().toISOString(),
    confirmedAt: new Date().toISOString(),
  }))
  await refIndex.set(myRefCode, email)

  // Best effort: a stale or mistyped ref code just means no credit.
  if (refCode) {
    try {
      const referrerEmail = await refIndex.get(refCode)
      if (referrerEmail && referrerEmail !== email) {
        await getStore("referral-credits").set(`${refCode}:${email}`, new Date().toISOString())
      }
    } catch (err) {
      console.error("digest-signup: referral credit failed", err)
    }
  }
  return myRefCode
}
