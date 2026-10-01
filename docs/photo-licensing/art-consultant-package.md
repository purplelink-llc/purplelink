# Art-consultant package: rights position, selected set, price list

Written 2026-09-10. Decisions taken on Ben's instruction to "pick the decor
shortlist and decide the rights position."

The channel this serves: hospitality / healthcare / corporate art consultants,
who license reproduction rights across a property and pay **50%** (NINE dot
ARTS, net-30 after the client pays) to **60%** (Indiewalls) of retail with zero
production cost on our side. Atlanta is a hospitality-art hub — Kalisher/Soho
Myriad is here, and their submission form explicitly asks whether work is
available for licensing.

---

## 1. Rights position — DECIDED

### The constraint that drives everything
**751 of our images are already live, non-exclusively, on Alamy / Getty /
Shutterstock / Adobe.** We cannot sell exclusivity on any of them. Attempting to
is not a negotiating stance, it's a misrepresentation, and it surfaces later as
a real problem when a consultant's client finds the same image on a stock site.

### The policy

**a) Everything currently on a stock platform is offered NON-EXCLUSIVE only.**
No exceptions, no "quiet" exclusivity. If a project requires exclusivity, we
either decline or offer it from the reserved pool below.

**b) Standard grant we offer** (the default ask, before negotiation):
- Non-exclusive
- Unlimited reproduction **within one named property or project**
- Perpetual for that property, no renewal fee
- Any size, any substrate, framed or unframed
- No third-party resale of the image as standalone art prints
- Credit not required
- We retain all other rights, including continued stock licensing

**c) A reserved pool exists for exclusivity, and it is NEW WORK ONLY.**
Anything we want to be exclusive-eligible must never be uploaded to a stock
platform. The forthcoming Atlanta body of work is the first such pool — hold it
off stock entirely so it can be sold exclusively at a premium. This is the one
place exclusivity is genuinely available to us, so don't spend it accidentally.

**d) What we refuse**
- Exclusivity on any stock-live image
- Full copyright assignment / work-for-hire buyout of existing library images
- Anything requiring us to take images down from stock platforms retroactively
  (we'd be unable to guarantee removal from downstream distributors anyway)

**e) Releases.** Everything in a consultant package must be free of
recognisable people and of third-party IP. See the exclusion list in §4 — this
is the single biggest source of images that *look* sellable and aren't.

### Why this shape
It matches what consultants actually buy (reproduction rights per property, not
exclusivity), it costs us nothing we already have, and it keeps the
non-exclusive multi-platform strategy this business is built on intact. The
reserved-pool carve-out means we're not permanently locked out of the higher-
value exclusive deals — we just have to shoot for them deliberately.

---

## 2. Selected set — 25 images

Chosen by looking at every candidate, not by keyword inference. Criteria:
calm palette, open composition, restorative subject for the healthcare/
hospitality set; strong graphic architecture for the corporate/hospitality set.

Exported files and a manifest live in
`photo-licensing-workspace/consultant-package/` (25 files, 2000px long edge,
sRGB, copyright and creator embedded; originals untouched).

### Calm nature — 15 (healthcare + hospitality)
| # | file | subject |
|---|---|---|
| 1 | DSC_8669.jpeg | **Matterhorn mirrored in Riffelsee** — strongest decor frame in the library |
| 2 | DSC_1007.jpeg | Brúarfoss, braided turquoise falls |
| 3 | DSC_1275.jpeg | Gljúfrabúi, moss canyon waterfall |
| 4 | DSC_1326.jpeg | Skógafoss with rainbow |
| 5 | DSC_1601.jpeg | Jökulsárlón, icebergs on still water |
| 6 | DSC_8610.jpeg | Matterhorn with cloud |
| 7 | DSC_8450.jpeg | green alpine ridge panorama |
| 8 | DSC_8506.jpeg | Wetterhorn massif above a green valley |
| 9 | DSC_1362.jpeg | Dyrhólaey cliffs, blue sea |
| 10 | DSC_1372.jpeg | Reynisfjara black sand beach and sea stack |
| 11 | DSC_1395.jpeg | glacier ice cave, teal |
| 12 | DSC_1271.jpeg | Seljalandsfoss from behind the curtain |
| 13 | DSC_0832.jpeg | Kerið crater lake, deep teal |
| 14 | DSC_1143.jpeg | waterfall over green moss |
| 15 | DSC_0035.jpeg | calm bay and forested headland, Panama |

Geographic spread: 9 Iceland, 5 Switzerland, 1 Panama. Five weaker Iceland
frames (DSC_0755, DSC_1152, DSC_1216, DSC_1253, DSC_1558) were dropped after
the Switzerland/Panama sheet was reviewed.

**Final architecture 10** (swapped DSC_0119 out for DSC_8190, which pairs
architecture with water and is far stronger): DSC_1230, DSC_8190, DSC_0147,
DSC_0155, DSC_0159, DSC_8151, DSC_8199, DSC_6772, DSC_3542-Enhanced-NR,
DSC_3554-Enhanced-NR.

### Country labels look wrong for part of the library — NEEDS BEN
While reviewing, a cluster of images labelled **Switzerland** in
`alamy-locations.json` are visibly **California** — giant sequoias and what
looks like Lake Tahoe, not the Alps. Affected: DSC_1799, DSC_1912, DSC_1962,
DSC_0298, DSC_0380, DSC_1813, DSC_1856, DSC_0093 and possibly
DSC_1906-Enhanced-NR. The DSC_8xxx Swiss images are correctly labelled.

