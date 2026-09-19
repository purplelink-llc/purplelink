/**
 * POST /.netlify/functions/subscriber-update
 * body: { email: "...", fields: { last_sent_slug?: "...", tier?: "..." } }
 *
 * Internal endpoint — merges `fields` into one subscriber's existing
 * record. Called by the Modal digest cron after sending, to record
 * last_sent_slug (see mailer.py). Only a fixed allowlist of fields may be
 * set this way -- this is a narrow, single-purpose bridge, not a general
 * subscriber-record editor, so a bug or bad input elsewhere can't
 * overwrite fields like `token` or `referralCode` that this endpoint has
 * no business touching.
 *
 * Authorization: Bearer <SUBSCRIBE_SECRET> required.
 *
 * Required env var: SUBSCRIBE_SECRET
 */
import { getStore } from "@netlify/blobs"

const ALLOWED_FIELDS = new Set(["last_sent_slug", "tier"])

function json(status, body) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  })
}

export default async function handler(request) {
  const secret = process.env.SUBSCRIBE_SECRET
  const auth = request.headers.get("authorization") ?? ""
  if (!secret || auth !== `Bearer ${secret}`) {
    return json(401, { error: "unauthorized" })
  }
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
  const fields = body?.fields ?? {}
  if (!email || typeof fields !== "object") {
    return json(400, { error: "invalid_body" })
  }

  const store = getStore("subscribers")
  const existing = await store.get(email)
  if (!existing) {
    return json(404, { error: "not_found" })
  }

  let record
  try {
    record = JSON.parse(existing)
  } catch {
    return json(500, { error: "corrupt_record" })
  }

  for (const [key, value] of Object.entries(fields)) {
    if (ALLOWED_FIELDS.has(key)) {
      record[key] = value
    }
  }

  await store.set(email, JSON.stringify(record))
  return json(200, { ok: true })
}
