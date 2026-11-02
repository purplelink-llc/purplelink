// Undershelf waitlist: posts the address and the version the reader would buy. Double opt-in on the server
// (undershelf-waitlist.mjs, same pattern as checklist-signup.mjs): nothing is kept until the email link is clicked.
(() => {
  const API = "/.netlify/functions/undershelf-waitlist";
  const EMAIL = /^[^\s@]{1,64}@[^\s@]{1,190}\.[^\s@]{2,}$/;
  const box = document.querySelector("[data-undershelf-waitlist]");
  if (!box) return;
  const form = box.querySelector("form");
  const status = box.querySelector("[data-list-signup-status]");
  const btn = form.querySelector('button[type="submit"]');
  const say = (text, isError) => {
    status.textContent = text;
    status.classList.toggle("is-error", !!isError);
  };
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const data = new FormData(form);
    const email = String(data.get("email") || "").trim();
    if (!EMAIL.test(email)) {
      say("That email address does not look right.", true);
      return;
    }
    btn.disabled = true;
    say("Sending…");
    try {
      const res = await fetch(API, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, version: data.get("version"), website: data.get("website"), page: location.pathname }),
      });
      const body = await res.json().catch(() => ({}));
      if (res.ok && body.ok) {
        form.remove();
        say(body.already ? "You are already on the list." : "Check your email and click the link to confirm.");
      } else if (res.status === 429) {
        say("Too many tries today. Please try again tomorrow.", true);
      } else {
        say("That did not go through. Please try again.", true);
      }
    } catch (_) {
      say("No connection. Please try again.", true);
    } finally {
      btn.disabled = false;
    }
  });
})();
