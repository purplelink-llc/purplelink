// Feedback page. A rating arrives in the URL from an email or the status
// page (?r=useful|partly|not_useful&p=product, plus s/k or t to mark a
// buyer) and is recorded on load, so one click counts. The comment and
// permission to quote are optional and update the same entry.
(() => {
  const API = "https://ben-ampel--purplelink-latextools-web.modal.run/feedback";
  const RATINGS = { useful: "Useful", partly: "Partly useful", not_useful: "Not useful" };
  const q = new URLSearchParams(location.search);
  const product = q.get("p") || "paper-review";
  const proof = { s: q.get("s") || "", k: q.get("k") || "", token: q.get("t") || "" };
  let rating = RATINGS[q.get("r")] ? q.get("r") : "";
  let id = "";
  // The link can carry a review token; keep it out of history once read.
  if (location.search) history.replaceState(null, "", location.pathname);

  const pick = document.getElementById("fb-pick");
  const done = document.getElementById("fb-done");
  const doneHead = document.getElementById("fb-done-head");
  const form = document.getElementById("fb-form");
  const status = document.getElementById("fb-status");
  const thanks = document.getElementById("fb-thanks");

  async function send(extra) {
    const body = Object.assign({ rating, product, id }, id ? {} : proof, extra || {});
    const r = await fetch(API, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    if (!r.ok) throw new Error(String(r.status));
    const data = await r.json();
    if (data.id) id = data.id;
  }

  async function record(value) {
    rating = value;
    pick.hidden = true;
    done.hidden = false;
    doneHead.textContent = "Recording your answer...";
    try {
      await send();
      doneHead.textContent = "Thank you. " + RATINGS[rating] + " is recorded.";
      form.hidden = false;
      if (window.plTrack) window.plTrack("feedback_rating", rating);
    } catch (e) {
      doneHead.textContent = "That didn't go through. Try again in a minute, or reply to the email instead.";
      pick.hidden = false;
    }
  }

  pick.querySelectorAll("button[data-rating]").forEach((b) => {
    b.addEventListener("click", () => record(b.dataset.rating));
  });
  if (rating) record(rating);

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    if (form.website.value) return;
    const comment = form.comment.value.trim();
    if (!comment) { status.textContent = "Write a sentence or two first, or close this page: the rating is already saved."; form.comment.focus(); return; }
    const btn = form.querySelector("button[type=submit]");
    btn.disabled = true;
    status.textContent = "Sending...";
    try {
      await send({ comment, quote_ok: form.quote_ok.checked, name: form.name.value.trim(), field: form.field.value.trim() });
      form.hidden = true;
      thanks.hidden = false;
      thanks.focus();
    } catch (err) {
      btn.disabled = false;
      status.textContent = "That didn't go through. Try again in a minute, or email ben@purplelink.llc.";
    }
  });
})();
