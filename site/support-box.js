// "Write to Ben": the support box on /support/ and the app pages. Posts to
// netlify/functions/support-message.mjs, which emails Ben with Reply-To set to
// the visitor. Without JavaScript the form stays hidden and the mailto link
// beside it is the way in. Nothing typed here is stored in the browser.
(() => {
  const API = "/.netlify/functions/support-message";
  const MAIL = "ben@purplelink.llc";
  const MIN_FILL_MS = 3000;
  const MIN_MESSAGE = 10;
  const MAX_MESSAGE = 5000;
  const EMAIL = /^[^\s@<>(),;:"\\[\]]{1,64}@[^\s@<>(),;:"\\[\]]{1,190}\.[^\s@<>(),;:"\\[\]]{2,}$/;

  const COPY = {
    invalid_email: "Enter an email address Ben can reply to, such as you@example.org.",
    message_short: "Write at least 10 characters so there is something to answer.",
    message_long: "Keep the message under 5,000 characters.",
    invalid_topic: "Pick a topic from the list.",
    rate_limited: "Too many messages have come from this connection just now. Try again later, or email ",
    failed: "The message did not send. What you wrote is still here. Try again, or email ",
  };

  const wire = (box) => {
    const form = box.querySelector("form");
    const status = box.querySelector("[data-sb-status]");
    if (!form || !status) return;
    const email = form.elements.email;
    const message = form.elements.message;
    const topicSelect = form.elements.topic;
    const btn = form.querySelector('button[type="submit"]');
    const label = btn.textContent;
    const errors = {
      email: box.querySelector("#sb-email-error"),
      message: box.querySelector("#sb-message-error"),
    };
    const rendered = Date.now();

    const mailLink = () => {
      const a = document.createElement("a");
      a.href = "mailto:" + MAIL;
      a.textContent = MAIL;
      return a;
    };
    const say = (text, isError, withMail) => {
      status.textContent = text;
      status.classList.toggle("is-error", !!isError);
      if (withMail) {
        status.appendChild(mailLink());
        status.appendChild(document.createTextNode("."));
      }
    };
    const fieldError = (name, text) => {
      const el = errors[name];
      const input = form.elements[name];
      if (!el) return;
      el.textContent = text;
      el.hidden = !text;
      if (text) input.setAttribute("aria-invalid", "true");
      else input.removeAttribute("aria-invalid");
    };
    const clearErrors = () => {
      fieldError("email", "");
      fieldError("message", "");
      say("");
    };
    const topic = () => (topicSelect ? topicSelect.value : box.dataset.supportTopic || "general");

    email.addEventListener("input", () => { fieldError("email", ""); });
    message.addEventListener("input", () => { fieldError("message", ""); });
    // Say a typed address is malformed when the visitor leaves the field, not after they have written the
    // message and pressed Send. An empty field is left alone until submit.
    email.addEventListener("blur", () => {
      const addr = email.value.trim();
      if (addr && (!EMAIL.test(addr) || addr.length > 254)) fieldError("email", COPY.invalid_email);
    });
    message.addEventListener("blur", () => {
      if (message.value.trim().length > MAX_MESSAGE) fieldError("message", COPY.message_long);
    });

    const done = () => {
      form.hidden = true;
      form.reset();
      say("Sent. Ben reads every message and replies by email.", false);
      box.classList.add("is-done");
      status.setAttribute("tabindex", "-1");
      status.focus({ preventScroll: true });
    };

    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      if (btn.disabled) return;
      clearErrors();
      const addr = email.value.trim();
      const text = message.value.trim();
      let first = null;
      if (!EMAIL.test(addr) || addr.length > 254) { fieldError("email", COPY.invalid_email); first = first || email; }
      if (text.length < MIN_MESSAGE) { fieldError("message", COPY.message_short); first = first || message; }
      else if (text.length > MAX_MESSAGE) { fieldError("message", COPY.message_long); first = first || message; }
      if (first) { first.focus(); return; }

      btn.disabled = true;
      btn.textContent = "Sending…";
      say("Sending your message…", false);
      try {
        // The server refuses a form sent within three seconds of showing. A fast
        // paste should not trip that, so wait out the rest of the time first.
        const wait = MIN_FILL_MS + 100 - (Date.now() - rendered);
        if (wait > 0) await new Promise((r) => setTimeout(r, wait));
        const r = await fetch(API, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            email: addr,
            message: text,
            topic: topic(),
            page: location.pathname,
            website: form.elements.website.value,
            t: Date.now() - rendered,
          }),
        });
        if (r.status === 204) { done(); return; }
        let code = "";
        try { code = (await r.json()).error || ""; } catch (_) { code = ""; }
        if (r.status === 429) say(COPY.rate_limited, true, true);
        else if (code === "invalid_email") { fieldError("email", COPY.invalid_email); email.focus(); }
        else if (code === "message_short" || code === "message_long") { fieldError("message", COPY[code]); message.focus(); }
        else if (code === "invalid_topic" && topicSelect) { say(COPY.invalid_topic, true); topicSelect.focus(); }
        else say(COPY.failed, true, true);
      } catch (_) {
        say(COPY.failed, true, true);
      } finally {
        btn.disabled = false;
        btn.textContent = label;
      }
    });

    form.hidden = false;
  };

  const start = () => document.querySelectorAll("[data-support-box]").forEach(wire);
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start);
  else start();
})();
