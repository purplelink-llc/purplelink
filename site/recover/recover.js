// Find a purchase: posts the checkout email to purchases-recover.mjs, which
// answers the same way for every address and emails only that address.
(() => {
  const form = document.getElementById("recover-form");
  const status = document.getElementById("recover-status");
  if (!form || !status) return;
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const email = form.email.value.trim();
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      status.textContent = "Enter the email address you used at checkout.";
      form.email.focus();
      return;
    }
    const btn = form.querySelector("button");
    btn.disabled = true;
    status.textContent = "Looking...";
    try {
      const r = await fetch("/.netlify/functions/purchases-recover", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email }),
      });
      const body = await r.json().catch(() => ({}));
      if (r.ok) {
        status.textContent = `If ${email} made a ModernTex or kit purchase, the details are on their way to it now.`;
      } else {
        status.textContent = body.detail || "That didn't go through. Try again, or email ben@purplelink.llc.";
        btn.disabled = false;
      }
    } catch (_) {
      status.textContent = "That didn't go through. Try again, or email ben@purplelink.llc.";
      btn.disabled = false;
    }
  });
})();
