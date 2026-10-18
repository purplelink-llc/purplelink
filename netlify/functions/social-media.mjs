/**
 * Netlify Function — public image host for the social poster (Threads fetches images from a public URL).
 * Images live in the dedicated `social-media` Blobs store, uploaded by backend/scripts/social.py with the Netlify CLI
 * under a content-addressed key (first 40 hex characters of the file's sha256, plus .png/.jpg/.jpeg).
 *
 *   GET|HEAD /social-media/<key>  -> the image (long immutable cache)
 *
 * Read-only: no listing, no other method, no other store. The key is matched against a strict pattern before it is
 * used, which also rules out path traversal. The first bytes must match the extension, so the store can only ever
 * serve a PNG or a JPEG. Nothing is counted or logged.
 */
import { getStore } from "@netlify/blobs";

const STORE = "social-media";
const KEY = /^[a-f0-9]{40}\.(png|jpe?g)$/;
const PNG = [0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a];
const JPG = [0xff, 0xd8, 0xff];

function notFound() {
  return new Response("Not found", {
    status: 404,
    headers: { "Content-Type": "text/plain; charset=utf-8", "Cache-Control": "public, max-age=60" },
  });
}

function requestedKey(url) {
  let key = url.searchParams.get("file");
  if (key === null) {
    const prefix = "/social-media/";
    let path;
    try {
      path = decodeURIComponent(url.pathname);
    } catch {
      return null;
    }
    if (!path.startsWith(prefix)) return null;
    key = path.slice(prefix.length);
  }
  return KEY.test(key) ? key : null;
}

function startsWith(bytes, sig) {
  return sig.every((b, i) => bytes[i] === b);
}

export default async function handler(request) {
  if (request.method !== "GET" && request.method !== "HEAD") {
    return new Response("Method not allowed", { status: 405, headers: { Allow: "GET, HEAD" } });
  }
  const key = requestedKey(new URL(request.url));
  if (!key) return notFound();

  let body;
  try {
    body = await getStore(STORE).get(key, { type: "arrayBuffer" });
  } catch {
    return new Response("Temporarily unavailable", { status: 503, headers: { "Cache-Control": "no-store" } });
  }
  if (!body) return notFound();

  const bytes = new Uint8Array(body);
  const png = key.endsWith(".png");
  if (!startsWith(bytes, png ? PNG : JPG)) return notFound();

  const headers = {
    "Content-Type": png ? "image/png" : "image/jpeg",
    "Cache-Control": "public, max-age=31536000, immutable",
    "Content-Length": String(body.byteLength),
    "X-Content-Type-Options": "nosniff",
  };
  if (request.method === "HEAD") return new Response(null, { status: 200, headers });
  return new Response(body, { status: 200, headers });
}
