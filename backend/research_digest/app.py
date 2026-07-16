"""Modal weekly cron for the MuscleOnGLP research roundup (Option B: token deploy).

Runs Mondays 13:00 UTC. Harvests new GLP-1/muscle literature, curates + summarizes
via Claude, then clones the (private) getmuscleonglp.com repo, renders the post +
rebuilt hub + sitemap into it, commits, and deploys the whole site via the Netlify
CLI with an auth token. No Netlify git-connection or Pro plan required, and the
repo stays private. Finally emails Ben a review copy. DRY_RUN returns the rendered
artifacts without cloning/deploying.

Required Modal secrets:
  anthropic-secret -> ANTHROPIC_API_KEY
  github           -> GITHUB_TOKEN         (read+write to purplelink-llc/muscleonglp)
  netlify          -> NETLIFY_AUTH_TOKEN    (deploy the muscleonglp site)
  resend           -> RESEND_API_KEY        (review email; optional)
"""
import logging
import os
import subprocess

import modal

logger = logging.getLogger(__name__)

app = modal.App("muscleonglp-research")

SITE_ID = "c6201581-69ed-4da9-b982-c71c94d30260"
REPO = "purplelink-llc/muscleonglp"

_image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("git", "curl")
    .run_commands(
        "curl -fsSL https://deb.nodesource.com/setup_20.x | bash -",
        "apt-get install -y nodejs",
        "npm install -g netlify-cli@17",
    )
    .pip_install("httpx==0.27.2")
    .add_local_python_source("research_digest")
)


@app.function(
    image=_image,
    schedule=modal.Cron("0 13 * * 1"),  # Mondays 13:00 UTC (9am ET)
    secrets=[
        modal.Secret.from_name("anthropic-secret"),
        modal.Secret.from_name("github"),
        modal.Secret.from_name("netlify"),
        modal.Secret.from_name("resend"),
    ],
    timeout=900,
)
async def run_weekly_roundup(dry_run: bool = False):
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    import httpx
    from research_digest.harvester import harvest_all
    from research_digest.curator import curate
    from research_digest.renderer import render_post_html, render_hub_html, post_url

    dry_run = dry_run or os.environ.get("DRY_RUN", "").lower() in ("1", "true", "yes")
    gh_token = os.environ.get("GITHUB_TOKEN", "")
    netlify_token = os.environ.get("NETLIFY_AUTH_TOKEN", "")
    resend_key = os.environ.get("RESEND_API_KEY", "")

    async with httpx.AsyncClient() as client:
        papers = await harvest_all(client, days=7)
        logger.info("roundup: harvested %d papers", len(papers))
        digest = await curate(client, papers)
        if digest is None:
            logger.info("roundup: nothing to publish this week")
            return

        logger.info("roundup: %d items for %s", digest.count, digest.week_label)
        for it in digest.items:
            logger.info("  [%d/3] %s", it.relevance, it.paper.title)

        if dry_run:
            blurb = (digest.items[0].summary if digest.items else digest.intro)[:180]
            entry = {"slug": digest.slug, "week_label": digest.week_label,
                     "date": digest.date, "count": digest.count, "blurb": blurb}
            return {"slug": digest.slug, "post_html": render_post_html(digest),
                    "hub_html": render_hub_html([entry]), "entry": entry}

        # --- publish (Option B: clone -> render -> commit -> deploy via Netlify CLI) ---
        site = "/root/site"
        clone_url = f"https://x-access-token:{gh_token}@github.com/{REPO}.git"
        subprocess.run(["git", "clone", "--depth", "1", clone_url, site], check=True)

        from research_digest.publisher import write_into
        write_into(site, digest)

        subprocess.run(["git", "-C", site, "config", "user.email", "ben.ampel@gmail.com"], check=True)
        subprocess.run(["git", "-C", site, "config", "user.name", "MuscleOnGLP Bot"], check=True)
        subprocess.run(["git", "-C", site, "add", "-A"], check=True)
        subprocess.run(["git", "-C", site, "commit", "-m", f"research: roundup {digest.slug}"], check=False)
        # Push must succeed: the repo is the manifest's source of truth, so a
        # silent push failure would make next week's hub drop this week's post.
        subprocess.run(["git", "-C", site, "push", "origin", "HEAD:main"], check=True)

        # npm install so the Netlify CLI bundles @netlify/blobs into the functions.
        subprocess.run(["npm", "install"], cwd=site, check=True)
        env = {**os.environ, "NETLIFY_AUTH_TOKEN": netlify_token}
        subprocess.run(
            ["netlify", "deploy", "--prod", "--dir", ".",
             "--functions", "netlify/functions", "--site", SITE_ID,
             "--message", f"weekly research roundup {digest.slug}"],
            cwd=site, env=env, check=True,
        )
        logger.info("roundup: deployed %s to %s", digest.slug, post_url(digest.slug))

        from research_digest.mailer import notify_review
        sent = await notify_review(client, digest, resend_key)
        logger.info("roundup: review email sent=%s", sent)


@app.local_entrypoint()
def main():
    # Local render helper (used for the first post): renders via Modal secrets and
    # writes artifacts into OUTPUT_DIR so they can be published with local creds.
    res = run_weekly_roundup.remote(dry_run=True)
    if not res:
        print("no roundup produced"); return
    out = os.environ.get("OUTPUT_DIR", "../muscleonglp-site")
    slug = res["slug"]
    post_dir = os.path.join(out, "research", slug)
    os.makedirs(post_dir, exist_ok=True)
    open(os.path.join(post_dir, "index.html"), "w").write(res["post_html"])
    open(os.path.join(out, "research", "index.html"), "w").write(res["hub_html"])
    import json as _json
    open(os.path.join(out, "research", "index.json"), "w").write(_json.dumps([res["entry"]], indent=2))
    print(f"WROTE_SLUG={slug}")
