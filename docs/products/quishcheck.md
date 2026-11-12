# Quishcheck: check a QR code on your screen before you open it

Status: scoped and prototyped 2026-11-12. Not released, not listed, nothing bought. Prototype repo:
`/Volumes/Extreme SSD/Quishcheck` (local only, commit `6624d59`, no remote).

## The problem

QR phishing ("quishing") puts the link in an image so email link scanners never see it. The email says "scan to keep
your mailbox" or "scan to sign", and the reader picks up a phone, which has none of the company's protections and a
small address bar. Quishcheck reads the code on the Mac screen where the email already is and says what the link
really is before anyone opens it.

## What it does (v1)

- A hotkey (Control-Option-Command-Q; one key from Control-Command-Q, Lock Screen, so the default may change) or the menu-bar icon scans every display once. Vision finds QR, Micro QR and
  Aztec codes. Quishcheck's own windows are left out of the capture.
- Each code gets an outline drawn on top of it, coloured by verdict, on whichever display it is on.
- Clicking a code opens a card with the exact address, the registrable domain in bold, and a Safe / Caution / Danger
  verdict with up to five plain reasons.
- Buttons: Copy, Open, "Check where it leads". Open is the default only on Safe. On Caution the default is Copy. On
  Danger the default is Close, and opening needs "Open anyway…" and a confirmation.
- A host that imitates another name with lookalike letters is printed in its real `xn--` spelling, with "Looks like:
  paypal.com" underneath, never in the Unicode that imitates.
- Wi-Fi, phone, SMS, email and script payloads get their own explanation (an open Wi-Fi network is Caution, a
  `javascript:` code is Danger).

## How the verdict is made

| Signal | Where it runs | Verdict effect |
|---|---|---|
| Lookalike brand name: confusable letters, "rn" for "m", one typo or swapped letters, about 30 brands quishing imitates (Microsoft 365, DocuSign, carriers, banks, payment apps, tolls, parking) | Mac | Danger |
| Punycode with mixed alphabets | Mac | Danger |
| IP-address host, `user@host` trick, `javascript:` / `data:` scheme | Mac | Danger |
| Brand name inside a longer label ("microsoft-login"), cheap TLD, shortener, free hosting, open redirector, plain http, odd port, long URL, file download | Mac | Caution |
| Domain registered under 30 days (Danger) or under 180 days (Caution), 3+ years (good) | RDAP, sends only the registrable domain, only when the domain is not on the popularity list | as stated |
| On a popularity list of widely visited domains | Mac, list on disk (weekly refresh planned; the script exists but has not run) | good |
| Redirect chain: every hop checked, cookie-less, page never rendered, 10 hops max | Network, opt-in | the worst hop counts |

Rules: any Danger signal makes the verdict Danger. Safe needs at least one good signal and nothing worse than
information. Everything else is Caution, with "nothing vouches for this site" stated. There is no "probably fine".

Redirect following is off by default. A quishing link often carries a per-recipient token, so requesting it can tell
the sender this person looked. The card offers it as a separate click, and a menu switch turns it on for every scan.

## Data sources and licences

