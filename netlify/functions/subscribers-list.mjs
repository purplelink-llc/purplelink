/**
 * GET /.netlify/functions/subscribers-list
 *
 * Internal endpoint — returns all subscriber records as JSON.
 * Called by the Modal cron to get the mailing list before sending.
 *
 * Authorization: Bearer <SUBSCRIBE_SECRET> required.
 *
 * Required env var: SUBSCRIBE_SECRET
 */
import { getStore } from "@netlify/blobs"

export default async function handler(request) {
  const secret = process.env.SUBSCRIBE_SECRET
  const auth = request.headers.get("authorization") ?? ""

  if (!secret || auth !== `Bearer ${secret}`) {
    return new Response("Unauthorized", { status: 401 })
  }

  try {
    const store = getStore("subscribers")
    // store.list() pages results; following the cursor matters once the
    // subscriber count crosses one page, or the digest send this endpoint
    // feeds would silently drop everyone past page 1 (found 2026-09-21
    // backend audit).
    let cursor
    const allBlobs = []
    do {
      const { blobs, cursor: nextCursor } = await store.list({ cursor })
      allBlobs.push(...blobs)
      cursor = nextCursor
    } while (cursor)
    const subscribers = await Promise.all(
      allBlobs.map(async (b) => {
        const raw = await store.get(b.key)
        try {
          return JSON.parse(raw)
        } catch {
          return null
        }
      })
    )
    const valid = subscribers.filter(Boolean)

    return new Response(JSON.stringify({ subscribers: valid, count: valid.length }), {
      headers: { "Content-Type": "application/json" },
    })
  } catch (err) {
    return new Response(JSON.stringify({ error: err?.message ?? String(err) }), {
      status: 500,
      headers: { "Content-Type": "application/json" },
    })
  }
}
