/**
 * Netlify Function — IndexNow ping.
 *
 * Invoked by a Netlify "Deploy succeeded" outgoing webhook so that every
 * production deploy automatically pings Bing / Yandex / Seznam / Naver about
 * URLs whose lastmod matches today's date in the sitemap.
 *
 * Auth: require ?token=$INDEXNOW_WEBHOOK_TOKEN. Set that env var via
 * `netlify env:set INDEXNOW_WEBHOOK_TOKEN <value>`. The deploy-succeeded
 * webhook URL configured in Netlify must include the token in the query
 * string; any request without the matching token is rejected.
 *
 * Function URL (after deploy):
 *   https://purplelink.llc/.netlify/functions/indexnow-ping?token=...
 *
 * Manual test:
 *   curl -X POST "https://purplelink.llc/.netlify/functions/indexnow-ping?token=...&all=1"
 *
 * Query params:
 *   token  — required, must match INDEXNOW_WEBHOOK_TOKEN env var.
 *   all=1  — ping every URL in the sitemap (use sparingly, IndexNow caps).
 *            Default: ping only URLs whose lastmod is today's date.
 */

const INDEXNOW_KEY = '7c6ea98702bc415eccb029b334bc63fef6905e06458c01f93ea762fa140019cf';
const HOST = 'purplelink.llc';
const SITEMAP_URL = `https://${HOST}/sitemap.xml`;
const KEY_LOCATION = `https://${HOST}/${INDEXNOW_KEY}.txt`;
const ENDPOINT = 'https://api.indexnow.org/IndexNow';

function jsonResponse(status, body) {
  return new Response(JSON.stringify(body, null, 2), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

export default async function handler(request, context) {
  const url = new URL(request.url);
  const token = url.searchParams.get('token');
  const expected = Netlify.env.get('INDEXNOW_WEBHOOK_TOKEN');

  if (!expected) {
    // Misconfigured deployment — fail loud so the operator sees it in logs.
    return jsonResponse(500, {
      status: 'misconfigured',
      reason: 'INDEXNOW_WEBHOOK_TOKEN env var not set',
    });
  }

  if (token !== expected) {
    return jsonResponse(401, { status: 'unauthorized' });
  }

  // Fetch the live sitemap (just-published, since deploy succeeded).
  let sitemapXml;
  try {
    const resp = await fetch(SITEMAP_URL, { cache: 'no-store' });
    if (!resp.ok) {
      return jsonResponse(502, {
        status: 'sitemap-fetch-failed',
        httpStatus: resp.status,
      });
    }
    sitemapXml = await resp.text();
  } catch (err) {
    return jsonResponse(502, { status: 'sitemap-fetch-error', error: String(err) });
  }

  // Parse out <url><loc>...</loc><lastmod>YYYY-MM-DD</lastmod></url> blocks.
  // The two tags may be in any order within a <url> block, so handle both.
  const blockRe = /<url>([\s\S]*?)<\/url>/g;
  const locRe = /<loc>([^<]+)<\/loc>/;
  const modRe = /<lastmod>([^<]+)<\/lastmod>/;

  const today = new Date().toISOString().slice(0, 10);
  const allMode = url.searchParams.get('all') === '1';
  const urls = [];

  let block;
  while ((block = blockRe.exec(sitemapXml)) !== null) {
    const inner = block[1];
    const loc = inner.match(locRe)?.[1];
    const mod = inner.match(modRe)?.[1]?.slice(0, 10);
    if (!loc) continue;
    if (allMode || mod === today) urls.push(loc);
  }

  if (urls.length === 0) {
    return jsonResponse(200, { status: 'no-op', reason: 'no URLs to ping', today });
  }

  // Ping IndexNow.
  let indexNowStatus, indexNowBody;
  try {
    const resp = await fetch(ENDPOINT, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json; charset=utf-8' },
      body: JSON.stringify({
        host: HOST,
        key: INDEXNOW_KEY,
        keyLocation: KEY_LOCATION,
        urlList: urls,
      }),
    });
    indexNowStatus = resp.status;
    indexNowBody = await resp.text();
  } catch (err) {
    return jsonResponse(502, { status: 'indexnow-error', error: String(err) });
  }

  return jsonResponse(200, {
    status: indexNowStatus >= 200 && indexNowStatus < 300 ? 'pinged' : 'failed',
    indexNowStatus,
    indexNowBody: indexNowBody.slice(0, 200),
    urlCount: urls.length,
    urls,
  });
}
