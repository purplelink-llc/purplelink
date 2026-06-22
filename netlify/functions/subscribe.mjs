/**
 * POST /.netlify/functions/subscribe
 * body: { email: "..." }
 *
 * Adds a subscriber to the Netlify Blobs "subscribers" store.
 * Idempotent — re-subscribing an existing email succeeds silently.
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

  const secret = process.env.SUBSCRIBE_SECRET
  if (!secret) {
    console.error("subscribe: SUBSCRIBE_SECRET not set")
    return json(500, { error: "server_error" })
  }

  const token = createHmac("sha256", secret).update(email).digest("hex")
  const store = getStore("subscribers")

  const existing = await store.get(email)
  if (!existing) {
    await store.set(email, JSON.stringify({
      email,
      token,
      subscribedAt: new Date().toISOString(),
    }))
  }

  return json(200, { ok: true })
}
