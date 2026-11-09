# NOTE: runs against the key in STRIPE_SECRET_KEY; after the Stripe account cutover, re-run it with the new account's key exported as STRIPE_SECRET_KEY.
# One-off setup: the Stripe coupon behind Buddy's 20% codes (docs/designs/buddy-coupon.md). Runs inside Modal so the
# Stripe key stays in the Modal environment and is never printed; prints only the non-secret coupon id and counts.
#
# Usage (from backend/):  modal run setup_buddy_coupon.py              # create it (a re-run reports it exists)
#                         modal run setup_buddy_coupon.py --deactivate  # turn every unredeemed code off at once
#
# The coupon: 20% off, once, on any product (Ben, 2026-11-04: every product), and at most 100 redemptions in all,
# so the most it can ever take off is bounded whatever happens to the codes. Each code is its own single-use
# promotion code minted by app.py (_mint_buddy_code).
import modal

app = modal.App("purplelink-buddy-coupon-setup")
stripe_secret = modal.Secret.from_name("stripe-secret")
COUPON_ID = "buddy-20"


@app.function(image=modal.Image.debian_slim().pip_install("httpx"), secrets=[stripe_secret])
def setup(deactivate: bool = False):
    import os
    import httpx

    key = os.environ["STRIPE_SECRET_KEY"]
    if deactivate:
        n, starting_after = 0, None
        while True:
            params = {"coupon": COUPON_ID, "active": "true", "limit": "100"}
            if starting_after:
                params["starting_after"] = starting_after
            page = httpx.get("https://api.stripe.com/v1/promotion_codes", auth=(key, ""), params=params).json()
            for pc in page.get("data", []):
                httpx.post(f"https://api.stripe.com/v1/promotion_codes/{pc['id']}", auth=(key, ""),
                           data={"active": "false"}).raise_for_status()
                n += 1
            if not page.get("has_more"):
                break
            starting_after = page["data"][-1]["id"]
        print(f"Deactivated {n} promotion codes on {COUPON_ID}")
        return
    resp = httpx.post("https://api.stripe.com/v1/coupons", auth=(key, ""), data={
        "id": COUPON_ID, "percent_off": "20", "duration": "once", "max_redemptions": "100",
        "name": "Buddy 20% code"})
    if resp.status_code == 400 and "already exists" in resp.text:
        print(f"Coupon already exists: {COUPON_ID}")
        return
    resp.raise_for_status()
    print(f"Created coupon: {resp.json()['id']} (live mode: {resp.json().get('livemode')})")


@app.local_entrypoint()
def main(deactivate: bool = False):
    setup.remote(deactivate)