This matters beyond tidiness: `country_of_shoot` was written to Getty today
from this data, and the same-day inference in `getty-country-tag.py` propagates
whatever these files say. Note Ben labelled DSC_1906-Enhanced-NR as Switzerland
by hand today while labelling the DSC_16xx-17xx range United States, so either
that one frame really is Swiss or it was a slip. **Not corrected unilaterally —
a country is a factual claim and this needs his confirmation.**

### Architecture & cityscape — 10 (hospitality + corporate)
| # | file | subject |
|---|---|---|
| 16 | DSC_1230.jpeg | Búðakirkja black church, Iceland |
| 17 | DSC_8190.jpeg | Bern bridge over the turquoise Aare |
| 18 | DSC_0147.jpeg | San Francisco de Asís church, Panama |
| 19 | DSC_0155.jpeg | colourful colonial street, Casco Viejo |
| 20 | DSC_0159.jpeg | pink colonial facade with arches |
| 21 | DSC_8151.jpeg | Bern old town and cathedral spire |
| 22 | DSC_8199.jpeg | Bern rooftops from above |
| 23 | DSC_6772.jpeg | St Paul's Cathedral, London |
| 24 | DSC_3542-Enhanced-NR.jpeg | **Atlanta skyline at night** |
| 25 | DSC_3554-Enhanced-NR.jpeg | **Atlanta aerial at dusk** |

Both Atlanta frames are in deliberately — "local to the venue" is the strongest
documented hospitality preference and Atlanta is where the consultancies are.
They are also the *only* two Atlanta images in the entire library, which is the
argument for shooting more.

---

## 3. Price list — opening position

Anchored to verified production costs: a 24×36 luster print is ~$48
([ProLab](https://prolabprints.com/large-prints-and-posters/24x36/)), and
framed-and-matted from a pro lab runs **$155–190+** (20×30 = $155.04,
[Bay Photo](https://bayphoto.com/wall-displays/framed-prints/framed-matted-prints/)).
At a 50% consultant split, a framed piece must retail **≥$550** to be worth
fabricating — which is the whole reason we lead with licensing instead.

**Reproduction licence, per image, per property** — our preferred product:
| property scale | retail we propose | our 50-60% |
|---|---|---|
| single venue (restaurant, cafe, small office) | $450 | $225-270 |
| boutique property / one floor | $900 | $450-540 |
| full hotel or multi-floor corporate | $1,800 | $900-1,080 |

**Framed physical pieces** (only if a consultant insists on fabrication):
| size | retail | our net after ~$190 production at 50% |
|---|---|---|
| 20×30 framed | $650 | ~$135 |
| 24×36 framed | $850 | ~$235 |
| 30×45 framed | $1,200 | ~$410 |

**Direct / festival sales** (no consultant split): 16×24 unframed $150,
24×36 unframed $250, 24×36 framed $450.

**These retail figures are an opening position, not verified market rates.** The
production costs and the split percentages are verified; the retails are
extrapolated from an unverified $600–1,200 typical-framed-piece range. Expect
consultants to counter, and treat the first two deals as price discovery.

---

## 4. Excluded, and why — read before adding anything

The visual pass caught two categories that keyword filtering had let straight
through. Both would have been embarrassing at best.

**Recognisable people — needs a model release for commercial decor use.**
DSC_0908, DSC_1048, DSC_1336, DSC_1401, DSC_1531 (Iceland, Ben in frame);
DSC_0001, DSC_0005, DSC_2956, DSC_3059, DSC_3107 (portraits); DSC_5992,
DSC_6405 (graduation portraits). We hold no releases for any of these.

**Third-party IP / franchise content — do not license.**
DSC_6888 (Diagon Alley set), DSC_6873, DSC_6880, DSC_6699 (museum displays and
studio interiors). This is the same failure mode as the Warner Bros. studio-prop
incident that already reached two agencies; it must not reach a consultant.

**Brand and publicity rights.**
DSC_3208 (Tokyo neon including a recognisable film poster with an actor's
likeness), DSC_3429 (Mt Fuji framed over a Lawson storefront sign). Both are
fine as editorial stock and wrong for commercial decor.

**Excluded on demand, not on legality:** Sonoran desert work (arid, spiky reads
as low-restorative in the evidence-based-design literature), macro insects
(near-zero decor demand), college sports action (near-zero decor demand **and**
likely needs school/conference trademark clearance before being offered
anywhere as decor).

---

## 5. Next actions
1. Pull a Switzerland/Panama calm-nature sheet and swap 4-5 in for spread.
2. Export the 25 as sRGB JPEGs, long edge 2000px, with a discreet copyright.
3. Send to: curation@kalisher.com, DAC Art Consulting, Art Initiatives,
   ART+WORKS, Skyline Art (alexd@skylineart.com, healthcare), NINE dot ARTS
   (via CaFE, no fee), Indiewalls. Lead with **licensing available**, attach the
   price list, state non-exclusive plainly.
4. Shoot Atlanta deliberately, and **keep it off every stock platform** so it
   stays exclusive-eligible per §1(c).
