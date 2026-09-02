# Detecting checkout without a click handler

The kits page drew 24 visitors in August. Stripe showed no checkout sessions in the same window. I had no instrumentation between those two facts, so I couldn't tell whether people saw the price and left or something between the button and Stripe failed. Both look identical from outside.

The analytics beacon was already watching for fetch calls. When someone runs the anonymity checker or the BibTeX validator, the tool fires a POST to the tools backend; the beacon intercepts it and logs a run event. Checkout turned out to have the same structure. Every buy button on the site posts to the same endpoint: `/.netlify/functions/checkout`. Kits, Paper Review tiers, the packs page, all of them.

This was originally a decision about maintenance: one checkout function to update instead of product-specific handlers. The side effect is that a single fetch interceptor covers the whole site. When the beacon sees a POST to that URL, it logs a checkoutClick and reads the product key from the request body. New products added to the catalog later appear in tracking automatically. There are no onclick handlers, no per-button code, no per-page scripts.

What this produces is a checkout rate: product page views divided by checkout POSTs. Stripe separately records whether a session completed. Those are two different numbers and two different failure modes. No clicks despite page views means something about the product page isn't converting. Clicks without a Stripe session means the function itself broke. Collapsing them into one metric would make it harder to know which is happening.

Click tracking, between page load and button press, would answer a different question: scroll depth, whether the buy button is even visible without scrolling, where exactly people leave the page. I left it out. It would require page-specific scripts rather than a shared interceptor, and the problem I was diagnosing lived at the checkout boundary. That other question can wait.

The diagnostic value: if Stripe shows zero sessions but analytics shows clicks, the checkout function is broken. If both show nothing, the product page is the problem. If analytics shows nothing but Stripe shows sessions, the beacon itself broke. You can only separate these cases when something watches the boundary between them.

As of September, the clicks are landing and Stripe sessions are completing. The gap I feared, a broken button sitting silently on a page with real visitors, turned out not to exist. But without the measurement, I wouldn't have known that.

## LinkedIn Post

The kits page had 24 visitors in August. Stripe showed zero checkout sessions. I had no way to tell if the button was even working.

The analytics beacon already intercepted fetch calls for tool runs. Checkout uses the same structure: every buy button on the site posts to one endpoint. So one extension to the fetch interceptor covered all of them. The product key comes from the request body, so breakdown by product is automatic. No per-button code, no per-page scripts.

What this gave me is two separate numbers: checkout clicks and completed Stripe sessions. No clicks despite page views means the product page isn't converting. Clicks without a session means the checkout function broke. Without something sitting at the boundary, both scenarios look identical from the outside.

The button was working, as it turned out. But I wouldn't have known that.

https://purplelink.llc/blog/detecting-checkout-without-a-click-handler/
