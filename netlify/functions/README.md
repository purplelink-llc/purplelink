# Netlify Functions

## `indexnow-ping`

Pings the IndexNow shared endpoint (Bing / Yandex / Seznam / Naver) with URLs from the live sitemap whose `<lastmod>` matches today. Triggered automatically after every production deploy via a Netlify outgoing webhook.

**Function URL:**
```
https://purplelink.llc/.netlify/functions/indexnow-ping?token=<INDEXNOW_WEBHOOK_TOKEN>
```

The `INDEXNOW_WEBHOOK_TOKEN` environment variable is already set in Netlify (production context). To rotate it:

```
netlify env:set INDEXNOW_WEBHOOK_TOKEN <new-value> --context production
netlify deploy --prod   # function picks up the new value on next deploy
# Then update the outgoing webhook URL in Netlify dashboard to match.
```

## One-time setup: wire the deploy-succeeded webhook

This is the only step you have to do in the Netlify UI (the CLI doesn't expose outgoing-webhook config yet).

1. Go to [Site configuration → Build & deploy → Deploy notifications](https://app.netlify.com/projects/purplelink/configuration/notifications)
2. Under **Outgoing webhooks**, click **Add notification**
3. Configure:
   - **Event:** `Deploy succeeded`
   - **URL to notify:** `https://purplelink.llc/.netlify/functions/indexnow-ping?token=_LpQkCvG08Pp7kD62F5LXipYj70JsSG9R3iUk405pik`
   - **JWT signature secret:** leave blank (auth is via the URL token instead)
4. Save

After that, every successful production deploy automatically pings IndexNow about that day's changed URLs.

## Manual invocation

If you ever need to force a full re-ping (e.g., after a large sitemap rewrite):

```
TOKEN='_LpQkCvG08Pp7kD62F5LXipYj70JsSG9R3iUk405pik'
curl -X POST "https://purplelink.llc/.netlify/functions/indexnow-ping?token=$TOKEN&all=1"
```

The `all=1` flag pings every URL in the sitemap, not just today's. Use sparingly — IndexNow rate limits at ~10k URLs/day per domain.

## Verifying it works

After a `make deploy` finishes, check Netlify's Function logs:
- https://app.netlify.com/projects/purplelink/logs/functions

Look for a `indexnow-ping` invocation with a `200 pinged` response.

## The local-vs-webhook double-ping

`make deploy` (via `scripts/deploy.sh`) ALSO pings IndexNow from your laptop. After the Netlify webhook is wired up, you can either:

- **Leave both running** — IndexNow is idempotent and the double-ping is harmless (and gives you redundancy if either path fails).
- **Disable the local one** — edit `scripts/deploy.sh` to default to `--skip-ping`, or just stop using `make deploy` and rely on the webhook.

I'd recommend leaving both for the first week, then disabling the local ping once you've confirmed the webhook is firing reliably in the Function logs.
