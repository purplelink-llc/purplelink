# One-off setup script — creates the live Stripe Price for the new
# Resume Review product ($5, one-time). Run via `modal run` so the secret
# key stays inside the Modal execution environment and is never printed
# to a local shell/log. Prints only the resulting (non-secret) price id.
#
# Usage (from backend/): modal run setup_resume_review_price.py
import modal

app = modal.App("purplelink-resume-review-setup")
stripe_secret = modal.Secret.from_name("stripe-secret")


@app.function(image=modal.Image.debian_slim().pip_install("httpx"), secrets=[stripe_secret])
def create_price():
    import os
    import httpx

    secret_key = os.environ["STRIPE_SECRET_KEY"]
    with httpx.Client() as client:
        product_resp = client.post(
            "https://api.stripe.com/v1/products",
            auth=(secret_key, ""),
            data={
                "name": "Resume Review",
                "description": "Three-persona AI panel (ATS Screener, Hiring Manager Skeptic, Recruiter Red Flags) critiques an uploaded resume.",
            },
        )
        product_resp.raise_for_status()
        product_id = product_resp.json()["id"]

        price_resp = client.post(
            "https://api.stripe.com/v1/prices",
            auth=(secret_key, ""),
            data={
                "product": product_id,
                "unit_amount": "500",
                "currency": "usd",
            },
        )
        price_resp.raise_for_status()
        price_id = price_resp.json()["id"]

    print(f"Created product: {product_id}")
    print(f"Created price: {price_id}")
    print("Set this as STRIPE_PRICE_RESUME_REVIEW in Netlify env vars.")
