// Paper Review landing page: the free reference check.
//
// Posts the chosen PDF to POST /paper-review/preview and renders the counts
// and up to three findings it returns. The endpoint runs no AI: it reads the
// reference list, checks it against CrossRef, scans for anonymity leftovers
// and discards the file. Everything from the response is written with
// textContent, never innerHTML, because the quotes are manuscript text.
(function () {
  var form = document.getElementById("pr-preview-form");
  var fileInput = document.getElementById("pr-preview-file");
  var button = document.getElementById("pr-preview-btn");
  var statusEl = document.getElementById("pr-preview-status");
  var results = document.getElementById("pr-preview-results");
  if (!form || !fileInput || !button || !statusEl || !results) return;

  var BASE = (typeof API_BASE === "string" && API_BASE) || "https://ben-ampel--purplelink-latextools-web.modal.run";
  var MAX_BYTES = 20 * 1024 * 1024;
  var CLIENT_TIMEOUT_MS = 75000;
  var busy = false;

  function el(tag, className, text) {
    var node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined && text !== null) node.textContent = String(text);
    return node;
  }

  function setStatus(message, kind) {
    statusEl.textContent = "";
    statusEl.classList.toggle("is-error", kind === "error");
    if (kind === "busy") {
      var spinner = el("span", "tool-spinner");
      spinner.setAttribute("aria-hidden", "true");
      statusEl.appendChild(spinner);
    }
    statusEl.appendChild(document.createTextNode(message || ""));
  }

  function setBusy(on) {
    busy = on;
    button.disabled = on;
    button.textContent = on ? "Checking" : "Check";
    form.setAttribute("aria-busy", on ? "true" : "false");
  }

  function plural(n, one, many) {
    return n + " " + (n === 1 ? one : many);
  }

  function countCard(label, value) {
    var wrap = el("div", "pr-preview-count");
    wrap.appendChild(el("dt", "", label));
    wrap.appendChild(el("dd", "", value));
    return wrap;
  }

  function moreLine(more) {
    var parts = [];
    if (more.retracted) parts.push(plural(more.retracted, "more retracted paper", "more retracted papers"));
    if (more.concern) parts.push(plural(more.concern, "more paper with an expression of concern", "more papers with an expression of concern"));
    var unmatched = (more.reference_not_found || 0) + (more.dead_doi || 0);
    if (unmatched) parts.push(plural(unmatched, "more reference without a match", "more references without a match"));
    if (more.doi_mismatch) parts.push(plural(more.doi_mismatch, "more DOI that points to a different title", "more DOIs that point to a different title"));
    if (more.weak_match) parts.push(plural(more.weak_match, "more partial match", "more partial matches"));
    if (more.anonymity) parts.push(plural(more.anonymity, "more anonymity leftover", "more anonymity leftovers"));
    return parts.length ? "Not shown here: " + parts.join(", ") + "." : "";
  }

  function startReviewLabel() {
    var checkout = document.getElementById("checkout-btn");
    return (checkout && checkout.textContent.trim()) || "Start a review";
  }

  function render(data) {
    var counts = data.counts || {};
    var findings = Array.isArray(data.findings) ? data.findings.slice(0, 3) : [];
    results.textContent = "";

    var dl = el("dl", "pr-preview-counts");
    dl.appendChild(countCard("References found", counts.references_found || 0));
    dl.appendChild(countCard("Confirmed by CrossRef", counts.verified || 0));
    dl.appendChild(countCard("Partial matches", counts.weak_matches || 0));
    dl.appendChild(countCard("No match", (counts.not_found || 0) + (counts.doi_mismatches || 0)));
    if (counts.retracted) dl.appendChild(countCard("Retracted", counts.retracted));
    results.appendChild(dl);

    if (counts.unchecked) {
      results.appendChild(el("p", "pr-preview-note",
        plural(counts.unchecked, "reference was", "references were") +
        " not checked: preprints and web pages are not in CrossRef, and some lookups get no answer."));
    }
    (data.notes || []).forEach(function (note) {
      results.appendChild(el("p", "pr-preview-note", note));
    });

    if (findings.length) {
      var list = el("ol", "pr-preview-findings");
      findings.forEach(function (f) {
        var item = el("li", "pr-preview-finding");
        var heading = el("h3", "", f.label || "Finding");
        if (f.page) {
          heading.appendChild(document.createTextNode(" "));
          heading.appendChild(el("span", "pr-preview-where", "page " + f.page));
        }
        item.appendChild(heading);
        if (f.quote) item.appendChild(el("blockquote", "pr-preview-quote", f.quote));
        if (f.detail) item.appendChild(el("p", "pr-preview-detail", f.detail));
        list.appendChild(item);
      });
      results.appendChild(list);
    } else {
      results.appendChild(el("p", "pr-preview-note", "This check found no reference or anonymity problems to show."));
    }

    var more = moreLine(data.more || {});
    if (more) results.appendChild(el("p", "pr-preview-note", more));

    var upsell = el("div", "pr-preview-upsell");
    upsell.appendChild(el("p", "", "The full review adds four reviewers on methods, statistics and claims"));
    var start = el("button", "btn btn-primary", startReviewLabel());
    start.type = "button";
    start.id = "pr-preview-start";
    start.addEventListener("click", function () {
      var checkout = document.getElementById("checkout-btn");
      if (checkout) checkout.click();
    });
    upsell.appendChild(start);
    results.appendChild(upsell);

    results.hidden = false;
    results.focus({ preventScroll: true });
  }

  // The checkout button's label follows the chosen tier; keep the copy in
  // the results in step with it.
  document.addEventListener("change", function (event) {
    if (!event.target || event.target.name !== "tier") return;
    var start = document.getElementById("pr-preview-start");
    if (start) start.textContent = startReviewLabel();
  });

  var FALLBACK_ERROR = "The free check could not be completed. Please try again in a minute.";

  form.addEventListener("submit", function (event) {
    event.preventDefault();
    if (busy) return;
    var file = fileInput.files && fileInput.files[0];
    if (!file) {
      setStatus("Choose a PDF or Word file first.", "error");
      fileInput.focus();
      return;
    }
    if (!/\.(pdf|docx)$/i.test(file.name)) {
      setStatus("The file must be a PDF or a Word (.docx) file.", "error");
      return;
    }
    if (file.size > MAX_BYTES) {
      setStatus("That file is over 20 MB. Compress it or export it again and retry.", "error");
      return;
    }

    results.hidden = true;
    setBusy(true);
    setStatus("Checking the reference list against CrossRef. This can take up to a minute.", "busy");

    var body = new FormData();
    body.append("file", file, file.name);
    var controller = typeof AbortController === "function" ? new AbortController() : null;
    var timer = setTimeout(function () { if (controller) controller.abort(); }, CLIENT_TIMEOUT_MS);

    fetch(BASE + "/paper-review/preview", { method: "POST", body: body, signal: controller ? controller.signal : undefined })
      .then(function (resp) {
        return resp.json().catch(function () { return null; }).then(function (data) {
          if (!resp.ok || !data || data.status !== "ok") {
            throw { detail: (data && data.detail) || FALLBACK_ERROR };
          }
          return data;
        });
      })
      .then(function (data) {
        var counts = data.counts || {};
        setStatus("Checked " + plural(counts.references_found || 0, "reference", "references") +
          " across " + plural(data.pages || 0, "page", "pages") + ". The file has been discarded.");
        render(data);
      })
      .catch(function (err) {
        setStatus((err && err.detail) || FALLBACK_ERROR, "error");
      })
      .then(function () {
        clearTimeout(timer);
        setBusy(false);
      });
  });
})();
