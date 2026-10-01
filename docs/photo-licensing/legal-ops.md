# Photo Licensing — Legal & Operational Foundations

Researched 2026-08-04. Purplelink LLC (GA single-member LLC, disregarded entity).
The LLC's purpose clause ("any lawful business activity") already covers this — no
operating-agreement amendment needed.

## Copyright registration

- **Register before uploading.** Statutory damages ($750–$30k/work, $150k willful)
  and attorney's fees require registration *before* infringement or within 3 months
  of first publication (17 U.S.C. §412). Uploading to a stock agency counts as
  publication. Unregistered = actual damages only, i.e. a few dollars per stock photo.
- **GRUPH** (Group of Unpublished Photographs): $55 per application, up to **750
  photos**, online via eCO, same author+claimant, sequentially numbered title list.
  This is the tool. One filing per batch before its first upload.
- If photos slip out unregistered: **GRPPH** (published group, also $55/750) within
  90 days of first upload, grouped by calendar year.
- Each photo in a group registration counts as a **separate work** for damages.
- Budget: ~$55/batch, ~$220–660/yr at a monthly-to-quarterly cadence.

## License types (what we're selling)

- **Royalty-free (RF)** is the market default; rights-managed is dead outside niche
  archives (Getty retired creative RM in 2020).
- **Editorial-only**: no releases needed, but usable only in news/descriptive
  contexts; must carry accurate caption/date. Lower ceiling, zero release burden.
- **Extended licenses** (merch, >500k print runs, templates) pay meaningfully more
  per sale — enable wherever offered.
- Non-exclusive contributor agreements grant platforms a sublicensable right to
  license and market; **we retain copyright** and the right to sell the same image
  everywhere else. Termination doesn't claw back already-sold licenses, and partner-
  network takedowns lag months.

## Releases

- **Model release** for any recognizable person in commercial content (face,
  tattoo, silhouette, context all count). Self-portraits need a self-release.
  Minors need guardian signature. Getty requires witness signatures.
- **Property release** for identifiable private property, artwork, and venues with
  photo policies. Landmarks/trademarked buildings are often restricted regardless
  of release. Logos must be cloned out for commercial, or the image goes editorial.
- Standard tooling: **Easy Release** app (accepted by Getty, iStock, Shutterstock,
  Alamy, Dreamstime; captures witness signatures). Standardize on it from shoot #1.
- Release hygiene is a liability issue, not just QC — contributor agreements make
  **us indemnify the platform** for release/rights failures.

## Metadata standard

- Every platform ingests embedded **IPTC**: Title (ObjectName/XMP-dc:Title),
  Description (Caption-Abstract/XMP-dc:Description), Keywords (IPTC
  Keywords/XMP-dc:Subject). Write once with `scripts/photo-metadata.sh embed`,
  every platform auto-fills.
- Keywording: 25–50 relevant terms; **Adobe caps at 49 and weights the first ~10**
  (order matters there); Shutterstock caps at 50, order-agnostic; Alamy uses 10
  supertags. Spam triggers rejection.
- At scale: CSV upload (Shutterstock and Adobe have documented CSV formats) and
  **Xpiks** (free, macOS) for keywording presets + direct FTP upload to agencies.
  StockSubmitter is Windows-only now — not an option on this Mac.

## Tax

- **Schedule C** (active trade or business, SE tax, QBI-eligible) — platforms
  report on 1099-MISC Box 2 "Royalties" but it is not passive Schedule E income.
  Keep the photography line as its own Schedule C, separate from the software line.
- **W-9 everywhere** (including foreign platforms like 123RF/Depositphotos):
  owner name on line 1, "Purplelink LLC" line 2, owner TIN (disregarded-entity
  rule). Decide whether to use an owner-level EIN instead of spreading the SSN
  across a dozen platforms.
- 1099-MISC royalty threshold stays **$10**; platforms paying via PayPal/Payoneer
  fall under the 1099-K regime ($20k/200 txns for TY2026). All income reportable
  regardless of forms received.
- **Sales tax — the direct-sales trap:** Georgia taxes digital photographs sold
  with permanent-use rights (effective 2024-01-01). Marketplace sales are the
  platform's problem; **direct licensing from purplelink.llc to a GA buyer is
  ours**. Before the first direct sale: either register to collect GA sales tax,
  or route checkout through a merchant-of-record (Paddle / Lemon Squeezy).

## GSU / USG outside-activity wrinkle

BOR Policy 8.2.15 requires prior written approval for compensated outside
activities that "relate to the employee's expertise or responsibilities."
Photography licensing is plausibly unrelated to IS-professor expertise, **but** it
runs through the same LLC named in the existing approved disclosure, and GSU's
local implementation may sweep broader than the BOR minimum. Low-cost safe move:
ask GSU ethics/compliance whether the existing disclosure needs amending; keep
university time/equipment/facilities fully out of the photo business. (Existing
disclosure docs: `Legal/gsu-external-activities-disclosure.*`.)

## Contributor-terms traps (check before every signup)

1. **Exclusivity upsells** — Getty/iStock per-image or account exclusivity kills
   the multi-platform strategy. Stay non-exclusive everywhere.
2. **AI-training clauses (2025–26 status):**
   - *Adobe Stock*: Firefly trains on the library, **no opt-out** (contributor
     challenge lost, Mar 2026). Uploading = consenting. Decide once.
   - *Shutterstock*: data deals with **opt-out** in Account → data licensing.
   - *Getty*: trains + licenses datasets; contributor compensation opaque.
   - *Alamy*: explicit AI-training program with revenue share, opt-in status
     tied to contributor agreement.
3. **Distribution-partner sublicensing** at steep discounts, on by default.
4. **Unilateral royalty resets** (Shutterstock 2020 precedent).
5. **Indemnification** — we warrant releases/rights.
6. **Payout minimums** ($25–$100) strand small balances; factor into how many
   platforms are actually worth carrying.

## Decisions Ben must make personally

1. Registration cadence (GRUPH-before-upload recommended) and $55/batch budget.
2. Non-exclusive stance confirmed on every signup (recommended: yes, always).
3. AI-training posture per platform (Adobe is all-or-nothing).
4. GSU disclosure: email ethics/compliance about amending.
5. Direct-sales tax: GA registration vs merchant-of-record.
6. W-9 TIN choice (SSN vs owner-level EIN).
7. Catalog split: commercial (release burden, higher ceiling) vs editorial-only.
8. Release app standardization (Easy Release default).
