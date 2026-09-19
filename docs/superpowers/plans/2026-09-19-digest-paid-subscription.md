# Digest Paid Subscription Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a real, paid ($5/mo or $40/yr) same-day-delivery email tier for
the Purplelink Daily Digest, alongside the existing free web archive and a
new free-but-2-day-delayed email tier, giving the business its first
genuine recurring-MRR product.

**Architecture:** Extends four existing systems rather than building new
ones: `checkout.mjs`/`stripe-webhook.mjs` (Stripe, JS/Netlify Functions)
gain subscription-mode support and exactly one new webhook event; the
`subscribers` Netlify Blobs store gains a `tier` field, defaulted lazily
the same way `referralCode` already is; `mailer.py`/`publisher.py`
(Python/Modal) gain a second, delayed send path that reloads a JSON
snapshot of a past day's digest (a new artifact — today only rendered HTML
is persisted) to re-render that day's email fresh, rather than storing a
second copy of pre-rendered email HTML.

**Tech Stack:** Netlify Functions (Node/JS), Netlify Blobs, Stripe Checkout
+ Webhooks + Customer Portal, Modal (Python), GitHub Contents API (existing
publish path), Resend (existing email delivery).

**Spec:** `docs/superpowers/specs/2026-09-19-digest-paid-subscription-design.md`

**Before starting:** confirm this is a git repo (`git rev-parse
--is-inside-work-tree` — it is; this whole plan's commit steps are real,
not optional save points) and that `pytest` is available for the Python
tasks (`cd backend && python3 -m pytest --version`).

---

### Task 1: Stripe products — `checkout.mjs` gets a `mode` field

**Files:**
- Modify: `netlify/functions/checkout.mjs:77-98` (PRODUCT_CATALOG), `:175` (mode)

- [ ] **Step 1: Add `mode` to every existing catalog entry, defaulting to `"payment"`**

Open `netlify/functions/checkout.mjs`. The catalog currently looks like:

```js
const PRODUCT_CATALOG = {
  "paper-review-standard":   { envKey: "STRIPE_PRICE_PAPER_REVIEW_STANDARD",   successPath: "/tools/paper-review/upload/" },
  "paper-review-journal":    { envKey: "STRIPE_PRICE_PAPER_REVIEW_JOURNAL",    successPath: "/tools/paper-review/upload/" },
  // ... more entries ...
};
```

Do not touch the existing entries — no entry needs a `mode` key added,
since the code change in Step 2 defaults missing `mode` to `"payment"`.
Add two new entries at the end of the object, before the closing `};`:

```js
  "digest-monthly": {
    envKey: "STRIPE_PRICE_DIGEST_MONTHLY",
    successPath: "/blog/digest/subscribed/",
    mode: "subscription",
  },
  "digest-annual": {
    envKey: "STRIPE_PRICE_DIGEST_ANNUAL",
    successPath: "/blog/digest/subscribed/",
    mode: "subscription",
  },
```

- [ ] **Step 2: Make the Stripe session's `mode` read from the catalog entry**

At line 175, find:

```js
    mode: "payment",
```

Replace with:

```js
    mode: entry.mode || "payment",
```

