# One-off setup script: a limited run of free Paper Review reviews for early users.
#
# Creates a 100%-off Stripe coupon that applies ONLY to the Stripe products you name, and one promotion code
# with a redemption cap and an expiry. Checkout already accepts promotion codes (allow_promotion_codes in
# netlify/functions/checkout.mjs). A 100%-off code that was not restricted to products would also discount
# ModernTex and the kits, so this script refuses to run without product ids.
#
# It runs on Modal so the live Stripe key stays in the Modal environment and is never printed locally.
#
# Step 1, list candidate products (read only, the default):
#     cd backend && modal run setup_early_reviewer_coupon.py
# Step 2, after checking the product ids it prints, create the code:
#     modal run setup_early_reviewer_coupon.py --create --product-ids prod_AAA,prod_BBB --code PRSTART --max-redemptions 20 --expires 2026-12-15
#
# Re-running with the same code is a no-op (Stripe rejects a duplicate promotion code).
# To end the program early, deactivate the promotion code in the Stripe dashboard.
import modal

app = modal.App("purplelink-early-reviewer-setup")
stripe_secret = modal.Secret.from_name("stripe-secret")
image = modal.Image.debian_slim().pip_install("httpx")


@app.function(image=image, secrets=[stripe_secret])
def run(create: bool, product_ids: str, code: str, max_redemptions: int, expires: str) -> None:
    import datetime
    import os
    import re

    import httpx

    key = os.environ["STRIPE_SECRET_KEY"]
    auth = (key, "")

    def get(path: str, params: dict | None = None) -> dict:
        r = httpx.get("https://api.stripe.com/v1/" + path, auth=auth, params=params or {}, timeout=30)
        r.raise_for_status()
        return r.json()

    if not create:
        print("Read-only listing of active products whose name mentions review. Pick the Paper Review ones.\n")
        found = {}
        for query in ('active:"true" AND name~"review"', 'active:"true" AND name~"Paper"'):
            for p in get("products/search", {"query": query, "limit": 50}).get("data", []):
                found[p["id"]] = p
        for p in sorted(found.values(), key=lambda x: x.get("name", "")):
            print(f"  {p['id']:<26} {p.get('name')}")
        print("\nThen run again with --create --product-ids <comma separated ids> --code CODE --max-redemptions N --expires YYYY-MM-DD")
        return

    ids = [i.strip() for i in product_ids.split(",") if i.strip()]
    if not ids or not all(re.fullmatch(r"prod_[A-Za-z0-9]+", i) for i in ids):
        raise SystemExit("--product-ids must be one or more Stripe product ids (prod_...). Refusing to create an unrestricted 100% coupon.")
    if not re.fullmatch(r"[A-Z0-9]{4,20}", code):
        raise SystemExit("--code must be 4 to 20 capital letters or digits.")
    if not 1 <= max_redemptions <= 50:
        raise SystemExit("--max-redemptions must be between 1 and 50.")
    expires_at = int(datetime.datetime.strptime(expires, "%Y-%m-%d").replace(tzinfo=datetime.timezone.utc).timestamp())
    if expires_at < datetime.datetime.now(datetime.timezone.utc).timestamp() + 86400:
        raise SystemExit("--expires must be at least a day in the future.")
    for pid in ids:
        get("products/" + pid)          # raises if the product does not exist

    coupon_id = f"early-reviewer-{code.lower()}"
    data = {"id": coupon_id, "percent_off": "100", "duration": "once", "max_redemptions": str(max_redemptions),
            "redeem_by": str(expires_at), "name": f"Early reviewer ({code}): free Paper Review"}
    for i, pid in enumerate(ids):
        data[f"applies_to[products][{i}]"] = pid
    r = httpx.post("https://api.stripe.com/v1/coupons", auth=auth, data=data, timeout=30)
    if r.status_code == 400 and "already exists" in r.text:
        print("Coupon already exists:", coupon_id)
    else:
        r.raise_for_status()
        print("Created coupon:", coupon_id)

    r = httpx.post("https://api.stripe.com/v1/promotion_codes", auth=auth, timeout=30, data={
        "coupon": coupon_id, "code": code, "max_redemptions": str(max_redemptions), "expires_at": str(expires_at),
        "restrictions[first_time_transaction]": "true"})
    if r.status_code == 400 and "already exists" in r.text.lower():
        print("Promotion code already exists:", code)
        return
    r.raise_for_status()
    print(f"Created promotion code {code}: {max_redemptions} redemptions, first-time customers only, expires {expires}.")


@app.local_entrypoint()
def main(create: bool = False, product_ids: str = "", code: str = "PRSTART", max_redemptions: int = 20, expires: str = "2026-12-15"):
    run.remote(create, product_ids, code, max_redemptions, expires)
