# Vitae sidebar card: the sponsor slot

Vitae's sidebar has one small card. The app reads its text from
`https://purplelink.llc/vitae/promos.json` at most once a day, and falls back to
a copy built into the app when offline. The file has two parts:

- `"promos"`: the list of Purplelink suggestions the card rotates through. Older
  versions of Vitae read only this key and ignore everything else, so its shape
  must never change.
- `"sponsor"`: one optional entry that newer versions of Vitae show in the same
  card for part of the time. It is currently Purplelink's own (Vitae Plus).

## Schema

```json
"sponsor": {
  "id": "vitae-plus",
  "sponsor": "Purplelink",
  "title": "Vitae Plus",
  "body": "Themes, alternate icons and a milestones case for $5, once. Everything else stays free.",
  "url": "https://purplelink.llc/vitae/plus/?ref=vitae-card",
  "symbol": "sparkles",
  "starts": "2026-09-23",
  "ends": "2027-12-31",
  "share": 0.5
}
```

| Field | Rule |
|---|---|
| `id` | Short, stable slug for this placement. Use a new id for a new sponsor or campaign. |
| `sponsor` | Display name. `"Purplelink"` makes the card read "From Purplelink"; any other name makes it read "Sponsor · <name>". |
| `title` | 40 characters or fewer. |
| `body` | 140 characters or fewer. Plain text, no emoji, no urgency. |
| `url` | Must be `https://purplelink.llc/...`. The app opens only purplelink.llc links, so any other host is not opened. |
| `symbol` | An SF Symbols name, for example `sparkles` or `book`. |
| `starts`, `ends` | `YYYY-MM-DD`. The entry is shown only between these dates. |
| `share` | 0 to 1: the fraction of card showings given to the sponsor while it is active. The rest rotate through `promos`. |

To remove the sponsor, delete the `"sponsor"` key (or let `ends` pass). The card
goes back to rotating `promos`.

Check the file before deploying:

```sh
python3 -c 'import json; s=json.load(open("site/vitae/promos.json"))["sponsor"]; \
assert len(s["title"])<=40 and len(s["body"])<=140 and s["url"].startswith("https://purplelink.llc/"); print("ok")'
```

## Third-party sponsors

Because the app opens only purplelink.llc links, a third-party sponsor's link has
to go through a redirect on this site. Use the path `/go/<id>`, where `<id>`
matches the sponsor entry's `id`:

```json
"url": "https://purplelink.llc/go/example-sponsor"
```

Add the redirect to `netlify.toml`. It must sit above the catch-all
`from = "/*"` 404 rule at the end of the file, because Netlify applies the first
rule that matches. Example only; this is not a live redirect:

```toml
# Vitae sidebar sponsor: Example Sponsor, 2027-01-01 to 2027-03-31.
[[redirects]]
  from = "/go/example-sponsor"
  to = "https://example.com/?utm_source=vitae"
  status = 302
```

Use 302, not 301, so browsers do not cache the destination and the redirect can
be changed or ended. When a placement ends, point its `/go/` path at `/vitae/`
instead of deleting it, so a card text still cached somewhere never leads to a
404.

## Before a paid sponsor goes live

- The destination URL may carry a campaign tag such as `utm_source=vitae`, and
  nothing else. Vitae sends nothing to sponsors, and the redirect must not add
  anything about the person clicking.
- Update the copy that is only true while the card is Purplelink's own: on
  `site/vitae/index.html`, the "No third-party ads" line in the support section
  and the FAQ answer to "Does Vitae show ads?". The privacy policy already says
  the card may show a clearly labeled sponsor and that Vitae sends nothing to
  sponsors; re-read it against the actual arrangement.
- Keep the title and body in the site's voice: plain, specific, no hype.
