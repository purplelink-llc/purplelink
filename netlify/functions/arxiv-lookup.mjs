/**
 * Netlify Function — arXiv metadata proxy for the citation generator.
 *
 * GET /.netlify/functions/arxiv-lookup?id=<arxiv-id>
 *
 * export.arxiv.org's query API sends no Access-Control-Allow-Origin header
 * (confirmed 2026-09-21), so it can never be called directly from a browser
 * no matter what CSP allows — unlike Crossref and Open Library, which do
 * support cross-origin fetches and are called directly from the client. This
 * function fetches arXiv server-side (no CORS restriction there) and returns
 * the same Atom XML unchanged, so the client's existing DOMParser-based
 * parsing in citation-generator/index.html needs no change beyond the URL.
 */

const ARXIV_API = "https://export.arxiv.org/api/query";

// New-style (1706.03762, optionally versioned 1706.03762v2) or old-style
// (hep-th/9901001) arXiv identifiers. Rejects anything else so this can't be
// used as an open relay to arbitrary query strings against arXiv's API.
const ARXIV_ID_RE = /^([a-z-]+(\.[A-Z]{2})?\/\d{7}|\d{4}\.\d{4,5})(v\d+)?$/i;

function jsonResponse(status, body) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

export default async function handler(request) {
  if (request.method !== "GET") {
    return jsonResponse(405, { error: "method_not_allowed" });
  }

  const id = new URL(request.url).searchParams.get("id") || "";
  if (!ARXIV_ID_RE.test(id)) {
    return jsonResponse(400, { error: "invalid_arxiv_id" });
  }

  let resp;
  try {
    resp = await fetch(`${ARXIV_API}?id_list=${encodeURIComponent(id)}&max_results=1`);
  } catch (err) {
    return jsonResponse(502, { error: "arxiv_unreachable", detail: String(err) });
  }

  if (!resp.ok) {
    return jsonResponse(resp.status, { error: "arxiv_error", status: resp.status });
  }

  const xml = await resp.text();
  return new Response(xml, {
    status: 200,
    headers: { "Content-Type": "application/atom+xml; charset=utf-8" },
  });
}
