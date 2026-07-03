# One-off setup script — creates the Stripe Coupon backing the referral
# credit mechanic (task #57). Run once via `modal run` so the secret key
# stays inside the Modal execution environment and is never printed to a
# local shell/log. Prints only the resulting (non-secret) coupon id.
#
# Usage (from backend/): modal run setup_referral_coupon.py
#
# Already run once — created coupon id "purplelink-referral-2usd" ($2 off,
# duration=once) on 2026-07-03. Re-running is safe/idempotent (it detects
# the "already exists" error and no-ops) — kept here as the source of
# truth for what that coupon is, not something that needs to run again.
import modal

app = modal.App("purplelink-referral-setup")
stripe_secret = modal.Secret.from_name("stripe-secret")


@app.function(image=modal.Image.debian_slim().pip_install("httpx"), secrets=[stripe_secret])
def create_coupon():
    import os
    import httpx

    secret_key = os.environ["STRIPE_SECRET_KEY"]
    resp = httpx.post(
        "https://api.stripe.com/v1/coupons",
        auth=(secret_key, ""),
        data={
            "id": "purplelink-referral-2usd",
            "amount_off": "200",
            "currency": "usd",
            "duration": "once",
            "name": "Purplelink referral credit ($2 off)",
        },
    )
    if resp.status_code == 400 and "already exists" in resp.text:
        print("Coupon already exists: purplelink-referral-2usd")
        return
    resp.raise_for_status()
    data = resp.json()
    print(f"Created coupon: {data['id']}")