(`entry` is already the in-scope `PRODUCT_CATALOG[productKey]` variable at
this point in the function — confirm the variable name by reading the ~20
lines above line 175 before editing; it may be named differently, e.g.
`product` or `catalogEntry`. Use whatever name the function already uses
for the looked-up catalog entry, don't introduce a new one.)

- [ ] **Step 3: Create the two Stripe Prices**

This is a one-time manual step, not code — run once, before deploying:

```bash
STRIPE_KEY=$(netlify env:get STRIPE_SECRET_KEY --context production)
curl -s https://api.stripe.com/v1/products -u "$STRIPE_KEY:" -d name="Purplelink Daily Digest" -d description="Same-day delivery of the Purplelink Daily Digest"
# note the returned "id", e.g. prod_XXXX, then:
curl -s https://api.stripe.com/v1/prices -u "$STRIPE_KEY:" \
  -d product=prod_XXXX -d unit_amount=500 -d currency=usd \
  -d "recurring[interval]=month"
curl -s https://api.stripe.com/v1/prices -u "$STRIPE_KEY:" \
  -d product=prod_XXXX -d unit_amount=4000 -d currency=usd \
  -d "recurring[interval]=year"
```

Take the two returned Price ids (`price_...`) and set them:

```bash
netlify env:set STRIPE_PRICE_DIGEST_MONTHLY price_XXXX --context production --force
netlify env:set STRIPE_PRICE_DIGEST_ANNUAL price_YYYY --context production --force
```

- [ ] **Step 4: Verify both new products return a real subscription session**

```bash
curl -s -X POST https://purplelink.llc/.netlify/functions/checkout \
  -H "Content-Type: application/json" \
  -d '{"product":"digest-monthly"}'
```

Expected: a JSON body containing a `url` starting `https://checkout.stripe.com/...`.
Open that URL in a browser (or check via the Stripe Dashboard's test-mode
log) and confirm it shows "Subscribe" / a recurring amount, not "Pay" —
this is the one thing curl alone can't verify, since `mode` isn't visible
in the JSON response itself.

- [ ] **Step 5: Commit**

```bash
git add netlify/functions/checkout.mjs
git commit -m "checkout: add subscription-mode support, two digest products"
```

---

### Task 2: Subscriber data model — `tier` field

**Files:**
- Modify: `netlify/functions/subscribe.mjs:62-69` (new-record shape)
- Modify: `netlify/functions/subscribers-list.mjs` (return full records)
- Test: manual (no existing JS test framework in this repo — see Task 8 for the one place Python tests apply)

- [ ] **Step 1: New free signups get `tier: "free"`**

In `netlify/functions/subscribe.mjs`, find the new-subscriber block:

```js
  const existing = await store.get(email)
  if (!existing) {
    await store.set(email, JSON.stringify({
      email,
      token,
      referralCode: myRefCode,
      referralCount: 0,
      referredBy: refCode || null,
      subscribedAt: new Date().toISOString(),
    }))
```

Add `tier: "free"` to that object:

```js
  const existing = await store.get(email)
  if (!existing) {
    await store.set(email, JSON.stringify({
      email,
      token,
      tier: "free",
      referralCode: myRefCode,
      referralCount: 0,
      referredBy: refCode || null,
      subscribedAt: new Date().toISOString(),
    }))
```

- [ ] **Step 2: Existing (pre-launch) subscribers backfill to `tier: "legacy"` lazily**

Follow the exact pattern already used for `referralCode` backfill, a few
lines below in the same file:

```js
  } else {
    // Backfill: subscribers who joined before the referral mechanic
    // existed have a record with no referralCode. Add it on their next
    // visit (re-submitting the form is idempotent and harmless) so their
    // link starts working without needing a separate migration.
    try {
      const record = JSON.parse(existing)
      if (!record.referralCode) {
        record.referralCode = myRefCode
        await store.set(email, JSON.stringify(record))
        await refIndex.set(myRefCode, email)
      }
    } catch (err) {
      console.error("subscribe: referral backfill failed", err)
    }
  }
```

Add a `tier` backfill in the same `try` block, right after the
`referralCode` check:

```js
      if (!record.referralCode) {
        record.referralCode = myRefCode
        await store.set(email, JSON.stringify(record))
        await refIndex.set(myRefCode, email)
      }
      if (!record.tier) {
        record.tier = "legacy"
        await store.set(email, JSON.stringify(record))
      }
```

This only fires when someone re-submits the signup form with an email
that's already subscribed — it does **not** cover subscribers who never
revisit the form. Task 8's mailer-side logic must therefore also treat a
record with no `tier` field as `"legacy"` directly (never assume every
record has been backfilled by the time mailer.py reads it) — this is
covered in Task 8, Step 1.

- [ ] **Step 3: `subscribers-list.mjs` returns full records, not bare emails**

The mailer needs `tier` and (after Task 8) `last_sent_slug` per subscriber,
not just an email string. Replace the body of
`netlify/functions/subscribers-list.mjs`:

```js
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
```

This changes the response shape from `{emails: [...], count}` to
`{subscribers: [{email, tier, ...}, ...], count}` — Task 8 updates
`mailer.py`'s `_get_subscribers` to match. One other consumer exists,
`backend/scripts/track_subscribers.py` (a manual growth-tracking script,
not part of the daily cron) — confirmed by a repo-wide search for
`subscribers-list` before writing this plan. It only reads the `count`
field, which this new response shape still includes unchanged, so it is
not broken by this change. Re-run it once after deploying this task anyway
to be sure: `python3 backend/scripts/track_subscribers.py` should still
print `Recorded: ... -> N subscribers`, not an error.

- [ ] **Step 4: Commit**

```bash
git add netlify/functions/subscribe.mjs netlify/functions/subscribers-list.mjs
git commit -m "subscribe: add tier field (free/legacy), list full subscriber records"
```

---

### Task 3: Subscriber-update bridge for Python

Python (`mailer.py`, on Modal) has no direct write access to Netlify Blobs
today — it only reads via `subscribers-list.mjs`. It needs to write
`last_sent_slug` after each send (Task 8). Rather than giving Python raw
Netlify Blobs API access (a new, parallel pattern inconsistent with how
this codebase already bridges Python↔JS for this exact subsystem), add one
companion write endpoint following the same Bearer-token-gated shape as
`subscribers-list.mjs`.

**Files:**
- Create: `netlify/functions/subscriber-update.mjs`

- [ ] **Step 1: Write the endpoint**

```js
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
```

- [ ] **Step 2: Verify it rejects an unlisted field and accepts an allowed one**

```bash
SECRET=$(netlify env:get SUBSCRIBE_SECRET --context production)
# should 404 (no such test subscriber) or 200, never 500, and must not
# let `token` be overwritten even if sent:
curl -s -X POST https://purplelink.llc/.netlify/functions/subscriber-update \
  -H "Authorization: Bearer $SECRET" -H "Content-Type: application/json" \
  -d '{"email":"nonexistent-test@example.com","fields":{"last_sent_slug":"2026-09-19","token":"should-be-ignored"}}'
```

Expected: `{"error":"not_found"}` with HTTP 404, since no such subscriber
exists — this confirms the endpoint is live and doesn't 500 on a
well-formed request. A full write-then-read test happens in Task 8's live
verification, against a real test subscriber.

- [ ] **Step 3: Commit**

```bash
git add netlify/functions/subscriber-update.mjs
git commit -m "add subscriber-update: narrow write bridge for the Modal cron"
```

---

### Task 4: Stripe webhook — upsert on subscription checkout

**Files:**
- Modify: `netlify/functions/stripe-webhook.mjs`

- [ ] **Step 1: Add the two digest product keys to `PURPLELINK_PRODUCTS`**

`netlify/functions/stripe-webhook.mjs:47-59` defines:

```js
const PURPLELINK_PRODUCTS = new Set([
  "paper-review-standard",
  "paper-review-journal",
  "paper-review-deep",
  "paper-review-pack-5",
  "paper-review-pack-20",
  "cover-letter",
  "anonymity-check",
  "citation-gap",
  "revision-review",
  "response-review",
  "resume-review",
]);
```

Without this, line 332's foreign-product check (`if (rawProduct &&
!PURPLELINK_PRODUCTS.has(rawProduct))`) rejects `digest-monthly`/
`digest-annual` before the new branch in Step 3 is ever reached. Add both:

```js
const PURPLELINK_PRODUCTS = new Set([
  "paper-review-standard",
  "paper-review-journal",
  "paper-review-deep",
  "paper-review-pack-5",
  "paper-review-pack-20",
  "cover-letter",
  "anonymity-check",
  "citation-gap",
  "revision-review",
  "response-review",
  "resume-review",
  "digest-monthly",
  "digest-annual",
]);
```

- [ ] **Step 2: Import `getStore`**

Line 30 currently imports only from `node:crypto`:

```js
import { createHmac, timingSafeEqual, randomBytes, sign as edSign, createPrivateKey } from "node:crypto";
```

Add a new import line right after it (the webhook doesn't touch Netlify
Blobs anywhere today — Paper Review/ModernTex fulfillment goes through
Modal and the Blobs-based file stores respectively, not this pattern):

```js
import { getStore } from "@netlify/blobs";
```

- [ ] **Step 3: Add the digest-subscription branch**

At line 335 (the blank line right after the foreign-product check at
`netlify/functions/stripe-webhook.mjs:332-334`, and *before* line 336's
`// Sessions predating the metadata stamp are Paper Review's by
definition:` comment that starts the Paper Review-specific flow), insert:

```js
  if (rawProduct === "digest-monthly" || rawProduct === "digest-annual") {
    const store = getStore("subscribers");
    const digestEmail = email.toLowerCase().trim();
    if (digestEmail) {
      const existing = await store.get(digestEmail);
      const record = existing ? JSON.parse(existing) : {
        email: digestEmail,
        subscribedAt: new Date().toISOString(),
      };
      record.tier = "paid";
      record.stripe_customer_id = session.customer;
      record.stripe_subscription_id = session.subscription;
      await store.set(digestEmail, JSON.stringify(record));
    }
    return jsonResponse(200, { status: "digest_subscribed", product: rawProduct, email: digestEmail });
  }

