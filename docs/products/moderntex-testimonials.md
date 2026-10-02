# ModernTex buyer feedback: process

Sent 2026-10-02 (nine individual emails, subject "Two questions about ModernTex") to the nine
paying customers from the first month. New buyers get the same ask as one sentence at the end
of the purchase email (netlify/functions/stripe-webhook.mjs). Replies arrive at
ben@purplelink.llc; the daily update lists them under "Needs a reply".

## Rules

- Nothing is published without a reply that grants permission for that sentence.
- Attribute by first name and field only, as the email promised. No surname, employer,
  email or photo.
- Quote exactly. Trim only with the buyer's agreement. Never invent, merge or "clean up"
  a quote into something the buyer did not say.
- No incentive was offered, so there is nothing to disclose beyond "ModernTex buyer".
- If a reply says something negative or a bug, it goes to the product list, not the page.
- Do not add aggregateRating, star counts or review schema; two or three quotes are
  testimonials, not a rating.

## Reply to a buyer who answers but does not mention permission

```
Thank you, this is helpful. May I quote one sentence from it on the ModernTex page, with your first name and field only? If you would rather not, that is fine.

Ben
```

## Page block (fill only from approved quotes)

Place after the "At a glance" section on site/moderntex/index.html. The site's CSP forbids
inline styles, so reuse existing classes.

```html
<section class="catalog-section" aria-labelledby="buyers-h">
  <div class="catalog-section-head">
    <p class="eyebrow">From early buyers</p>
    <h2 id="buyers-h">What people use it for</h2>
  </div>
  <figure class="buyer-quote">
    <blockquote><p>QUOTE EXACTLY AS APPROVED</p></blockquote>
    <figcaption>FIRST NAME, FIELD. ModernTex buyer.</figcaption>
  </figure>
</section>
```

The site has no quote component yet (checked 2026-10-02: no `blockquote` or `quote` rule in
site/styles.css). When the first approved quote lands, add a small `.buyer-quote` rule to
site/styles.css using the existing tokens (surface background, Fraunces for the quote,
muted small-caps-free caption), then run scripts/fingerprint_assets.py. Dark is the default
theme; gate any dark-only values as `:where(:root:not([data-theme="light"]))`.
