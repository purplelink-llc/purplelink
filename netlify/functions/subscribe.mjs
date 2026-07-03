/**
 * POST /.netlify/functions/subscribe
 * body: { email: "...", ref?: "<referral code>" }
 *
 * Adds a subscriber to the Netlify Blobs "subscribers" store.
 * Idempotent — re-subscribing an existing email succeeds silently.
 *
 * Referral: every subscriber gets a stable referral code (HMAC of their
 * email, namespaced separately from the unsubscribe token so sharing one
 * can never be used to derive the other). If `ref` matches a known code,
 * the referring subscriber's referralCount is incremented. This is a
 * plain recommendation mechanic — no credits or rewards are promised or
 * tracked; referralCount is just a courtesy shown back to the referrer.
 *
 * Required env var: SUBSCRIBE_SECRET
 */
import { getStore } from "@netlify/blobs"
import { createHmac } from "node:crypto"

function json(status, body) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  })
}

function referralCode(email, secret) {
  return createHmac("sha256", secret).update(`ref:${email}`).digest("hex").slice(0, 10)
}

export default async function handler(request) {
  if (request.method !== "POST") {
    return json(405, { error: "method_not_allowed" })
  }

  let body
  try {
    body = await request.json()
  } catch {
    return json(400, { error: "invalid_json" })
  }

  const email = (body?.email ?? "").toLowerCase().trim()
  if (!email || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
    return json(400, { error: "invalid_email" })
  }
  const refCode = typeof body?.ref === "string" ? body.ref.trim().slice(0, 32) : ""

  const secret = process.env.SUBSCRIBE_SECRET
  if (!secret) {
    console.error("subscribe: SUBSCRIBE_SECRET not set")
    return json(500, { error: "server_error" })
  }

  const token = createHmac("sha256", secret).update(email).digest("hex")
  const myRefCode = referralCode(email, secret)
  const store = getStore("subscribers")
  const refIndex = getStore("referral-index")

  const existing = await store.get(email)
  if (!existing) {
    await store.set(email, JSON.stringify({
      email,
      token,
      referralCode: myRefCode,
      referralCount: 0,
      referredBy: refCode || null,
      subscribedAt: new Date().toISOString(),
    }))
    await refIndex.set(myRefCode, email)

    // Credit the referrer, if the code matches a real subscriber. Best
    // effort — a stale or mistyped ref code just means no credit, not
    // a failed subscribe.
    if (refCode) {
      try {
        const referrerEmail = await refIndex.get(refCode)
        if (referrerEmail && referrerEmail !== email) {
          const referrerRaw = await store.get(referrerEmail)
          if (referrerRaw) {
            const referrer = JSON.parse(referrerRaw)
            referrer.referralCount = (referrer.referralCount || 0) + 1
            await store.set(referrerEmail, JSON.stringify(referrer))
          }
        }
      } catch (err) {
        console.error("subscribe: referral credit failed", err)
      }
    }
  } else {
    // Backfill: subscribers who joined before the referral mechanic
    // existed have a record with no referralCode. Add it on their next
    // visit (re-submitting the form is idempotent and harmless) so their
    // link starts working without needing a separate migration.
    try {
      const record = JSON.parse(existing)
      if (!record.referralCode) {
        record.referralCode = myRefCode
        await store.set(email, JSON.stringify(record))
        await refIndex.set(myRefCode, email)
      }
    } catch (err) {
      console.error("subscribe: referral backfill failed", err)
    }
  }

  return json(200, { ok: true, referralCode: myRefCode })
}