```

This reuses `email` exactly as already extracted at line 311-314
(`(session.customer_details && session.customer_details.email) ||
session.customer_email || ""`) and `rawProduct` exactly as extracted at
line 318 — no new extraction logic, matching this file's existing `&&`-chain
style rather than introducing `?.` optional chaining, which nothing else in
this file uses. The early `return` is required: without it, execution falls
through into line 338's `const product = rawProduct || "paper-review-standard"`
and the Paper Review Modal-forwarding flow, which would wrongly try to
register a Paper Review redemption token for a digest subscription.

- [ ] **Step 4: Add the `customer.subscription.deleted` handler**

`netlify/functions/stripe-webhook.mjs:296-300` currently reads:

```js
  // We only care about a completed Checkout session for v1.
  if (event.type !== "checkout.session.completed") {
    // 200-OK every other event type so Stripe doesn't retry indefinitely.
    return jsonResponse(200, { status: "ignored", type: event.type });
  }
```

This single-type gate becomes a small dispatch. Replace it with:

```js
  if (event.type === "customer.subscription.deleted") {
    const store = getStore("subscribers");
    const subscriptionId = event.data && event.data.object && event.data.object.id;
    const { blobs } = await store.list();
    for (const b of blobs) {
      const raw = await store.get(b.key);
      if (!raw) continue;
      const record = JSON.parse(raw);
      if (record.stripe_subscription_id === subscriptionId) {
        record.tier = "free";
        await store.set(b.key, JSON.stringify(record));
        break;
      }
    }
    return jsonResponse(200, { status: "processed", type: event.type });
  }

  // We only care about a completed Checkout session beyond this point.
  if (event.type !== "checkout.session.completed") {
    // 200-OK every other event type so Stripe doesn't retry indefinitely.
    return jsonResponse(200, { status: "ignored", type: event.type });
  }
```

The list-and-scan approach is O(subscriber count) per cancellation —
acceptable at current and near-future subscriber volumes (this whole
product doesn't have a single subscriber yet); revisit only if it ever
becomes slow enough to matter.

- [ ] **Step 5: Add the Stripe Dashboard event subscription (manual, not code)**

In the Stripe Dashboard, under the existing webhook endpoint's
configuration, add `customer.subscription.deleted` to its subscribed
events — it's very likely currently configured for only
`checkout.session.completed`, matching what the code handled before this
task.

- [ ] **Step 6: Verify with Stripe's CLI or test-mode dashboard**

```bash
stripe trigger customer.subscription.deleted
```

(requires the Stripe CLI logged into the account; if unavailable, trigger
it by canceling a real test-mode subscription in the Dashboard instead).
Check the function logs (`netlify logs --source functions --function
stripe-webhook --since 5m`) for `{"status":"processed",...}`, not an error.

- [ ] **Step 7: Commit**

```bash
git add netlify/functions/stripe-webhook.mjs
git commit -m "stripe-webhook: handle digest subscription checkout + cancellation"
```

---

### Task 5: Persist a JSON snapshot of each day's digest

Today, `publish()` only writes rendered HTML — nothing lets a later run
reconstruct a past day's `DigestData` to re-render its email. The delayed
free-tier send (Task 8) needs exactly that.

**Files:**
- Modify: `backend/digest/publisher.py`
- Test: `backend/tests/test_digest_publisher.py`

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/test_digest_publisher.py` (check the file's existing
imports/fixtures first and match its style — it already tests this same
module):

```python
def test_digest_to_dict_round_trips_through_json():
    import json
    import datetime
    from digest.curator import DigestData, DigestItem
    from digest.publisher import digest_to_dict, digest_from_dict

    original = DigestData(
        date=datetime.date(2026, 9, 17),
        number=42,
        intro="Test intro.",
        sections={"ai_tech": [
            DigestItem(title="A paper", url="https://example.com/a",
                       source_name="Example", category="ai_tech",
                       editorial_note="A note."),
        ]},
        sources_reviewed=100,
        items_selected=1,
    )
    round_tripped = digest_from_dict(json.loads(json.dumps(digest_to_dict(original))))
    assert round_tripped.date == original.date
    assert round_tripped.number == original.number
    assert round_tripped.intro == original.intro
    assert round_tripped.sources_reviewed == original.sources_reviewed
    assert round_tripped.items_selected == original.items_selected
    assert round_tripped.sections["ai_tech"][0].title == "A paper"
    assert round_tripped.sections["ai_tech"][0].url == "https://example.com/a"
```

- [ ] **Step 2: Run it to verify it fails**

```bash
cd backend && python3 -m pytest tests/test_digest_publisher.py::test_digest_to_dict_round_trips_through_json -v
```

