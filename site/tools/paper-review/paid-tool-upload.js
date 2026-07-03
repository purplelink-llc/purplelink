// Shared upload-page helper for the adjacent paid tools.
//
// Each tool's upload page calls `setupPaidToolUpload({...})` with its
// product-specific shape. The helper handles:
//   - Redeeming the Stripe session_id for a token
//   - Verifying the product category matches the page's expected product
//   - Wiring the submit button (dropzone OR textarea inputs, per config)
//   - Redirecting to the status page on success
//
// Config shape:
//   {
//     productCategory: "cover-letter" | "anonymity-check" | "citation-gap" |
//                      "revision-review" | "response-review",
//     submitPath: "/cover-letter/submit",
//     fields: [
//       { type: "file"     | "text" | "textarea" | "email",
//         name: "abstract" | "title" | "journal_name" | ...,
//         elementId: "abstract-input",
//         required: true|false,
//         maxBytes: 20_000_000   // for files
//       },
//       ...
//     ],
//     extraValidate: function(values) { return null | "error message"; }
//   }
window.setupPaidToolUpload = function (cfg) {
  var redeemEl = document.getElementById("redeem-status");
  var formEl = document.getElementById("upload-form");
  var submitBtn = document.getElementById("submit-btn");
  var statusEl = document.getElementById("status");
  var token = null;
  var sessionId = new URLSearchParams(window.location.search).get("session_id");
  var submitted = false;
  var draftKey = "purplelink-draft:" + cfg.productCategory;

  // Autosave pasted textarea content to localStorage so an accidental tab
  // close / back-nav / nav-link click doesn't destroy a long paste. Text
  // fields only (files and Stripe tokens are never persisted).
  var textFields = cfg.fields.filter(function (f) { return f.type === "textarea" || f.type === "text"; });
  var requiredFileFields = cfg.fields.filter(function (f) { return f.type === "file" && f.required; });
  // Drafts (which may hold sensitive pasted manuscript/review text) are only
  // kept for a short window. Anything older is purged rather than restored.
  var DRAFT_TTL_MS = 48 * 60 * 60 * 1000; // 48h

  function saveDraft() {
    if (!textFields.length) return;
    try {
      var draft = { savedAt: Date.now(), fields: {} };
      var hasContent = false;
      textFields.forEach(function (f) {
        var el = document.getElementById(f.elementId);
        var v = el ? el.value : "";
        draft.fields[f.elementId] = v;
        if (v) hasContent = true;
      });
      if (hasContent) {
        window.localStorage.setItem(draftKey, JSON.stringify(draft));
      } else {
        window.localStorage.removeItem(draftKey);
      }
    } catch (e) { /* localStorage unavailable (private browsing, quota) — ignore */ }
  }

  function restoreDraft() {
    if (!textFields.length) return;
    try {
      var raw = window.localStorage.getItem(draftKey);
      if (!raw) return;
      var draft = JSON.parse(raw);
      // Legacy drafts (saved before the TTL field existed) and anything past
      // the TTL are purged rather than restored — they may hold sensitive
      // manuscript/review text that shouldn't linger in browser storage.
      var savedAt = typeof draft.savedAt === "number" ? draft.savedAt : 0;
      if (!savedAt || Date.now() - savedAt > DRAFT_TTL_MS) {
        window.localStorage.removeItem(draftKey);
        return;
      }
      var fields = draft.fields || {};
      var restoredAny = false;
      textFields.forEach(function (f) {
        var el = document.getElementById(f.elementId);
        if (el && fields[f.elementId]) {
          el.value = fields[f.elementId];
          restoredAny = true;
        }
      });
      if (restoredAny && statusEl) {
        var msg = "Restored your previously pasted text from this browser.";
        if (requiredFileFields.length) {
          msg += " Your file wasn't saved — please re-attach it before submitting.";
        }
        statusEl.textContent = msg;
      }
    } catch (e) { /* ignore malformed/unavailable storage */ }
  }

  function clearDraft() {
    try { window.localStorage.removeItem(draftKey); } catch (e) { /* ignore */ }
  }

  function hasUnsavedText() {
    return textFields.some(function (f) {
      var el = document.getElementById(f.elementId);
      return el && (el.value || "").trim().length > 0;
    });
  }

  window.addEventListener("beforeunload", function (e) {
    if (submitted) return;
    if (!hasUnsavedText()) return;
    e.preventDefault();
    e.returnValue = "";
    return "";
  });

  function setRedeemStatus(msg, isError) {
    if (!redeemEl) return;
    redeemEl.textContent = msg;
    redeemEl.classList.toggle("error", !!isError);
  }

  function showForm() {
    if (formEl) formEl.hidden = false;
    if (redeemEl) redeemEl.hidden = true;
    restoreDraft();
    updateSubmitEnabled();
  }

  function updateSubmitEnabled() {
    var ok = !!token;
    cfg.fields.forEach(function (f) {
      if (!f.required) return;
      var el = document.getElementById(f.elementId);
      if (!el) { ok = false; return; }
      if (f.type === "file") {
        if (!(el.files && el.files.length > 0)) ok = false;
      } else {
        if (!(el.value || "").trim()) ok = false;
      }
    });
    if (submitBtn) submitBtn.disabled = !ok;
  }

  var REDEEM_ERROR_MESSAGES = {
    already_used: "This link has already been used to submit. Check your email for the status link, or email ben@purplelink.llc if you need help.",
    all_used: "All tokens for this payment have already been redeemed. Check your email for the status link, or email ben@purplelink.llc if you need help.",
    expired: "This payment link has expired. Email ben@purplelink.llc with your Stripe receipt.",
    missing_session_id: "Missing payment session ID. Restart from the product page.",
  };

  function redeem(attempt) {
    attempt = attempt || 1;
    fetch(API_BASE + "/paper-review/redeem-session", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: sessionId }),
    })
      .then(function (resp) {
        if (resp.status === 404) {
          if (attempt < 15) {
            setRedeemStatus("Waiting on payment confirmation… (retry " + attempt + ")", false);
            setTimeout(function () { redeem(attempt + 1); }, 2000);
            return null;
          }
          throw { detail: "Payment confirmation didn't arrive. Email ben@purplelink.llc with your Stripe receipt." };
        }
        if (!resp.ok) return resp.json().then(function (p) { throw p; });
        return resp.json();
      })
      .then(function (data) {
        if (!data) return;
        if (!data.token) throw { detail: "No token returned." };
        if (data.category !== cfg.productCategory) {
          setRedeemStatus("Your token is for the " + data.category + " product, not " + cfg.productCategory + ". Open that product's upload page instead.", true);
          return;
        }
        token = data.token;
        setRedeemStatus("Payment verified. Fill in the form below.", false);
        showForm();
      })
      .catch(function (err) {
        var code = err && err.error;
        var msg = (err && err.detail) || (code && REDEEM_ERROR_MESSAGES[code]) || "Could not redeem your payment.";
        setRedeemStatus(msg, true);
      });
  }

  // Wire dropzone for the file field if there is one
  cfg.fields.forEach(function (f) {
    var el = document.getElementById(f.elementId);
    if (!el) return;
    if (f.type === "file") {
      // The page must include a #<dropzone-id> wrapping the input.
      var zoneId = f.elementId + "-zone";
      var nameEl = document.getElementById(f.elementId + "-name");
      wireDropzone(zoneId, f.elementId, function (fl) {
        if (f.maxBytes && fl.size > f.maxBytes) {
          statusEl.textContent = "File is too large (max " + (f.maxBytes / (1024 * 1024)) + " MB)."; return;
        }
        if (nameEl) nameEl.textContent = fl.name + " (" + Math.round(fl.size / 1024) + " KB)";
        statusEl.textContent = "";
        updateSubmitEnabled();
      });
    } else {
      el.addEventListener("input", updateSubmitEnabled);
      if (f.type === "textarea" || f.type === "text") {
        el.addEventListener("input", saveDraft);
      }
    }
  });

  submitBtn.addEventListener("click", function () {
    if (!token) return;
    var fd = new FormData();
    fd.append("token", token);

    var values = {};
    var failed = null;
    cfg.fields.forEach(function (f) {
      if (failed) return;
      var el = document.getElementById(f.elementId);
      if (!el) return;
      if (f.type === "file") {
        var fl = el.files && el.files[0];
        if (!fl && f.required) { failed = "Missing file: " + f.name; return; }
        if (fl) {
          fd.append(f.name, fl, fl.name);
          values[f.name] = fl;
        }
      } else {
        var v = (el.value || "").trim();
        if (!v && f.required) { failed = "Missing field: " + f.name; return; }
        if (v) {
          fd.append(f.name, v);
          values[f.name] = v;
        }
      }
    });

    if (!failed && cfg.extraValidate) failed = cfg.extraValidate(values);
    if (failed) {
      statusEl.innerHTML = '<span class="bib-err">' + escapeHtml(failed) + "</span>";
      return;
    }

    submitBtn.disabled = true;
    statusEl.innerHTML = '<span class="tool-spinner" aria-hidden="true"></span>Submitting…';

    fetch(API_BASE + cfg.submitPath, { method: "POST", body: fd })
      .then(function (resp) {
        if (!resp.ok) return resp.json().then(function (p) { throw p; });
        return resp.json();
      })
      .then(function (data) {
        if (!data || !data.token) throw { detail: "No status URL returned." };
        submitted = true;
        clearDraft();
        // Note: the Stripe session_id is intentionally NOT forwarded here.
        // It is a bearer credential for /paper-review/redeem-session (whoever
        // holds it can claim any unused tokens for that session), and the
        // status page never reads it, so carrying it into browser history /
        // Referer headers on this page would be pure unnecessary exposure.
        var url = "/tools/paper-review/status/?token=" + encodeURIComponent(data.token) + "&product=" + encodeURIComponent(cfg.productCategory);
        window.location.assign(url);
      })
      .catch(function (err) {
        submitBtn.disabled = false;
        var msg = (err && err.detail) ? err.detail : "Submit failed. Please try again.";
        statusEl.innerHTML = '<span class="bib-err">' + escapeHtml(msg) + "</span>";
      });
  });

  if (!sessionId) {
    setRedeemStatus("Missing payment session ID. Restart from the product page.", true);
    return;
  }
  redeem();
};
