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
    const { blobs } = await store.list()
    const subscribers = await Promise.all(
      blobs.map(async (b) => {
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
