# Remaining Platforms — Account Setup Checklist

Work top to bottom. Each account is yours to create (signup, terms, W-9 can't be
delegated); once credentials are in Keychain, uploading is one command.

Live already: **Fine Art America** (267), **Adobe Stock** (273 uploaded),
**Alamy** (QC pending).

---

## The pattern for every FTP agency

1. Create the account and complete the tax form (**W-9**: your name line 1,
   Purplelink LLC line 2, EIN — same as the others).
2. Find the FTP username in the contributor area.
3. Store the password in Keychain (prompts, so it stays out of shell history):

```bash
security add-generic-password -a "<ftp-username>" -s <service> -w
```

4. Export the username, then upload:

```bash
export SHUTTERSTOCK_USER="<ftp-username>"
python3 scripts/stock-ftp-upload.py --agency shutterstock --set qc
python3 scripts/stock-ftp-upload.py --agency shutterstock --set all
```

Run `scripts/stock-ftp-upload.py --list` for every agency's host, service name,
and env var. State is journaled per agency, so re-runs skip what's done.

---

## 1. Shutterstock — do this first

- Sign up: https://submit.shutterstock.com
- **Toggle the AI data-licensing opt-out** in Account Settings if you want your
  work excluded from their AI training deals. Unlike Adobe, they let you.
- FTP host `ftp.shutterstock.com`, Keychain service `shutterstock-ftp`
- **749 images eligible** (≥4MP)
- Royalty 15–40%, resets to the floor every January 1
- Biggest buyer pool of anything left; FTP makes it cheap to feed

## 2. Dreamstime

- Sign up: https://www.dreamstime.com/sell-stock-photos-images
- FTP host `upload.dreamstime.com`, service `dreamstime-ftp`
- **749 images eligible** (≥3MP)
- Royalty 25–50%. **Decline per-image exclusivity** — the +10% isn't worth
  pulling a file from everywhere else.

## 3. Depositphotos

- Sign up: https://depositphotos.com/seller-price.html
- FTP host `ftp.depositphotos.com`, service `depositphotos-ftp`
- **749 images eligible** (≥3.8MP)
- Royalty 30–38% on packs; subscription downloads pay a flat $0.25–0.33

## 4. Getty / iStock — apply early, upload later

- Apply: https://www.gettyimages.com/workwithus
- **The only major agency with no FTP** — uploads go through their ESP web tool,
  so this one stays manual.
- Six application images staged in `photo-licensing-workspace/getty-application/`
- **Accept the non-exclusive agreement** (it's their default on acceptance).
  Decline exclusivity if offered later — it locks images to Getty alone.
- Use the **666-image AI-free set** (`getty-safe-set.csv`), not the full library:
  Getty bans generative-AI retouching beyond 10% of pixels, and bans it entirely
  on editorial. 85 of your images are Topaz-processed.
- Juried, so apply now — the review lead time runs in parallel with everything else.

## 5. 123RF — last, and optional

- Sign up: https://www.123rf.com/contributors
- FTP host `submit.123rf.com`, service `123rf-ftp`
- **694 images eligible** (≥6MP — the highest floor of the group)
- Royalty 30–60% but a documented history of unannounced royalty cuts and
  payment complaints. Watch the first payout closely.

---

## Sequencing note

Alamy's QC verdict on your 5 test images is the cheapest quality signal you'll
get. If those fail, the same flaw applies to every agency above — worth knowing
before pushing 749 images to four more places.

## Deliberately skipped

**Wirestock** (15% cut, exit lock-in), **500px** (25% of opaque net, conflicts
with a direct Getty port), **Freepik/Magnific** (~$0.05/download, AI-flooded),
**Pond5** (photos are an afterthought there; revisit only with video),
**Canva** (contributor program paused since 2022 — check quarterly),
**EyeEm/Twenty20** (dead). Reasoning in `platform-matrix.md`.
