/**
 * Netlify Function — gated delivery for photograph licenses and calendars.
 *
 *   GET /.netlify/functions/photo-download?session_id=cs_…              -> JSON list
 *   GET /.netlify/functions/photo-download?session_id=cs_…&file=photo   -> the original JPEG
 *   GET /.netlify/functions/photo-download?session_id=cs_…&file=license -> the license (text)
 *   GET /.netlify/functions/photo-download?session_id=cs_…&file=cal:<set>:<paper> -> a calendar PDF
 *
 * Same shape as kit-download.mjs: the Stripe Checkout Session is the bearer
 * token, it must be paid and belong to this account, and the product key in
 * its metadata decides what it entitles. Originals and PDFs live only in the
 * private `photo-files` Blobs store (scripts/photo-blobs-upload.sh), never in
 * the published site; the site carries watermarked copies.
 *
 * A license purchase delivers two things: the clean full-resolution JPEG of
 * the photograph named in session.metadata.photo, and a license text that
 * names the buyer, the file, the tier, the date and the terms, so the buyer
 * has a record to show whoever asks.
 */
import { getStore } from "@netlify/blobs";

const STRIPE_API = "https://api.stripe.com/v1";
const FILE_STORE = "photo-files";
const PHOTO_RE = /^DSC_[A-Za-z0-9-]{1,40}$/;

const TIERS = {
  "photo-license-web": {
    label: "Web and social license",
    terms: [
      "Scope: use on one website or blog and the social-media accounts, newsletters and presentations of the licensee, in digital form.",
      "Not included: print advertising, products or merchandise for sale, use in a logo or trademark, use by anyone other than the licensee, and training of machine-learning models.",
    ],
  },
  "photo-license-commercial": {
    label: "Commercial license",
    terms: [
      "Scope: use by one business on its websites, social-media accounts, newsletters, presentations, internal documents, trade-show and office displays, and printed marketing material of any run.",
      "Not included: products or merchandise for sale, use in a logo or trademark, sub-licensing or resale of the file, and training of machine-learning models.",
    ],
  },
  "photo-license-extended": {
    label: "Extended license",
    terms: [
      "Scope: everything in the commercial license, plus editorial publication (books, magazines, newspapers, documentaries), print advertising including billboards, and products or merchandise for sale up to 5,000 units.",
      "Not included: use in a logo or trademark, sub-licensing or resale of the file itself, use as a template or in a stock or design-asset collection, and training of machine-learning models.",
    ],
  },
};

const CALENDAR_SETS = ["iceland", "japan", "switzerland", "european-cities", "arizona-desert", "hawaii", "best-of"];
const CALENDAR_NAMES = {
  "iceland": "Iceland", "japan": "Japan", "switzerland": "Switzerland", "european-cities": "European Cities",
  "arizona-desert": "Arizona Desert", "hawaii": "Hawaii", "best-of": "Best Of",
};

function json(status, body) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json", "Cache-Control": "private, no-store" },
  });
}

async function loadSession(sessionId) {
  const secretKey = Netlify.env.get("STRIPE_SECRET_KEY");
  if (!secretKey) return { error: json(500, { error: "misconfigured", detail: "STRIPE_SECRET_KEY not set." }) };
  let resp;
  try {
    resp = await fetch(`${STRIPE_API}/checkout/sessions/${sessionId}`, {
      headers: { Authorization: `Bearer ${secretKey}` },
    });
  } catch (err) {
    return { error: json(502, { error: "stripe_unreachable", detail: String(err) }) };
  }
  if (!resp.ok) return { error: json(403, { error: "session_not_found", detail: "That download link is not valid for this store." }) };
  const session = await resp.json();
  if (session.payment_status !== "paid") return { error: json(403, { error: "not_paid", detail: "This order has not been paid." }) };
  return { session };
}

function calendarsFor(product) {
  if (product === "photo-calendar-bundle") return CALENDAR_SETS;
  const m = /^photo-calendar-(.+)$/.exec(product);
  return m && CALENDAR_SETS.includes(m[1]) ? [m[1]] : [];
}

