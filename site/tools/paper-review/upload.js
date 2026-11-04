// Paper Review upload page logic.
//
// Steps:
//   1. Redeem the Stripe session_id for a token + product config.
//   2. Show the upload form. For tiers that bundled the Journal Pack,
//      load the journal list for the chosen domain and reveal the picker.
//      For tiers that bundled Anonymity Check, show the (already-ticked)
//      anonymity checkbox.
//   3. POST PDF + token + domain + optional journal + anonymity + email to
//      /paper-review/submit, then redirect to the status page.
(function () {
  var MAX_PDF_BYTES = 20 * 1024 * 1024;
  var redeemEl = document.getElementById("redeem-status");
  var formEl = document.getElementById("upload-form");
  var nameEl = document.getElementById("filename");
  var submitBtn = document.getElementById("submit-btn");
  var statusEl = document.getElementById("status");
  var journalWrap = document.getElementById("journal-picker-wrap");
  var journalSelect = document.getElementById("journal-select");
  var journalErrorEl = document.getElementById("journal-error");
  var anonymityWrap = document.getElementById("anonymity-wrap");
  var emailField = document.getElementById("email-field");
  var reportGroup = document.getElementById("report-address-group");
  var reportEmail = document.getElementById("report-email");
  var reportEcho = document.getElementById("report-email-echo");
  var reportError = document.getElementById("report-email-error");
  var overrideGroup = document.getElementById("email-override-group");
  var retryWrap = document.getElementById("redeem-retry");
  var retryBtn = document.getElementById("redeem-retry-btn");
  var resumeEl = document.getElementById("pr-resume");
  var REDEEM_WINDOW_MS = 90000;
  var STATUS_KEY = "pl_pr_status";
  var EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  var reportRequired = false;

  var chosen = null;
  var token = null;
  var journalListFailed = false;
  var productConfig = { category: "paper-review", bundled_anonymity: false, bundled_journal: false };

  function setRedeemStatus(msg, isError, linkHref, linkText) {
    if (!redeemEl) return;
    redeemEl.hidden = false;
    redeemEl.textContent = msg;
    redeemEl.classList.toggle("error", !!isError);
    if (linkHref) {
      redeemEl.appendChild(document.createTextNode(" "));
      var a = document.createElement("a");
      a.href = linkHref;
      a.textContent = linkText || "Open the status page";
      redeemEl.appendChild(a);
    }
  }

  function statusPageUrl(t) {
    return "/tools/paper-review/status/?token=" + encodeURIComponent(t);
  }

  // Only ever follow a status link that stays on this site.
  function safeStatusUrl(u) {
    return typeof u === "string" && /^\/tools\/paper-review\/status\/\?token=[^&#\s]+$/.test(u) ? u : "";
  }

  // The status address is kept so the landing and upload pages can offer a
  // way back until the report has been opened (status.js clears it then).
  function saveStatusUrl(u) {
    try { localStorage.setItem(STATUS_KEY, JSON.stringify({ url: u, at: Date.now() })); } catch (e) { /* storage blocked */ }
  }
  function savedStatusUrl() {
    try {
      var v = JSON.parse(localStorage.getItem(STATUS_KEY) || "null");
      if (v && v.url && Date.now() - v.at < 86400000) return safeStatusUrl(v.url);
    } catch (e) { /* storage blocked or bad value */ }
    return "";
  }
  (function showResume() {
    var u = savedStatusUrl();
    if (!u || !resumeEl) return;
    var a = resumeEl.querySelector("a");
    if (a) a.href = u;
    resumeEl.hidden = false;
  })();

  function getSessionId() {
    return new URLSearchParams(window.location.search).get("session_id");
  }

  function getDirectToken() {
    return new URLSearchParams(window.location.search).get("direct_token");
  }

  // Shares the pl_prefs store that site.js uses for data-remember controls.
  function readPref(k) {
    try { return (JSON.parse(localStorage.getItem("pl_prefs") || "{}") || {})[k] || ""; } catch (e) { return ""; }
  }
  function writePref(k, v) {
    try {
      var p = JSON.parse(localStorage.getItem("pl_prefs") || "{}") || {};
      p[k] = v;
      localStorage.setItem("pl_prefs", JSON.stringify(p));
    } catch (e) { /* storage blocked: nothing to remember */ }
  }
  if (journalSelect) {
    journalSelect.addEventListener("change", function () { if (journalSelect.value) writePref("pr-journal", journalSelect.value); });
  }

  function loadJournalList(domain) {
    if (!journalSelect) return;
    journalListFailed = false;
    setJournalError("");
    journalSelect.disabled = true;
    journalSelect.innerHTML = '<option value="">Loading journals…</option>';
    fetch(API_BASE + "/paper-review/journals?domain=" + encodeURIComponent(domain))
      .then(function (resp) {
        if (!resp.ok) throw new Error("HTTP " + resp.status);
        return resp.json();
      })
      .then(function (data) {
        var opts = (data && data.journals) || [];
        journalSelect.innerHTML = '<option value="">— pick a journal —</option>';
        opts.forEach(function (j) {
          var o = document.createElement("option");
          o.value = j.key;
          o.textContent = j.name + (j.domain && j.domain !== "general" ? " · " + j.domain.replace("_", " ") : "");
          journalSelect.appendChild(o);
        });
        // Preselect the journal from ?journal= or the one chosen last time.
        var wanted = new URLSearchParams(window.location.search).get("journal") || readPref("pr-journal");
        if (wanted && opts.some(function (j) { return j.key === wanted; })) journalSelect.value = wanted;
        journalSelect.disabled = false;
        journalListFailed = false;
        setJournalError("");
        updateSubmit();
      })
      .catch(function () {
        journalListFailed = true;
        journalSelect.innerHTML = '<option value="">— journal list unavailable —</option>';
        journalSelect.disabled = true;
        setJournalError('Could not load the journal list. Your plan includes journal-compliance checking, so this is required. <button type="button" class="pr-retry-link" id="journal-retry-btn">Retry</button>');
        var retryBtn = document.getElementById("journal-retry-btn");
        if (retryBtn) {
          retryBtn.addEventListener("click", function () { loadJournalList(domain); });
        }
        updateSubmit();
      });
  }

  function setJournalError(html) {
    if (!journalErrorEl) return;
    journalErrorEl.innerHTML = html;
    journalErrorEl.hidden = !html;
  }

  function showForm() {
    if (formEl) formEl.hidden = false;
    if (redeemEl) redeemEl.hidden = true;
    if (productConfig.bundled_journal && journalWrap) {
      journalWrap.hidden = false;
      var domain = (document.querySelector('input[name="domain"]:checked') || {}).value || "general";
      loadJournalList(domain);
    }
    if (productConfig.bundled_anonymity && anonymityWrap) {
      anonymityWrap.hidden = false;
    }
    if (reportRequired && reportGroup) {
      reportGroup.hidden = false;
      if (overrideGroup) overrideGroup.hidden = true;
      var moreOpts = document.getElementById("more-options");
      if (moreOpts && getDirectToken()) moreOpts.hidden = true;
    }
    document.querySelectorAll('input[name="domain"]').forEach(function (input) {
      input.addEventListener("change", function () {
        if (productConfig.bundled_journal) {
          loadJournalList(input.value);
        }
      });
    });
  }

  function redeem(requestBody, startedAt, attempt) {
    startedAt = startedAt || Date.now();
    attempt = attempt || 1;
    if (retryWrap) retryWrap.hidden = true;
    fetch(API_BASE + "/paper-review/redeem-session", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(requestBody),
    })
      .then(function (resp) {
        if (resp.status === 404) {
          if (Date.now() - startedAt < REDEEM_WINDOW_MS) {
            // Back off from 2 s towards 6 s so a slow webhook is not hammered.
            var delay = Math.min(6000, Math.round(2000 * Math.pow(1.25, attempt - 1)));
            setRedeemStatus("Confirming your payment. This usually takes a few seconds.", false);
            setTimeout(function () { redeem(requestBody, startedAt, attempt + 1); }, delay);
            return null;
          }
          if (typeof window.plTrack === "function") {
            window.plTrack("redeem_timeout", requestBody.token ? "token" : "session");
          }
          setRedeemStatus("We have not received confirmation of your payment yet. If you have paid, it can still arrive: check again in a minute, or open the \"link to start\" email we sent to the address you paid with. Still stuck? Email ben@purplelink.llc with your Stripe receipt; there is no need to pay again.", true);
          if (retryWrap) retryWrap.hidden = false;
          return null;
        }
        if (resp.status === 409) {
          return resp.json().catch(function () { return {}; }).then(function (p) {
            throw {
              detail: (p && p.detail) || "A review was already started with this link.",
              status_url: safeStatusUrl(p && p.status_url) || (requestBody.token ? statusPageUrl(requestBody.token) : ""),
            };
          });
        }
        if (!resp.ok) return resp.json().then(function (p) { throw p; });
        return resp.json();
      })
      .then(function (data) {
        if (!data) return;
        if (!data.token) throw { detail: "No token returned." };
        token = data.token;
        productConfig = {
          category: data.category || "paper-review",
          bundled_anonymity: !!data.bundled_anonymity,
          bundled_journal: !!data.bundled_journal,
          tier: data.tier || "standard",
          product: data.product || "",
        };
        if (productConfig.category !== "paper-review") {
          setRedeemStatus("Your token is for a different product (" + productConfig.category + "). Open that product's upload page.", true);
          return;
        }
        reportRequired = !!getDirectToken() || /pack|annual/.test(productConfig.product);
        setRedeemStatus("Payment verified. Upload your manuscript below.", false);
        showForm();
      })
      .catch(function (err) {
        var href = err && err.status_url;
        setRedeemStatus((err && err.detail) || "Could not redeem your payment.", true, href, "Open the status page");
      });
  }

  if (retryBtn) {
    retryBtn.addEventListener("click", function () {
      setRedeemStatus("Checking again. This usually takes a few seconds.", false);
      if (directToken) redeem({ token: directToken }); else if (sessionId) redeem({ session_id: sessionId });
    });
  }

  function validPdf(file) {
    var lower = file.name.toLowerCase();
    if (!lower.endsWith(".pdf") && !lower.endsWith(".docx")) {
      statusEl.textContent = "Please choose a PDF or a Word (.docx) file."; return false;
    }
    if (file.size === 0) { statusEl.textContent = "That file is empty."; return false; }
    if (file.size > MAX_PDF_BYTES) {
      statusEl.textContent = "File is too large (max 20 MB)."; return false;
    }
    return true;
  }

  function updateSubmit() {
    var journalBlocked = productConfig.bundled_journal && journalListFailed;
    submitBtn.disabled = !(chosen && token) || journalBlocked;
  }

  wireDropzone("dropzone", "file", function (f) {
    if (!validPdf(f)) {
      chosen = null; nameEl.textContent = ""; updateSubmit(); return;
    }
    chosen = f;
    nameEl.textContent = f.name + " (" + Math.round(f.size / 1024) + " KB)";
    statusEl.textContent = "";
    updateSubmit();
  });

  submitBtn.addEventListener("click", function () {
    if (!chosen || !token) return;
    var domain = (document.querySelector('input[name="domain"]:checked') || {}).value || "general";
    var address = "";
    if (reportRequired && reportEmail) {
      address = reportEmail.value.trim();
      if (!EMAIL_RE.test(address)) {
        setReportError("Enter the address where the report should be sent.");
        reportEmail.focus();
        return;
      }
      setReportError("");
    } else if (emailField && emailField.value) {
      address = emailField.value.trim();
    }
    if (productConfig.bundled_journal && journalSelect && !journalSelect.value &&
        !window.confirm("You have not chosen a journal, so the journal compliance check will be skipped. Submit without one?")) {
      journalSelect.focus();
      return;
    }
    var fd = new FormData();
    fd.append("token", token);
    fd.append("domain", domain);
    fd.append("file", chosen, chosen.name);
    if (productConfig.bundled_journal && journalSelect && journalSelect.value) {
      fd.append("journal_key", journalSelect.value);
    }
    var anonymityToggle = document.getElementById("anonymity-toggle");
    if (productConfig.bundled_anonymity && anonymityToggle && anonymityToggle.checked) {
      fd.append("anonymity_check", "true");
    }
    if (address) fd.append("email", address);
    var remind = document.querySelector('input[name="remind_weeks"]:checked');
    if (remind && remind.value) {
      fd.append("remind_weeks", remind.value);
    }

    submitBtn.disabled = true;
    statusEl.innerHTML = '<span class="tool-spinner" aria-hidden="true"></span>Uploading and starting your review…';

    fetch(API_BASE + "/paper-review/submit", { method: "POST", body: fd })
      .then(function (resp) {
        if (!resp.ok) {
          return resp.text().then(function (text) {
            var parsed = null;
            try { parsed = JSON.parse(text); } catch (e) { /* non-JSON error body */ }
            var err = { httpStatus: resp.status };
            if (resp.status === 409) {
              err.status_url = safeStatusUrl(parsed && parsed.status_url) || statusPageUrl(token);
            } else if (resp.status === 410) {
              err.detail = "This link has expired. Email ben@purplelink.llc with your Stripe receipt and we will send you a new one. There is no need to pay again.";
            } else if (resp.status === 429) {
              err.detail = "Too many attempts in a short time. Wait a minute, then submit again.";
            } else if (parsed && parsed.detail) {
              err.detail = parsed.detail;
            } else {
              err.detail = "Upload failed (HTTP " + resp.status + "). Please try again.";
            }
            throw err;
          });
        }
        return resp.json();
      })
      .then(function (data) {
        if (!data || !data.token) throw { detail: "No status URL returned." };
        // Note: the Stripe session_id is intentionally NOT forwarded here.
        // It is a bearer credential for /paper-review/redeem-session (whoever
        // holds it can claim any unused tokens for that session), and the
        // status page never reads it, so carrying it into browser history /
        // Referer headers on this page would be pure unnecessary exposure.
        var url = statusPageUrl(data.token);
        saveStatusUrl(url);
        window.location.assign(url);
      })
      .catch(function (err) {
        // A 409 here means the review already started (a second click, a
        // second tab): the status page is where it can be followed.
        if (err && err.httpStatus === 409 && err.status_url) {
          saveStatusUrl(err.status_url);
          window.location.assign(err.status_url);
          return;
        }
        submitBtn.disabled = false;
        var msg = (err && err.detail) ? err.detail : "Upload failed. Please try again.";
        statusEl.innerHTML = '<span class="bib-err">' + escapeHtml(msg) + "</span>";
      });
  });

  function setReportError(msg) {
    if (!reportError) return;
    reportError.textContent = msg;
    reportError.hidden = !msg;
  }
  if (reportEmail && reportEcho) {
    reportEmail.addEventListener("input", function () {
      var v = reportEmail.value.trim();
      if (EMAIL_RE.test(v)) setReportError("");
      reportEcho.textContent = EMAIL_RE.test(v)
        ? "The report will be sent to " + v + "."
        : "The report is emailed to this address as a PDF when the review finishes.";
    });
  }

  var sessionId = getSessionId();
  var directToken = getDirectToken();
  // A token redeemed directly usually came from someone else's pack (a PI
  // handing one to a student). The decision reminder goes to whoever paid,
  // so don't offer it here.
  if (directToken) {
    var remindPick = document.querySelector(".pr-remind-pick");
    if (remindPick) remindPick.hidden = true;
  }
  if (directToken) {
    redeem({ token: directToken });
  } else if (sessionId) {
    redeem({ session_id: sessionId });
  } else {
    setRedeemStatus("We couldn't find a payment in this link; closing the tab while Stripe redirects can drop it. If you paid, open the email titled \"link to start\" that we sent to the address you paid with: it opens this page, ready to upload, on any device. Still stuck? Email ben@purplelink.llc with your Stripe receipt and we'll sort it out, with no need to pay again.", true);
    var tokenForm = document.getElementById("token-form");
    if (tokenForm) {
      tokenForm.hidden = false;
      tokenForm.addEventListener("submit", function (e) {
        e.preventDefault();
        var t = (document.getElementById("token-input").value || "").trim();
        if (!t) return;
        window.location.search = "?direct_token=" + encodeURIComponent(t);
      });
    }
  }
})();