| Source | Use in a paid app | Decision |
|---|---|---|
| Google Safe Browsing | Non-commercial only ([usage limits](https://developers.google.com/safe-browsing/v4/usage-limits)); commercial use is the paid [Web Risk](https://cloud.google.com/web-risk/pricing) API | Not used |
| OpenPhish community feed | [Terms](https://openphish.com/terms.html) bar commercial use without written consent | Not used |
| URLhaus (abuse.ch) | Needs an Auth-Key; commercial use "may require a paid subscription" via Spamhaus ([API](https://urlhaus.abuse.ch/api/), [terms](https://abuse.ch/terms-of-use/)); terms bar AI training on the data | Not used |
| PhishTank | [New registrations disabled](https://phishtank.org/register.php), so no key | Not used |
| [Tranco](https://tranco-list.eu/) top list | No licence of its own; one input (Cloudflare Radar) is CC BY-NC | Not used |
| Majestic Million | CC BY 3.0 Unported, per [its page](https://majestic.com/reports/majestic-million) (checked 2026-11-12); attribution required, commercial use allowed | Popularity list, credited in About |
| RDAP via the IANA bootstrap file, rdap.org fallback | Public registry data ([IANA bootstrap](https://data.iana.org/rdap/dns.json)); [rdap.org](https://about.rdap.org/) allows 10 requests per 10 s | Domain age, cached |

The code has a `ThreatList` hook for a licensed blocklist later. Asking OpenPhish or Spamhaus for terms is outreach and
is Ben's call. The bundled public suffix list is MPL 2.0 and also gets an About credit.

## Privacy stance

The scan, decoding and every check except RDAP and redirects run on the Mac. Screen images are never saved or sent.
RDAP gets the registrable domain only, never the full link. Redirects are followed only when the user asks. No
account, no telemetry, no analytics. The app needs Screen Recording permission; the planned onboarding says why before macOS asks (not built yet).

## Price and packaging

$9.99 once, 7-day trial then a licence key, like Panely and Summonly. Direct download first (Screen Recording and
global capture fit the App Store sandbox poorly; a Mac App Store build is a later question). Whether it joins the
Mac Suite is Ben's decision.

## Competitors (checked 2026-11-12)

| App | Platform, price | On-screen scan | Overlay on code | Verdict or safety check | Follows redirects |
|---|---|---|---|---|---|
| QRSpell | Mac App Store, free with tips | Yes, all displays | No | No | No |
| QRCodeSnap | Mac App Store, free + subscription | Yes, whole screen | No | No | No |
| QRule | Mac App Store, free | Yes, drag a box, multi-display | No | No | No |
| QR Capture | Mac App Store, free + IAP | Yes | No | No | No |
| QRGo (Block) | Homebrew, free | Drag a box | No | No; a developer tool that opens the link in a simulator | No |
| Zapp | GitHub, free | Via screenshots | No | No | No |
| qr-scanner (open source) | GitHub, free | Yes, "Smart Mode" highlights codes | Partial | Preview only | No |
| QR Detective | Mac menu bar, paid (Product Hunt; store listing not confirmed) | Web pages | Not confirmed | No | No |
| AI ScamScan QR | iPhone only | No (camera) | n/a | Claims phishing detection; method not described | Not stated |
| Netcraft, Kaspersky, Trend Micro scanners | Phones, cloud lookups | No | n/a | Yes, their own reputation data | Some |

None of the App Store QR apps had a US rating at the time of the check.

**The gap is real.** Every Mac app that reads codes on screen only decodes and opens them. The phone apps that judge
links cannot see a Mac screen. Nothing on the Mac draws on the code, says Safe / Caution / Danger with a stated
method, or unwraps the redirect chain. Plain scanning is free everywhere, so the verdict and the redirect chain are
what a buyer pays for, and the reasons on the card have to be good enough to earn that.

## Name

Working name: **Quishcheck**. No App Store hit for it, Quishlens, QR Sentry, CodeWard, ScanSure or Lookfirst. Taken or
too close: QR Guard, Quishield, QRSafe, Codecheck, Glance QR, Squint, Peekcode (a Mac app), Linklens, Scanwise, QR
PreScan. QR Lookout is clear on the store but Lookout is a security company, so avoid it. Domain and USPTO checks are
not done for any of them.

## Risks

- **A wrong Safe.** A link rated Safe that is not is the worst outcome for a security app. Safe therefore needs
  positive evidence, and a compromised popular site would still pass. The card should keep saying what was checked.
- **Screen Recording permission.** It scares some people and macOS asks again from time to time. The onboarding
  has to explain it plainly.
- **Abuse of popular hosts.** Quishing often lands on user content under a popular domain (Google Forms, Workers and Pages hosting, search-engine redirect URLs). Those hosts are on the free-hosting and open-redirector lists, so they read as Caution even when the domain ranks high: checked on the prototype with google.com, workers.dev and github.io on the list, all three came out Caution. A file share or form host missing from those lists would get Safe.
- **Popularity list.** Without it almost nothing reaches Safe. Majestic is CC BY 3.0, so it can ship with credit.
- **The heuristics will miss things.** A new domain with a plain name and no brand word reads as Caution, not Danger,
  unless RDAP says it is days old.
- **Free competitors** may add a basic check.

## What the prototype proved, and what it did not

Proved, headless and offline, with no permission prompt and no window:
- 16 tests pass, covering Vision detection on generated codes, the public suffix list, punycode, lookalikes, verdict
  rules, Open never the default on Danger, and redirects followed only when asked.
- `--scan-image` finds three codes on a 1800x900 test image with correct boxes and verdicts (Danger, Safe, Caution).
- `--render-card` renders the card for each verdict.
- The app builds and is ad hoc signed as `llc.purplelink.quishcheck.test`.

Not exercised yet:
- live ScreenCaptureKit capture
- overlay placement across several displays and mixed Retina scales
- the hotkey
- real RDAP and redirect requests against the network
- the 1M-domain list load time and `scripts/refresh-data.sh`
- onboarding, licence key and About credits (not built)

Next step if this goes ahead: run a test copy with Screen Recording granted on a second display, then the onboarding,
licence key and About credits.