function licenseText(session, product, photo) {
  const tier = TIERS[product];
  const when = new Date((session.created || 0) * 1000).toISOString().slice(0, 10);
  const buyer = session.customer_details?.name || "";
  const email = session.customer_details?.email || "";
  const amount = session.amount_total != null ? `$${(session.amount_total / 100).toFixed(2)} ${String(session.currency || "usd").toUpperCase()}` : "";
  return [
    "PHOTOGRAPH LICENSE",
    "",
    `Licensor: Benjamin Ampel, Purplelink LLC, Atlanta, Georgia, USA (ben@purplelink.llc)`,
    `Licensee: ${buyer}${email ? ` <${email}>` : ""}`,
    `Photograph: ${photo} (file ${photo}.jpeg, delivered at full resolution)`,
    `License: ${tier.label}`,
    `Date: ${when}`,
    `Order: ${session.id}${amount ? `, ${amount}` : ""}`,
    "",
    "Terms",
    `1. ${tier.terms[0]}`,
    `2. ${tier.terms[1]}`,
    "3. The license is non-exclusive, worldwide and does not expire. The photographer keeps the copyright and may license the same photograph to others.",
    "4. Credit is appreciated but not required: \"Photo: Benjamin Ampel / purplelink.llc\".",
    "5. The photograph may be cropped, colour-adjusted and combined with text or other images; it may not be presented in a way that is defamatory or that implies the photographer's endorsement.",
    "6. The file is for the licensee's own use and may be given to a printer, designer or agency working for the licensee for that use only.",
    "7. If a use outside this scope is needed, write to ben@purplelink.llc for a quote.",
    "",
    "Keep this text with the file; it is your record of the license.",
    "",
  ].join("\n");
}

export default async function handler(request) {
  if (request.method !== "GET" && request.method !== "HEAD") return json(405, { error: "method_not_allowed" });

  const url = new URL(request.url);
  const sessionId = url.searchParams.get("session_id") || "";
  const fileKey = url.searchParams.get("file") || "";
  if (!/^cs_[A-Za-z0-9_]{10,200}$/.test(sessionId)) {
    return json(400, { error: "bad_session_id", detail: "Missing or malformed session_id." });
  }

  const { session, error } = await loadSession(sessionId);
  if (error) return error;
  const product = session.metadata?.product || "";
  const photo = session.metadata?.photo || "";
  const isLicense = Object.prototype.hasOwnProperty.call(TIERS, product) && PHOTO_RE.test(photo);
  const calendars = calendarsFor(product);
  if (!isLicense && !calendars.length) {
    return json(404, { error: "unknown_product", detail: "We could not match this order to a photograph product. Contact ben@purplelink.llc." });
  }

  const base = `/.netlify/functions/photo-download?session_id=${encodeURIComponent(sessionId)}&file=`;
  if (!fileKey) {
    const files = [];
    if (isLicense) {
      files.push({ key: "photo", label: `${photo}.jpeg, full resolution`, url: base + "photo" });
      files.push({ key: "license", label: `${TIERS[product].label} (text)`, url: base + "license" });
    }
    for (const set of calendars) {
      for (const paper of ["letter", "a4"]) {
        files.push({ key: `cal:${set}:${paper}`, label: `2027 ${CALENDAR_NAMES[set]} calendar, ${paper === "a4" ? "A4" : "US Letter"} (PDF)`,
          url: base + encodeURIComponent(`cal:${set}:${paper}`) });
      }
    }
    return json(200, { product, photo: isLicense ? photo : undefined, files });
  }

  if (fileKey === "license" && isLicense) {
    const text = licenseText(session, product, photo);
    return new Response(text, {
      status: 200,
      headers: {
        "Content-Type": "text/plain; charset=utf-8",
        "Content-Disposition": `attachment; filename="license-${photo}.txt"`,
        "Cache-Control": "private, no-store",
        "X-Content-Type-Options": "nosniff",
      },
    });
  }

  let blobName, outName, type;
  if (fileKey === "photo" && isLicense) {
    blobName = `${photo}.jpeg`; outName = `${photo}.jpeg`; type = "image/jpeg";
  } else {
    const m = /^cal:([a-z-]+):(letter|a4)$/.exec(fileKey);
    if (!m || !calendars.includes(m[1])) return json(403, { error: "not_entitled", detail: "This order does not include that file." });
    blobName = `calendar-2027-${m[1]}-${m[2]}.pdf`; outName = blobName; type = "application/pdf";
  }

  let bytes;
  try {
    const blob = await getStore(FILE_STORE).get(blobName, { type: "arrayBuffer" });
    if (!blob) throw new Error(`missing blob ${blobName}`);
    bytes = new Uint8Array(blob);
  } catch (err) {
    return json(500, { error: "file_unavailable", detail: "The file is temporarily unavailable. Email ben@purplelink.llc with your order id and it will be sent directly." });
  }
  return new Response(bytes, {
    status: 200,
    headers: {
      "Content-Type": type,
      "Content-Disposition": `attachment; filename="${outName}"`,
      "Content-Length": String(bytes.length),
      "Cache-Control": "private, no-store",
      "X-Content-Type-Options": "nosniff",
    },
  });
}
