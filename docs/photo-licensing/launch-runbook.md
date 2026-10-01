# Photo Licensing — Launch Runbook

Sequenced checklist. Items marked **[BEN]** require you personally — account
creation, terms acceptance, tax forms, and payments are things an agent must not
do on your behalf. Everything else can be delegated/automated.

Track per-platform status in `tracker.csv`.

## Phase 0 — Decisions (before anything else)

- [ ] **[BEN]** Confirm non-exclusive stance everywhere (recommended: yes).
- [ ] **[BEN]** Adobe AI posture: uploading to Adobe Stock = consenting to
      Firefly training, no opt-out. In or out? (It's also the #1 earner.)
- [ ] **[BEN]** Pick catalog split: which work goes commercial (needs releases)
      vs editorial-only (no releases, Alamy-centric).
- [ ] **[BEN]** W-9 TIN choice: SSN vs owner-level EIN across ~8 platform tax
      interviews.
- [ ] **[BEN]** Email GSU ethics/compliance: does the existing outside-activity
      disclosure need amending to add photography licensing under Purplelink LLC?
      (BOR 8.2.15; see legal-ops.md §GSU.)

## Phase 1 — Foundation (week 1)

- [ ] Select the first batch (target 100–300 strong images; platforms reward
      consistent uploads over one dump — hold reserves for a weekly cadence).
- [ ] Keyword + title + describe each (25–49 keywords, most important first
      ~10 for Adobe). Build `metadata.csv` (filename,title,description,keywords).
- [ ] Embed IPTC: `scripts/photo-metadata.sh embed metadata.csv <dir>`.
      Verify: `scripts/photo-metadata.sh check <dir>`.
- [ ] **[BEN]** File copyright registration **before first upload**: eCO GRUPH
      group application, $55, up to 750 photos, with numbered title list
      (export via `scripts/photo-metadata.sh export`). This is what makes
      infringement enforceable ($750–$30k statutory/work vs ~nothing).
- [ ] **[BEN]** Install a release app (Easy Release recommended — Getty-accepted,
      witness signatures) and back-fill releases for any recognizable
      people/property in the commercial set. No release → editorial or cut.

## Phase 2 — Base layer signups (weeks 1–2)

Order matters — juried applications have lead time, so submit those first.

- [ ] **[BEN]** Apply to iStock/Getty (juried, 3–6 best images) — sign the
      **non-exclusive** ASA only. $100 payout min.
- [ ] **[BEN]** Apply to Vecteezy (25 files + government ID, ~1 week decision).
- [ ] **[BEN]** Create Adobe Stock contributor account (if Phase 0 says yes);
      complete tax interview (W-9); note SFTP credentials.
- [ ] **[BEN]** Create Shutterstock contributor account; tax interview;
      **toggle the AI data-licensing opt-out** in Account settings if desired;
      note FTPS credentials.
- [ ] **[BEN]** Create Alamy contributor account. First submission is 100%-
      inspected — send 3–5 technically flawless files to pass QC, then volume.
- [ ] **[BEN]** Create Dreamstime, Depositphotos accounts; tax interviews; FTP creds.
- [ ] **[BEN]** Create 123RF account (last priority; watch payments), Pond5
      (only if video planned), Freepik/Magnific (150–200-asset initial batch,
      only if the volume tail is wanted).
- [ ] Store all FTP/SFTP credentials in Keychain; record signup dates in tracker.

## Phase 3 — First distribution (weeks 2–3)

- [ ] Install Xpiks (free, macOS) → configure FTP endpoints for all live accounts.
- [ ] Push batch #1 everywhere; where CSV metadata is supported (Adobe,
      Shutterstock, Vecteezy), upload the CSV too.
- [ ] Log acceptance/rejection rates per platform in tracker; adjust QC.
- [ ] Set a weekly upload cadence (steady uploads outrank bulk dumps).

## Phase 4 — Premium + genre applications (month 2, once base is live)

- [ ] **[BEN]** Apply to Offset via the Shutterstock account (no partition cost).
- [ ] Watch stocksy.com/cta/welcome for the next Call to Artists window
      (economics are the best in the industry: 50–75% + profit share, but it
      takes the whole shoot's similars exclusive).
- [ ] **[BEN]** If the work fits: Westend61 or Cavan application (one premium
      home per shoot — never both). Confirm Cavan Pro pricing first.
- [ ] **[BEN]** If moody/conceptual work exists: Arcangel or Trevillion (never
      split similars between them; Arcangel license model is permanent per image).

## Phase 5 — Direct channel (defer until agencies validate demand)

- [ ] **[BEN]** Picfair Plus (~$11/mo) as the first direct storefront — 0% cut,
      own marketplace demand, custom domain (e.g. photos.purplelink.llc).
- [ ] Own-site `/photos/` storefront on the existing Netlify+Stripe stack only
      after Stripe reactivates for the manuscript tools. **Before first direct
      sale:** resolve GA sales tax (register to collect, or merchant-of-record —
      Paddle/Lemon Squeezy). See legal-ops.md §Tax.

## Recurring operations

- Weekly: upload batch (Xpiks fan-out), update tracker.
- Monthly: **[BEN]** GRUPH registration for the month's new batch ($55) before
  its first upload; reconcile per-platform earnings into bookkeeping
  (photography = its own Schedule C line, separate from software).
- Quarterly: check Canva contributor reopening; check Stocksy CTA; re-verify
  royalty tables (Alamy/SSTK/123RF have all cut rates unilaterally before).
- Jan: expect 1099-MISC (Box 2, $10 threshold) from US platforms; foreign
  platforms (Alamy/123RF/Freepik) send nothing — income still reportable.

## Success gates

- Gate 1 (month 3): >60% acceptance rate on Adobe+SSTK, 500+ images live.
- Gate 2 (month 6): first payouts cleared on ≥2 platforms; decide whether
  low performers (123RF, Freepik) are worth continued uploads.
- Gate 3 (month 9–12): if monthly revenue > ~$100, invest in premium
  applications + direct channel; if not, hold at automated base-layer cadence.
