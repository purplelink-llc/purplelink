/**
 * ONE-OFF admin tool — issues and emails a ModernTex license key to every existing paid
 * purchaser (bought before license keys existed). Runs server-side specifically so it can
 * read RESEND_API_KEY and MODERNTEX_LICENSE_PRIVATE_KEY, both Netlify "sensitive" variables
 * that cannot be retrieved via the CLI/API by design — this endpoint is the correct place for
 * that logic to run, not a local script trying to exfiltrate them.
 *
 * Auth: header X-Backissue-Secret must match MODERNTEX_BACKISSUE_SECRET (a one-time secret,
 * unrelated to any other credential). Delete this file (and the env var) once it has been
 * run for real — it is not meant to be a standing endpoint.
 *
 * GET  ?send=0 (default) — dry run: lists what would be sent, sends nothing.
 * GET  ?send=1            — actually emails every match via Resend.
 */
import { randomBytes, sign as edSign, createPrivateKey, timingSafeEqual } from "node:crypto";

const PUB_B64 = "2bJapUgUz0FhlnCVgEnPUGOdr6TE8swfvdqHkB/6cBM=";
const DOMAIN = Buffer.from("ModernTexLicenseV1", "utf8");
const ALPHA = "0123456789ABCDEFGHJKMNPQRSTVWXYZ";

function b32(buf) {
  let bits = 0n, bitCount = 0, out = "";
  for (const byte of buf) {
    bits = (bits << 8n) | BigInt(byte);
    bitCount += 8;
    while (bitCount >= 5) { bitCount -= 5; out += ALPHA[Number((bits >> BigInt(bitCount)) & 0x1fn)]; }
  }
  if (bitCount > 0) out += ALPHA[Number((bits << BigInt(5 - bitCount)) & 0x1fn)];
  return out;
}

function issueLicense() {
  const privB64 = Netlify.env.get("MODERNTEX_LICENSE_PRIVATE_KEY");
  const b64url = (s) => s.replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
  const privateKey = createPrivateKey({
    key: { kty: "OKP", crv: "Ed25519", d: b64url(privB64), x: b64url(PUB_B64) },
    format: "jwk",
  });
  const nonce = randomBytes(4);
  const sig = edSign(null, Buffer.concat([DOMAIN, nonce]), privateKey);
  const body = b32(Buffer.concat([nonce, sig]));
  return "MTX1-" + (body.match(/.{1,5}/g) ?? []).join("-");
}

async function listPaidModernTexSessions() {
  const key = Netlify.env.get("STRIPE_SECRET_KEY");
  const all = [];
  let startingAfter = null;
  for (let page = 0; page < 50; page++) {
    const url = new URL("https://api.stripe.com/v1/checkout/sessions");
    url.searchParams.set("limit", "100");
    if (startingAfter) url.searchParams.set("starting_after", startingAfter);
    const resp = await fetch(url, { headers: { Authorization: `Bearer ${key}` } });
    if (!resp.ok) throw new Error(`Stripe list failed: ${resp.status}`);
    const data = await resp.json();
    all.push(...data.data);
    if (!data.has_more) break;
    startingAfter = data.data[data.data.length - 1].id;
  }
  return all.filter((s) => s.payment_status === "paid" && (s.metadata?.product || "") === "moderntex");
}

function emailBody(license) {
  const text =
    `Thanks again for buying ModernTex.\n\n` +
    `We've added license keys so ModernTex can work as one build with a free trial, ` +
    `unlockable permanently — this email is just catching up everyone who bought before ` +
    `that existed. Nothing changes for you: your existing download keeps working exactly ` +
    `as it does today.\n\n` +
    `Your license key (paste into ModernTex's "Have a license key?" if you ever reinstall ` +
    `or update):\n\n${license}\n\n` +
    `This unlocks the app permanently, offline — no account, no further steps.\n\n` +
    `Questions: just reply to this email.\n\n` +
    `Purplelink LLC, Atlanta, Georgia`;
  const html =
    `<p>Thanks again for buying ModernTex.</p>` +
    `<p>We've added license keys so ModernTex can work as one build with a free trial, ` +
    `unlockable permanently — this email is just catching up everyone who bought before ` +
    `that existed. Nothing changes for you: your existing download keeps working exactly ` +
    `as it does today.</p>` +
    `<p>Your license key (paste into ModernTex's "Have a license key?" if you ever reinstall ` +
    `or update):</p>` +
    `<p style="font-family: ui-monospace, monospace; font-size: 14px; letter-spacing: 0.5px;">${license}</p>` +
    `<p>This unlocks the app permanently, offline — no account, no further steps.</p>` +
    `<p>Questions: just reply to this email.</p>` +
    `<p>Purplelink LLC, Atlanta, Georgia</p>`;
  return { text, html };
}

function mask(email) {
  return email.replace(/(.{2}).*(@.*)/, "$1***$2");
}

export default async function handler(request) {
  const expected = Netlify.env.get("MODERNTEX_BACKISSUE_SECRET");
  const presented = request.headers.get("x-backissue-secret") || "";
  if (!expected || presented.length !== expected.length ||
      !timingSafeEqual(Buffer.from(presented), Buffer.from(expected))) {
    return new Response(JSON.stringify({ error: "forbidden" }), { status: 403 });
  }

  const url = new URL(request.url);
  const send = url.searchParams.get("send") === "1";
  const resendKey = Netlify.env.get("RESEND_API_KEY");

  let sessions;
  try {
    sessions = await listPaidModernTexSessions();
  } catch (err) {
    return new Response(JSON.stringify({ error: "stripe_list_failed", detail: String(err) }), { status: 502 });
  }

  const results = [];
  for (const s of sessions) {
    const email = s.customer_details?.email || s.customer_email || "";
    if (!email) { results.push({ session: s.id, status: "skipped_no_email" }); continue; }
    if (!send) { results.push({ session: s.id, email: mask(email), status: "dry_run" }); continue; }
    const license = issueLicense();
    const { text, html } = emailBody(license);
    try {
      const resp = await fetch("https://api.resend.com/emails", {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${resendKey}` },
        body: JSON.stringify({
          from: "Purplelink LLC <orders@purplelink.llc>",
          reply_to: "ben@purplelink.llc",
          to: [email],
          subject: "Your ModernTex license key",
          text, html,
        }),
      });
      results.push({ session: s.id, email: mask(email), status: resp.ok ? "sent" : "failed", httpStatus: resp.status });
    } catch (err) {
      results.push({ session: s.id, email: mask(email), status: "failed", error: String(err) });
    }
  }
  return new Response(JSON.stringify({ mode: send ? "send" : "dry_run", total: sessions.length, results }, null, 2), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}