Expected: `ImportError: cannot import name 'digest_to_dict'` (the functions
don't exist yet).

- [ ] **Step 3: Add `digest_to_dict`/`digest_from_dict` to `publisher.py`**

Add near the top of `backend/digest/publisher.py`, after the existing
imports (check what's already imported — `dataclasses` and `datetime` may
or may not be, add only what's missing):

```python
import dataclasses


def digest_to_dict(digest: DigestData) -> dict:
    """Plain-dict form of a DigestData, safe for json.dumps. The inverse of
    digest_from_dict. Exists so a day's digest can be persisted alongside
    its rendered HTML and reloaded later -- publish() only ever wrote HTML
    before this, which meant nothing could reconstruct a past day's digest
    to re-render its email (needed for the delayed free-tier send)."""
    d = dataclasses.asdict(digest)
    d["date"] = digest.date.isoformat()
    return d


def digest_from_dict(d: dict) -> DigestData:
    """Inverse of digest_to_dict."""
    sections = {
        section: [DigestItem(**item) for item in items]
        for section, items in d["sections"].items()
    }
    return DigestData(
        date=datetime.date.fromisoformat(d["date"]),
        number=d["number"],
        intro=d["intro"],
        sections=sections,
        sources_reviewed=d["sources_reviewed"],
        items_selected=d["items_selected"],
    )
```

`DigestData`/`DigestItem` are already imported into `publisher.py` from
`curator.py` (confirm the existing import line and reuse it — don't
duplicate the import).

- [ ] **Step 4: Run the test again to verify it passes**

```bash
cd backend && python3 -m pytest tests/test_digest_publisher.py::test_digest_to_dict_round_trips_through_json -v
```

Expected: `PASSED`.

- [ ] **Step 5: Write the GitHub read/write helpers for the JSON snapshot**

Add near `github_write_digest` (reuse `_github_put_file`/`_github_get_file`
exactly as that function does — same pattern, different path/content):

```python
def _digest_json_path(iso: str) -> str:
    return f"{DIGEST_DIR}/data/{iso}.json"


async def github_write_digest_json(client, digest: DigestData, token: str) -> None:
    """Write a raw JSON snapshot alongside the rendered HTML -- see
    digest_to_dict for why this exists."""
    import json
    iso = digest.date.isoformat()
    path = _digest_json_path(iso)
    _, existing_sha = await _github_get_file(client, path, token)
    content = json.dumps(digest_to_dict(digest), indent=2)
    await _github_put_file(client, path, content, f"digest: JSON snapshot {iso}", token, sha=existing_sha)


async def github_read_digest_json(client, iso: str, token: str) -> DigestData | None:
    """Reload a past day's digest from its JSON snapshot, or None if that
    day has no snapshot (e.g. predates this feature, or genuinely never
    published)."""
    import json
    content, _sha = await _github_get_file(client, _digest_json_path(iso), token)
    if content is None:
        return None
    return digest_from_dict(json.loads(content))
```

`DIGEST_DIR` is already a module-level constant in `publisher.py` (used by
`github_write_digest`) — reuse it, don't redefine it.

- [ ] **Step 6: Wire the snapshot write into `publish()`**

In `publish()`, right after the existing `await github_write_digest(client,
html_content, digest, github_token)` line, add:

```python
        await github_write_digest_json(client, digest, github_token)
```

- [ ] **Step 7: Commit**

```bash
cd backend && python3 -m pytest tests/test_digest_publisher.py -v
git add backend/digest/publisher.py backend/tests/test_digest_publisher.py
git commit -m "digest: persist a JSON snapshot of each day, for later re-rendering"
```

---

### Task 6: Self-hosted Buy Me a Coffee badge

**Files:**
- Create: `site/assets/bmac-badge.svg`

- [ ] **Step 1: Fetch the official badge image once, save it locally**

This is a one-time asset acquisition, not something the running site ever
fetches live — after this step the file is a normal committed repo asset,
consistent with the project's self-hosting rule.

```bash
curl -s -o "/Volumes/Extreme SSD/Purplelink LLC/site/assets/bmac-badge.svg" \
  "https://cdn.buymeacoffee.com/buttons/v2/default-yellow.svg"
```

If that exact URL 404s (Buy Me a Coffee's asset paths do change), get the
current one from https://www.buymeacoffee.com/brand — Settings → Widgets/
Button in your own BMAC dashboard also provides a direct badge-image link.
Confirm the downloaded file is actually SVG/PNG content, not an HTML error
page, before committing:

```bash
file "/Volumes/Extreme SSD/Purplelink LLC/site/assets/bmac-badge.svg"
```

Expected: `SVG Scalable Vector Graphics image` (or similar) — not `HTML
document`.

- [ ] **Step 2: Commit**

```bash
git add site/assets/bmac-badge.svg
git commit -m "assets: self-host the Buy Me a Coffee badge"
```

---

### Task 7: Tier-aware footers

**Files:**
- Modify: `backend/digest/publisher.py` (`render_html`, `render_email_html`)
- Test: `backend/tests/test_digest_publisher.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_render_email_html_paid_tier_has_no_upgrade_cta():
    import datetime
    from digest.curator import DigestData
    from digest.publisher import render_email_html

    digest = DigestData(date=datetime.date(2026, 9, 17), number=1, intro="",
                         sections={}, sources_reviewed=0, items_selected=0)
    html = render_email_html(digest, unsubscribe_url="https://x", tier="paid")
    assert "5/mo" not in html
    assert "buymeacoffee" not in html
    assert "thanks for subscribing" in html.lower()


def test_render_email_html_free_tier_has_upgrade_cta_and_bmac():
    import datetime
    from digest.curator import DigestData
    from digest.publisher import render_email_html

    digest = DigestData(date=datetime.date(2026, 9, 17), number=1, intro="",
                         sections={}, sources_reviewed=0, items_selected=0)
    html = render_email_html(digest, unsubscribe_url="https://x", tier="free")
    assert "5/mo" in html or "$5" in html
    assert "buymeacoffee.com/bampel" in html


def test_render_email_html_legacy_tier_has_no_upgrade_cta():
    import datetime
    from digest.curator import DigestData
    from digest.publisher import render_email_html

    digest = DigestData(date=datetime.date(2026, 9, 17), number=1, intro="",
                         sections={}, sources_reviewed=0, items_selected=0)
    html = render_email_html(digest, unsubscribe_url="https://x", tier="legacy")
    assert "5/mo" not in html
```

- [ ] **Step 2: Run to verify they fail**

```bash
cd backend && python3 -m pytest tests/test_digest_publisher.py -k "tier" -v
```

Expected: `TypeError: render_email_html() got an unexpected keyword argument 'tier'`.

- [ ] **Step 3: Update `render_email_html`'s signature and footer**

Replace the function in `backend/digest/publisher.py`:

```python
def render_email_html(digest: DigestData, unsubscribe_url: str = "", tier: str = "free") -> str:
    """Render email-safe HTML: no nav/footer, inline-friendly.

    tier controls the footer: "paid" and "legacy" subscribers already have
    what the upgrade offer is selling (same-day delivery), so showing them
    a $5/mo pitch for something they already have reads as not knowing who
    they are. Only "free" (the new, 2-day-delayed tier) sees the upgrade
    CTA and the Buy Me a Coffee badge.
    """
    date_str = _fmt_date(digest.date)
    title = f"Purplelink Daily Digest #{digest.number} — {date_str}"
    sections_html = _render_sections_html(digest)
    unsub_line = (
        f'<p style="font-size:12px;color:#888;margin-top:24px;">'
        f'You\'re receiving this because you subscribed at purplelink.llc. '
        f'<a href="{html.escape(unsubscribe_url, quote=True)}" style="color:#888;">Unsubscribe</a>'
        f'</p>'
    ) if unsubscribe_url else ""

    if tier == "free":
        tier_footer = f"""
  <div style="margin:24px 0;padding:16px;background:#f7f7f7;border-radius:8px;">
    <p style="margin:0 0 8px;font-size:14px;">
      Get this same-day, every morning, for $5/mo or $40/yr &mdash;
      <a href="https://purplelink.llc/blog/digest/#subscribe">upgrade</a>.
    </p>
    <a href="https://buymeacoffee.com/bampel" target="_blank" rel="noopener">
      <img src="https://purplelink.llc/assets/bmac-badge.svg" alt="Buy Me a Coffee" style="height:32px;">
    </a>
  </div>"""
    else:
        tier_footer = """
  <p style="margin:24px 0;font-size:13px;color:#888;">Thanks for subscribing.</p>"""

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
</head>
<body style="font-family:system-ui,sans-serif;max-width:600px;margin:0 auto;padding:24px 16px;color:#1a1a1a;">
  <h1 style="font-size:22px;margin-bottom:8px;">{title}</h1>
  <p style="color:#555;margin-bottom:24px;">{html.escape(digest.intro)}</p>
{sections_html}
  <hr style="border:none;border-top:1px solid #e0e0e0;margin:24px 0;">
  <p style="font-size:13px;color:#555;">
    <a href="https://purplelink.llc/blog/digest/{digest.date.isoformat()}.html">Read on the web</a>
    &middot;
    <a href="https://purplelink.llc/blog/digest/">All issues</a>
  </p>
  {tier_footer}
  {unsub_line}
</body>
</html>"""
```

Note: an email `<img src>` pointing at `purplelink.llc/assets/bmac-badge.svg`
requires that asset to be reachable at that exact public URL once deployed
(Task 6 saved it under `site/assets/`, which the existing site build already
publishes at `/assets/...` — no new deploy config needed, same as every
other file already in `site/assets/`).

- [ ] **Step 4: Run the tests again**

```bash
cd backend && python3 -m pytest tests/test_digest_publisher.py -k "tier" -v
```

Expected: all 3 `PASSED`.

- [ ] **Step 5: Add the same footer block to the web page (`render_html`)**

In `render_html`, find the existing footer block:

```python
    <div class="post-footer digest-footer">
      <p>Get this in your inbox. <a href="/blog/digest/">Subscribe to Purplelink Daily Digest</a>.</p>
      <a class="back-link" href="/blog/digest/">← All issues</a>
    </div>
```

Replace with:

```python
    <div class="post-footer digest-footer">
      <p>Get this in your inbox, same-day, for $5/mo or $40/yr. <a href="/blog/digest/#subscribe">Subscribe</a>,
      or get it free with a 2-day delay via the <a href="/blog/digest/#subscribe">free tier</a>.</p>
      <a href="https://buymeacoffee.com/bampel" target="_blank" rel="noopener">
        <img src="/assets/bmac-badge.svg" alt="Buy Me a Coffee" width="150" height="32" loading="lazy">
      </a>
      <a class="back-link" href="/blog/digest/">← All issues</a>
    </div>
```

Every web visitor is, by definition, not already a same-day paying
subscriber reading through a link only they'd have — so the web page
always shows both, unlike the tiered email footer.

- [ ] **Step 6: Commit**

```bash
cd backend && python3 -m pytest tests/test_digest_publisher.py -v
git add backend/digest/publisher.py backend/tests/test_digest_publisher.py
git commit -m "digest: tier-aware footers (paid CTA + BMAC badge on free/web only)"
```

---

### Task 8: Two-send mailer logic

**Files:**
- Modify: `backend/digest/mailer.py`
- Modify: `backend/digest/app.py` (call-site update)
- Test: create `backend/tests/test_digest_mailer.py`

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_digest_mailer.py
import sys
from pathlib import Path
BACKEND = Path(__file__).resolve().parent.parent
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

import asyncio
import datetime

from digest.mailer import split_by_send_group


def test_split_by_send_group_paid_and_legacy_get_same_day():
    subscribers = [
        {"email": "a@x.com", "tier": "paid"},
        {"email": "b@x.com", "tier": "legacy"},
        {"email": "c@x.com", "tier": "free", "last_sent_slug": None},
    ]
    same_day, delayed = split_by_send_group(subscribers, delayed_slug="2026-09-17")
    assert {s["email"] for s in same_day} == {"a@x.com", "b@x.com"}
    assert {s["email"] for s in delayed} == {"c@x.com"}


def test_split_by_send_group_skips_free_subscriber_already_caught_up():
    subscribers = [
        {"email": "c@x.com", "tier": "free", "last_sent_slug": "2026-09-17"},
    ]
    same_day, delayed = split_by_send_group(subscribers, delayed_slug="2026-09-17")
    assert same_day == []
    assert delayed == []


def test_split_by_send_group_treats_missing_tier_as_legacy():
    # A record that predates this feature and hasn't been touched by the
    # subscribe.mjs backfill (that backfill only fires on re-submission --
    # see Task 2, Step 2). Must not be silently dropped from every send.
    subscribers = [{"email": "old@x.com"}]
    same_day, delayed = split_by_send_group(subscribers, delayed_slug="2026-09-17")
    assert {s["email"] for s in same_day} == {"old@x.com"}
```

- [ ] **Step 2: Run to verify failure**

```bash
cd backend && python3 -m pytest tests/test_digest_mailer.py -v
```

Expected: `ImportError: cannot import name 'split_by_send_group'`.

- [ ] **Step 3: Implement `split_by_send_group` in `mailer.py`**

Add to `backend/digest/mailer.py`:

```python
def split_by_send_group(subscribers: list[dict], delayed_slug: str) -> tuple[list[dict], list[dict]]:
    """Split subscribers into (same_day, delayed) groups.

    paid/legacy -> same_day, always. A missing `tier` field is treated as
    legacy (same-day) -- not free -- since subscribe.mjs's backfill (Task 2)
    only runs when someone re-submits the signup form, so a record can
    reach this function with no tier field at all. Treating that as "free"
    would silently start delaying delivery to people who've had same-day
    delivery all along; treating it as legacy preserves what they already
    have, matching this whole feature's grandfathering principle.

    free -> delayed, but only if this subscriber hasn't already received
    the specific issue being delayed-sent today (last_sent_slug check) --
    the idempotency guard that lets a missed cron run self-heal on the next
    run instead of double-sending or permanently skipping someone.
    """
    same_day, delayed = [], []
    for sub in subscribers:
        tier = sub.get("tier") or "legacy"
        if tier in ("paid", "legacy"):
            same_day.append(sub)
        elif tier == "free":
            if sub.get("last_sent_slug") != delayed_slug:
                delayed.append(sub)
    return same_day, delayed
```

- [ ] **Step 4: Run the tests again**

```bash
cd backend && python3 -m pytest tests/test_digest_mailer.py -v
```

Expected: all 3 `PASSED`.

- [ ] **Step 5: Rewrite `_get_subscribers` and `mail_digest` for the new response shape and two-send flow**

Replace `_get_subscribers`:

```python
async def _get_subscribers(client: httpx.AsyncClient, subscribe_secret: str) -> list[dict]:
    try:
        resp = await client.get(
            SUBSCRIBERS_URL,
            headers={"Authorization": f"Bearer {subscribe_secret}"},
            timeout=10.0,
        )
        resp.raise_for_status()
        return resp.json().get("subscribers", [])
    except Exception as exc:
        logger.warning("mailer: get_subscribers failed: %s", exc)
        return []
```

Add a new helper to write `last_sent_slug` back after a delayed send:

```python
async def _mark_sent(client: httpx.AsyncClient, email: str, slug: str, subscribe_secret: str) -> None:
    try:
        resp = await client.post(
            f"{SITE_URL}/.netlify/functions/subscriber-update",
            headers={"Authorization": f"Bearer {subscribe_secret}", "Content-Type": "application/json"},
            json={"email": email, "fields": {"last_sent_slug": slug}},
            timeout=10.0,
        )
        resp.raise_for_status()
    except Exception as exc:
        logger.warning("mailer: mark_sent failed for %s: %s", email, exc)
```

Replace `mail_digest`:

```python
async def mail_digest(
    digest,
    render_email_html: Callable,
    subscribe_secret: str,
    resend_key: str,
    delayed_digest=None,
    delayed_slug: str = "",
) -> int:
    """Fetch subscriber list, split by send group, email each. Returns
    total count sent across both groups.

    delayed_digest/delayed_slug: the digest from DELAY_DAYS ago (see
    app.py), already reloaded from its JSON snapshot -- None if that day
    has no snapshot (predates this feature), in which case the delayed
    group is simply skipped this run rather than erroring; those
    subscribers catch up automatically once a snapshotted day reaches the
    right age.
    """
    from digest.publisher import _fmt_date

    async with httpx.AsyncClient() as client:
        subscribers = await _get_subscribers(client, subscribe_secret)
        if not subscribers:
            logger.info("mailer: no subscribers, skipping email send")
            return 0

        same_day, delayed = split_by_send_group(subscribers, delayed_slug)
        sent = 0

        subject = f"Purplelink Daily Digest #{digest.number} — {_fmt_date(digest.date)}"
        for sub in same_day:
            email = sub["email"]
            tier = sub.get("tier") or "legacy"
            unsub_url = _unsubscribe_url(email, subscribe_secret)
            html = render_email_html(digest, unsubscribe_url=unsub_url, tier=tier)
            await _send_one(client, email, subject, html, resend_key)
            sent += 1

        if delayed_digest is not None and delayed:
            delayed_subject = f"Purplelink Daily Digest #{delayed_digest.number} — {_fmt_date(delayed_digest.date)}"
            for sub in delayed:
                email = sub["email"]
                unsub_url = _unsubscribe_url(email, subscribe_secret)
                html = render_email_html(delayed_digest, unsubscribe_url=unsub_url, tier="free")
                await _send_one(client, email, delayed_subject, html, resend_key)
                await _mark_sent(client, email, delayed_slug, subscribe_secret)
                sent += 1
        elif delayed:
            logger.info("mailer: %d free-tier subscriber(s) behind, but no snapshot for %s yet", len(delayed), delayed_slug)

        logger.info("mailer: done, sent=%d (same_day=%d, delayed=%d)", sent, len(same_day), len(delayed))
        return sent
```

- [ ] **Step 6: Update `app.py`'s call site**

In `backend/digest/app.py`, find:

```python
    if subscribe_secret and resend_key:
        from digest.mailer import mail_digest
        from digest.publisher import render_email_html
        sent = await mail_digest(digest, render_email_html, subscribe_secret, resend_key)
        logger.info("digest: emailed %d subscribers", sent)
```

Replace with:

```python
    if subscribe_secret and resend_key:
        from digest.mailer import mail_digest
        from digest.publisher import render_email_html, github_read_digest_json
        import datetime as _dt

        delayed_date = digest.date - _dt.timedelta(days=2)
        delayed_slug = delayed_date.isoformat()
        try:
            delayed_digest = await github_read_digest_json(client, delayed_slug, github_token)
        except Exception as exc:
            logger.warning("digest: could not load delayed snapshot for %s: %s", delayed_slug, exc)
            delayed_digest = None

        sent = await mail_digest(
            digest, render_email_html, subscribe_secret, resend_key,
            delayed_digest=delayed_digest, delayed_slug=delayed_slug,
        )
        logger.info("digest: emailed %d subscribers", sent)
```

This reuses the same `client` (`httpx.AsyncClient`) already open in
`run_daily_digest`'s outer `async with` block — check that `client` is
still in scope at this point in the function (it is, per the existing code
structure read in Task 5/6's research) rather than opening a second one.

- [ ] **Step 7: Commit**

```bash
cd backend && python3 -m pytest tests/test_digest_mailer.py tests/test_digest_publisher.py -v
git add backend/digest/mailer.py backend/digest/app.py backend/tests/test_digest_mailer.py
git commit -m "digest: two-send mailer (same-day paid/legacy, delayed free-tier)"
```

- [ ] **Step 8: Live verification before trusting this against real subscribers**

Run the existing dry-run entrypoint locally to confirm nothing crashes with
real (test-mode) credentials:

```bash
cd backend && DRY_RUN=1 python3 digest/app.py
```

Expected: the existing dry-run preview output, no traceback. This does not
exercise the mailer (dry run returns before that point per the existing
code) — a true end-to-end mailer test requires a real Modal run with a
throwaway test subscriber in the Blobs store at each tier, checking their
inbox. Do this once, manually, before the first real scheduled run after
deploying this task.

---

### Task 9: Stripe Customer Portal (self-serve account management)

**Files:**
- Create: `netlify/functions/subscription-portal.mjs`
- Modify: `backend/digest/publisher.py` (paid-tier footer gets a manage link)

- [ ] **Step 1: Write the portal-session endpoint**

```js
/**
 * GET /.netlify/functions/subscription-portal?email=...&token=...
 *
 * Redirects a paying digest subscriber to Stripe's hosted Customer
 * Portal, where they can cancel or update their payment method
 * themselves -- no custom account UI needed. `token` is an HMAC of the
 * email, same signing pattern unsubscribe.mjs already uses, so this link
 * can be embedded directly in the paid-tier email footer without a
 * separate login step.
 *
 * Required env vars: SUBSCRIBE_SECRET, STRIPE_SECRET_KEY
 */
import { getStore } from "@netlify/blobs"
import { createHmac, timingSafeEqual } from "node:crypto"

const STRIPE_API = "https://api.stripe.com/v1"

function verifyToken(email, token, secret) {
  const expected = createHmac("sha256", secret).update(email).digest("hex")
  const a = Buffer.from(token, "utf8")
  const b = Buffer.from(expected, "utf8")
  return a.length === b.length && timingSafeEqual(a, b)
}

export default async function handler(request) {
  const url = new URL(request.url)
  const email = (url.searchParams.get("email") || "").toLowerCase().trim()
  const token = url.searchParams.get("token") || ""

  const secret = process.env.SUBSCRIBE_SECRET
  const stripeKey = process.env.STRIPE_SECRET_KEY
  if (!secret || !stripeKey) {
    return new Response("Server misconfigured", { status: 500 })
  }
  if (!email || !token || !verifyToken(email, token, secret)) {
    return new Response("Invalid or expired link", { status: 403 })
  }

  const store = getStore("subscribers")
  const raw = await store.get(email)
  if (!raw) {
    return new Response("No subscription found", { status: 404 })
  }
  const record = JSON.parse(raw)
  if (!record.stripe_customer_id) {
    return new Response("No billing account on file", { status: 404 })
  }

  const resp = await fetch(`${STRIPE_API}/billing_portal/sessions`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${stripeKey}`,
      "Content-Type": "application/x-www-form-urlencoded",
    },
    body: new URLSearchParams({
      customer: record.stripe_customer_id,
      return_url: "https://purplelink.llc/blog/digest/",
    }),
  })
  if (!resp.ok) {
    const detail = await resp.text().catch(() => "")
    console.error("subscription-portal: stripe error", resp.status, detail)
    return new Response("Could not open billing portal", { status: 502 })
  }
  const session = await resp.json()
  return Response.redirect(session.url, 303)
}
```

- [ ] **Step 2: Add a manage-subscription link, built the same way `_unsubscribe_url` already is**

`render_email_html` (in `publisher.py`) only ever receives strings the
*caller* builds — it has no access to the shared secret and never has
(the unsubscribe link is built by `mailer.py` and passed in as a plain
URL). The manage-subscription link follows the identical pattern rather
than plumbing a secret into `publisher.py` for the first time.

In `backend/digest/mailer.py`, add a new helper right after the existing
`_unsubscribe_url`:

```python
def _manage_subscription_url(email: str, secret: str) -> str:
    token = hmac.new(secret.encode(), email.encode(), hashlib.sha256).hexdigest()
    return (
        f"{SITE_URL}/.netlify/functions/subscription-portal"
        f"?email={quote(email)}&token={token}"
    )
```

In `backend/digest/publisher.py`, change `render_email_html`'s signature
(Task 7 added `tier`; this adds `manage_url` alongside it) and its
`tier_footer` logic to its final form:

```python
def render_email_html(digest: DigestData, unsubscribe_url: str = "", tier: str = "free", manage_url: str = "") -> str:
    """Render email-safe HTML: no nav/footer, inline-friendly.

    tier controls the footer: "paid" and "legacy" subscribers already have
    what the upgrade offer is selling (same-day delivery), so showing them
    a $5/mo pitch for something they already have reads as not knowing who
    they are. Only "free" (the new, 2-day-delayed tier) sees the upgrade
    CTA and the Buy Me a Coffee badge. manage_url is only ever non-empty
    for "paid" (legacy subscribers have no Stripe customer to manage).
    """
    date_str = _fmt_date(digest.date)
    title = f"Purplelink Daily Digest #{digest.number} — {date_str}"
    sections_html = _render_sections_html(digest)
    unsub_line = (
        f'<p style="font-size:12px;color:#888;margin-top:24px;">'
        f'You\'re receiving this because you subscribed at purplelink.llc. '
        f'<a href="{html.escape(unsubscribe_url, quote=True)}" style="color:#888;">Unsubscribe</a>'
        f'</p>'
    ) if unsubscribe_url else ""

    if tier == "free":
        tier_footer = f"""
  <div style="margin:24px 0;padding:16px;background:#f7f7f7;border-radius:8px;">
    <p style="margin:0 0 8px;font-size:14px;">
      Get this same-day, every morning, for $5/mo or $40/yr &mdash;
      <a href="https://purplelink.llc/blog/digest/#subscribe">upgrade</a>.
    </p>
    <a href="https://buymeacoffee.com/bampel" target="_blank" rel="noopener">
      <img src="https://purplelink.llc/assets/bmac-badge.svg" alt="Buy Me a Coffee" style="height:32px;">
    </a>
  </div>"""
    elif tier == "paid":
        manage_line = (
            f' <a href="{html.escape(manage_url, quote=True)}" style="color:#888;">Manage subscription</a>'
        ) if manage_url else ""
        tier_footer = f"""
  <p style="margin:24px 0;font-size:13px;color:#888;">Thanks for subscribing.{manage_line}</p>"""
    else:
        tier_footer = """
  <p style="margin:24px 0;font-size:13px;color:#888;">Thanks for subscribing.</p>"""

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
</head>
<body style="font-family:system-ui,sans-serif;max-width:600px;margin:0 auto;padding:24px 16px;color:#1a1a1a;">
  <h1 style="font-size:22px;margin-bottom:8px;">{title}</h1>
  <p style="color:#555;margin-bottom:24px;">{html.escape(digest.intro)}</p>
{sections_html}
  <hr style="border:none;border-top:1px solid #e0e0e0;margin:24px 0;">
  <p style="font-size:13px;color:#555;">
    <a href="https://purplelink.llc/blog/digest/{digest.date.isoformat()}.html">Read on the web</a>
    &middot;
    <a href="https://purplelink.llc/blog/digest/">All issues</a>
  </p>
  {tier_footer}
  {unsub_line}
</body>
</html>"""
```

In `backend/digest/mailer.py`, `mail_digest`'s `same_day` loop (added in
Task 8, Step 5) becomes, in its final form:

```python
        for sub in same_day:
            email = sub["email"]
            tier = sub.get("tier") or "legacy"
            unsub_url = _unsubscribe_url(email, subscribe_secret)
            manage_url = _manage_subscription_url(email, subscribe_secret) if tier == "paid" else ""
            html = render_email_html(digest, unsubscribe_url=unsub_url, tier=tier, manage_url=manage_url)
            await _send_one(client, email, subject, html, resend_key)
            sent += 1
```

This is the same loop Task 8 wrote, with one added line (`manage_url = ...`)
and `manage_url=manage_url` added to the `render_email_html` call —
replace Task 8's version of this loop with this one; nothing else in
`mail_digest` changes.

- [ ] **Step 3: Update the Task 7 tests to match the new signature**

The three tests added in Task 7 call `render_email_html(digest,
unsubscribe_url="https://x", tier=...)` without `manage_url` — since it
defaults to `""`, they still pass unchanged. Add one more:

```python
def test_render_email_html_paid_tier_shows_manage_link_when_provided():
    import datetime
    from digest.curator import DigestData
    from digest.publisher import render_email_html

    digest = DigestData(date=datetime.date(2026, 9, 17), number=1, intro="",
                         sections={}, sources_reviewed=0, items_selected=0)
    html = render_email_html(digest, unsubscribe_url="https://x", tier="paid",
                              manage_url="https://purplelink.llc/.netlify/functions/subscription-portal?email=a@b.com&token=t")
    assert "Manage subscription" in html
    assert "subscription-portal" in html
```

- [ ] **Step 4: Run all digest tests**

```bash
cd backend && python3 -m pytest tests/test_digest_publisher.py tests/test_digest_mailer.py -v
```

Expected: all `PASSED`.

- [ ] **Step 5: Live verification**

```bash
curl -sI "https://purplelink.llc/.netlify/functions/subscription-portal?email=nonexistent@example.com&token=badtoken"
```

Expected: `HTTP/2 403` (bad token) — confirms the function deploys and the
auth check runs, without needing a real subscriber yet.

- [ ] **Step 6: Commit**

```bash
git add netlify/functions/subscription-portal.mjs backend/digest/mailer.py backend/digest/publisher.py backend/tests/test_digest_publisher.py
git commit -m "digest: Stripe Customer Portal for self-serve billing management"
```

---

### Task 10: Full pipeline dry run

**Files:** none new — verification only.

- [ ] **Step 1: Run the complete test suite for everything this plan touched**

```bash
cd backend && python3 -m pytest tests/test_digest_publisher.py tests/test_digest_mailer.py tests/test_digest_curator.py tests/test_digest_harvester.py -v
```

Expected: all `PASSED`, nothing broken in the modules this plan didn't
directly change but that import from the ones it did.

- [ ] **Step 2: Dry-run the full Modal entrypoint**

```bash
cd backend && DRY_RUN=1 python3 digest/app.py
```

Expected: the existing preview output, no traceback — confirms the new
imports (`github_read_digest_json`, the new `mail_digest` signature) don't
break the module-level import graph even though dry-run exits before
calling `mail_digest`.

- [ ] **Step 3: Deploy the Modal app**

```bash
cd backend && modal deploy digest/app.py
```

- [ ] **Step 4: Deploy the site (Netlify functions)**

```bash
cd "/Volumes/Extreme SSD/Purplelink LLC" && bash scripts/deploy.sh
```

- [ ] **Step 5: One real end-to-end check before the next scheduled run**

Create one throwaway test subscriber at each tier directly in the
Blobs store (or via the live signup form + a manual Stripe test-mode
checkout for the paid one), then manually trigger the Modal function once
and confirm all three receive the correct version of the email (same-day
paid with a manage link, same-day legacy with a plain thanks, and —
if a snapshot exists from 2 days ago — the delayed free-tier version with
the upgrade CTA and BMAC badge). Clean up the test subscribers afterward
(delete their Blobs entries) so they don't pollute the real subscriber
count.
