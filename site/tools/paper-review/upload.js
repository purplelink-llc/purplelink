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

  var chosen = null;
  var token = null;
  var journalListFailed = false;
  var productConfig = { category: "paper-review", bundled_anonymity: false, bundled_journal: false };

  function setRedeemStatus(msg, isError) {
    if (!redeemEl) return;
    redeemEl.textContent = msg;
    redeemEl.classList.toggle("error", !!isError);
  }

  function getSessionId() {
    return new URLSearchParams(window.location.search).get("session_id");
  }

  function getDirectToken() {
    return new URLSearchParams(window.location.search).get("direct_token");
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
    document.querySelectorAll('input[name="domain"]').forEach(function (input) {
      input.addEventListener("change", function () {
        if (productConfig.bundled_journal) {
          loadJournalList(input.value);
        }
      });
    });
  }

  function redeem(requestBody, attempt) {
    attempt = attempt || 1;
    fetch(API_BASE + "/paper-review/redeem-session", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(requestBody),
    })
      .then(function (resp) {
        if (resp.status === 404) {
          if (attempt < 15) {
            setRedeemStatus("Waiting on payment confirmation… (retry " + attempt + ")", false);
            setTimeout(function () { redeem(requestBody, attempt + 1); }, 2000);
            return null;
          }
          throw { detail: "Payment confirmation didn't arrive. Email ben@purplelink.llc with your Stripe receipt." };
        }
        if (resp.status === 409) {
          throw { detail: "This token has already been used. Use another token from your pack, or check its status if you already started a review." };
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
        };
        if (productConfig.category !== "paper-review") {
          setRedeemStatus("Your token is for a different product (" + productConfig.category + "). Open that product's upload page.", true);
          return;
        }
        setRedeemStatus("Payment verified. Upload your manuscript below.", false);
        showForm();
      })
      .catch(function (err) {
        setRedeemStatus((err && err.detail) || "Could not redeem your payment.", true);
      });
  }

  function validPdf(file) {
    if (!file.name.toLowerCase().endsWith(".pdf")) {
      statusEl.textContent = "Please choose a PDF file."; return false;
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
    if (emailField && emailField.value) {
      fd.append("email", emailField.value.trim());
    }

    submitBtn.disabled = true;
    statusEl.innerHTML = '<span class="tool-spinner" aria-hidden="true"></span>Uploading and starting your review…';

    fetch(API_BASE + "/paper-review/submit", { method: "POST", body: fd })
      .then(function (resp) {
        if (!resp.ok) {
          return resp.text().then(function (text) {
            var parsed = null;
            try { parsed = JSON.parse(text); } catch (e) { /* non-JSON error body */ }
            if (parsed && parsed.detail) throw parsed;
            throw { detail: "Upload failed (HTTP " + resp.status + "). Please try again." };
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
        var url = "/tools/paper-review/status/?token=" + encodeURIComponent(data.token);
        window.location.assign(url);
      })
      .catch(function (err) {
        submitBtn.disabled = false;
        var msg = (err && err.detail) ? err.detail : "Upload failed. Please try again.";
        statusEl.innerHTML = '<span class="bib-err">' + escapeHtml(msg) + "</span>";
      });
  });

  var sessionId = getSessionId();
  var directToken = getDirectToken();
  if (directToken) {
    redeem({ token: directToken });
  } else if (sessionId) {
    redeem({ session_id: sessionId });
  } else {
    setRedeemStatus("We couldn't find a payment session in this link. If you just paid, go back to your Stripe confirmation email or receipt and click the link there again — closing the tab mid-redirect can drop this. If you already have a token from a previous purchase, add it to the URL as ?direct_token=YOUR_TOKEN. Still stuck? Email ben@purplelink.llc with your Stripe receipt and we'll sort it out — no need to pay again.", true);
  }
})();
