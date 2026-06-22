/**
 * GET /.netlify/functions/subscribers-list
 *
 * Internal endpoint — returns all subscriber emails as JSON.
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
    const emails = blobs.map(b => b.key)

    return new Response(JSON.stringify({ emails, count: emails.length }), {
      headers: { "Content-Type": "application/json" },
    })
  } catch (err) {
    return new Response(JSON.stringify({ error: err?.message ?? String(err) }), {
      status: 500,
      headers: { "Content-Type": "application/json" },
    })
  }
}
