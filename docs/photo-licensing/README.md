# Purplelink Photo Licensing

New business arm: licensing Ben's photography non-exclusively across every
channel that allows it. Established 2026-08-04.

## Strategy in one paragraph

Run a **partitioned portfolio**. A non-exclusive base layer (the same files on
Adobe Stock, Shutterstock, iStock, Alamy, Vecteezy, Dreamstime, Depositphotos,
123RF, Freepik) maximizes breadth at zero marginal cost per platform once IPTC
metadata is embedded and FTP fan-out is configured. The best commercial shoots
each get ONE premium home (Stocksy / Westend61 / Cavan — per-image/series
exclusive, 40–75% royalties). Genre work (book covers, food, travel) gets
dedicated exclusive tranches (Arcangel/Trevillion etc.). Direct licensing
(Picfair, then own site) is deferred until agency channels validate demand.
Nothing in the stack requires whole-portfolio exclusivity; the only forced
choice is which single premium home each strong shoot gets.

## Reality check

Industry revenue-per-download fell ~12% in 2025 under AI-content pressure.
Adobe Stock is the center of gravity (2–4x Shutterstock for identical
portfolios). This is a patient, compounding side income — steady weekly
uploads beat bulk dumps, and meaningful revenue typically takes 6–12 months
and 1,000+ images live.

## Documents

- **[platform-matrix.md](platform-matrix.md)** — every channel: royalties,
  requirements, upload methods, exclusivity traps, skip list. (Web-verified
  2026-08-04 — royalty tables change unilaterally; re-verify quarterly.)
- **[launch-runbook.md](launch-runbook.md)** — sequenced checklist; items
  marked [BEN] need the owner personally (accounts, terms, tax, payments).
- **[legal-ops.md](legal-ops.md)** — copyright registration (GRUPH, $55/750
  photos, register BEFORE upload), releases, metadata standards, Schedule C /
  W-9 / sales tax, GSU outside-activity question, contributor-terms traps.
- **[tracker.csv](tracker.csv)** — live per-platform status.
- **[../../scripts/photo-metadata.sh](../../scripts/photo-metadata.sh)** —
  embed/check/export IPTC metadata (exiftool). Write metadata once; every
  platform auto-fills from it.

## Toolchain

- `exiftool` (installed) — metadata embedding
- Xpiks (free, macOS) — keywording presets + FTP fan-out to all agencies
- Easy Release (iOS) — model/property releases, Getty-accepted
- eCO (copyright.gov) — GRUPH group registrations
