// Paper Review status (polling) page.
//
// Reads ?token=… from the URL, polls GET /paper-review/status?token=… every
// 5 seconds, advances the progress bar, and on completion renders the
// Markdown report inline + offers a Markdown download.
//
// Includes a tiny zero-dependency Markdown renderer (headings, bold, code,
// inline code, ordered/unordered lists, blockquotes, paragraphs). Input is
// HTML-escaped first, so any model-injected HTML cannot reach the DOM.
(function () {
  var POLL_MS = 5000;
  var MAX_POLLS = 240;   // 240 * 5s = 20 minutes hard cap

  var progressFill = document.getElementById("progress-fill");
  var progressPct = document.getElementById("progress-pct");
  var stageLabel = document.getElementById("stage-label");
  var resultContainer = document.getElementById("result-container");
  var pageTitle = document.getElementById("page-title");
  var pageBlurb = document.getElementById("page-blurb");
  var progressWrap = document.getElementById("progress-wrap");

  var stageBoxNodes = [
    document.getElementById("stg-extract"),
    document.getElementById("stg-vision"),
    document.getElementById("stg-panel"),
    document.getElementById("stg-rect"),
  ];

  // Each paid product runs a different backend pipeline (see
  // adjacent_tool_pipeline in backend/app.py) and emits its own stage
  // strings. PRODUCT_STAGES maps product -> { order, labels, boxes } so the
  // shared status page (4-box stepper) reflects what is actually running
  // instead of Paper Review's Extract/Vision+Cite/Panel/Synthesise steps.
  // `order` lists the pipeline's stages in sequence (for the active/done
  // highlighting); `labels` is the STAGE_LABEL text shown under the bar;
  // `boxes` describes up to 4 stepper boxes: [stageKey, title, tag].
  var PRODUCT_STAGES = {
    "paper-review": {
      order: ["extracting", "vision", "citations", "panel", "rectifying", "done"],
      labels: {
        queued: "Queued…",
        extracting: "Extracting paper structure…",
        vision: "Scanning figures + verifying citations…",
        citations: "Verifying citations…",
        panel: "Running adversarial four-persona panel…",
        rectifying: "Synthesising the final report…",
        done: "Done.",
      },
      boxes: [
        ["extracting", "Extract", "Parse PDF"],
        ["vision", "Vision + Cite", "L1 + L2"],
        ["panel", "Panel", "4-persona debate"],
        ["rectifying", "Synthesise", "Final report"],
      ],
    },
    "response-review": {
      order: ["extracting", "panel", "rectifying", "done"],
      labels: {
        queued: "Queued…",
        extracting: "Extracting manuscript + comments…",
        panel: "Running skeptical + tone + editor panel…",
        rectifying: "Synthesising the final report…",
        done: "Done.",
      },
      boxes: [
        ["extracting", "Extract", "Parse PDF"],
        ["panel", "Panel", "3-persona review"],
        ["rectifying", "Synthesise", "Final report"],
        null,
      ],
    },
    "cover-letter": {
      order: ["queued", "drafting", "done"],
      labels: {
        queued: "Queued…",
        drafting: "Drafting your cover letter…",
        done: "Done.",
      },
      boxes: [
        ["queued", "Queue", "Read submission"],
        ["drafting", "Draft", "Write letter"],
        null,
        null,
      ],
    },
    "anonymity-check": {
      order: ["extracting", "analysing", "done"],
      labels: {
        queued: "Queued…",
        extracting: "Extracting paper structure…",
        analysing: "Scanning for identifying information…",
        done: "Done.",
      },
      boxes: [
        ["extracting", "Extract", "Parse PDF"],
        ["analysing", "Analyse", "Scan for identifiers"],
        null,
        null,
      ],
    },
    "citation-gap": {
      order: ["extracting", "analysing", "done"],
      labels: {
        queued: "Queued…",
        extracting: "Extracting paper structure…",
        analysing: "Checking citation coverage…",
        done: "Done.",
      },
      boxes: [
        ["extracting", "Extract", "Parse PDF"],
        ["analysing", "Analyse", "Check citation gaps"],
        null,
        null,
      ],
    },
    "revision-review": {
      order: ["extracting", "comparing", "done"],
      labels: {
        queued: "Queued…",
        extracting: "Extracting revised manuscript…",
        comparing: "Comparing against the prior review…",
        done: "Done.",
      },
      boxes: [
        ["extracting", "Extract", "Parse PDF"],
        ["comparing", "Compare", "Vs. prior review"],
        null,
        null,
      ],
    },
  };

  function getProduct() {
    var p = new URLSearchParams(window.location.search).get("product");
    return (p && PRODUCT_STAGES[p]) ? p : "paper-review";
  }

  var ACTIVE_PRODUCT = getProduct();
  var ACTIVE_CONFIG = PRODUCT_STAGES[ACTIVE_PRODUCT];
  var STAGE_LABEL = ACTIVE_CONFIG.labels;

  // Render this product's stepper boxes (label + tag) into the existing
  // 4-box DOM/CSS grid, hiding any unused trailing boxes.
  (function renderStageBoxes() {
    ACTIVE_CONFIG.boxes.forEach(function (box, i) {
      var node = stageBoxNodes[i];
      if (!node) return;
      if (!box) {
        node.style.display = "none";
        return;
      }
      node.dataset.stage = box[0];
      var titleEl = node.querySelector(".pr-stage-label");
      var tagEl = node.querySelector(".pr-stage-tag");
      if (titleEl) titleEl.textContent = box[1];
      if (tagEl) tagEl.textContent = box[2];
    });
  })();

  function setStage(stage) {
    var order = ACTIVE_CONFIG.order;
    var current = order.indexOf(stage) !== -1 ? stage : order[0];
    var currentIdx = order.indexOf(current);
    ACTIVE_CONFIG.boxes.forEach(function (box, i) {
      var node = stageBoxNodes[i];
      if (!node || !box) return;
      node.classList.remove("active", "done");
      var boxIdx = order.indexOf(box[0]);
      if (boxIdx === -1) return;
      if (boxIdx === currentIdx) {
        node.classList.add("active");
      } else if (boxIdx < currentIdx) {
        node.classList.add("done");
      }
    });
  }

  function setProgress(pct, stage) {
    pct = Math.max(0, Math.min(100, parseInt(pct || 0, 10)));
    progressFill.style.width = pct + "%";
    progressPct.textContent = pct + "%";
    stageLabel.textContent = STAGE_LABEL[stage] || stage || "Working…";
    setStage(stage || ACTIVE_CONFIG.order[0]);
  }

  function getToken() {
    return new URLSearchParams(window.location.search).get("token");
  }

  // Backend error codes are internal identifiers (snake_case tokens, or
  // "ExceptionName: message" from uncaught exceptions) — never meant for a
  // paying customer to read verbatim. Map the known ones to plain,
  // actionable language; anything unrecognised (including raw exception
  // strings) falls back to a generic message rather than leaking internals.
  var ERROR_MESSAGES = {
    no_reviewer_comments_parsed: "We couldn't find any reviewer comments in the text you pasted. Double-check the format (each reviewer's comments should be numbered or clearly separated) and try again.",
    synthesis_failed: "We extracted your documents but hit an error writing the final report.",
    empty_manuscript: "We couldn't read any text from the manuscript you uploaded. Make sure the PDF isn't a scanned image with no selectable text, then try again.",
  };

  function friendlyError(code) {
    code = String(code || "");
    if (ERROR_MESSAGES[code]) return ERROR_MESSAGES[code];
    var base = code.split(":")[0];
    if (ERROR_MESSAGES[base]) return ERROR_MESSAGES[base];
    if (/^extraction_failed\b/.test(code)) {
      return "We couldn't extract text from your PDF. Make sure it isn't a scanned image or password-protected, then try again.";
    }
    if (/^unknown_product\b/.test(code)) {
      return "Something went wrong routing your request to the right tool.";
    }
    // revision-review's "mismatch" outcome (pasted review has no
    // Rectification Checklist, or doesn't match the uploaded manuscript)
    // already carries a specific, actionable, backend-authored message —
    // the backend prefixes it with "revision_mismatch:" precisely so it can
    // be shown verbatim here instead of being swallowed by the generic
    // fallback below. showError() HTML-escapes this before rendering.
    if (base === "revision_mismatch") {
      return code.slice("revision_mismatch:".length) || "Something went wrong processing your review.";
    }
    return "Something went wrong processing your review.";
  }

  function showError(msg, replacementToken) {
    var html = '<div class="pr-error-box">' + escapeHtml(msg) +
      ' If this looks like our fault, email <a href="mailto:ben@purplelink.llc">ben@purplelink.llc</a> with the time and we will refund your payment.</div>';
    if (replacementToken) {
      html += '<div class="pr-error-box pr-replacement-box">' +
        '<strong>Good news: your payment was not lost.</strong> ' +
        'Your original token was already used when the crash happened, so we minted a fresh, unused one at no extra charge.';
      if (ACTIVE_PRODUCT === "paper-review") {
        // Only Paper Review's own upload page can redeem a token directly
        // via ?direct_token= without a Stripe session — see upload.js.
        var resubmitUrl = "/tools/paper-review/upload/?direct_token=" + encodeURIComponent(replacementToken);
        html += '<div class="pr-result-actions"><a class="btn btn-primary" href="' + escapeHtml(resubmitUrl) + '">Try again with your new token</a></div>';
      } else {
        html += ' Reply to <a href="mailto:ben@purplelink.llc?subject=Replacement%20token&body=' +
          encodeURIComponent("My review crashed. Replacement token: " + replacementToken) +
          '">ben@purplelink.llc</a> with this token and we will get your review resubmitted: <code>' +
          escapeHtml(replacementToken) + '</code>';
      }
      html += '</div>';
    }
    resultContainer.innerHTML = html;
    if (progressWrap) progressWrap.style.display = "none";
  }

  function base64ToBlob(b64, mime) {
    var binary = atob(b64);
    var bytes = new Uint8Array(binary.length);
    for (var i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
    return new Blob([bytes], { type: mime });
  }

  function showResult(payload) {
    var md = payload.result_md || "";
    if (!md) {
      showError("The review completed but the report was empty.");
      return;
    }
    pageTitle.textContent = "Your review is ready";
    pageBlurb.innerHTML =
      "<strong>This is the only copy.</strong> Save it locally now — once you leave this page the review is gone from our servers.";
    if (progressWrap) progressWrap.style.display = "none";

    // session_id is deliberately never carried in the status page URL (see
    // upload.js / paid-tool-upload.js — it's a bearer credential for
    // /paper-review/redeem-session, so putting it in the URL would leak it
    // via browser history/Referer). The backend resolves it server-side from
    // the token and includes it in the completed-job payload instead; that's
    // what makes the "Get invoice" button below reachable at all.
    var sessionId = payload.session_id || "";
    var product = payload.product || "paper-review";
    var prettyName = (product === "paper-review")
      ? "manuscript-review"
      : product.replace(/-/g, "_");

    var html = '<div class="pr-result-wrap">';
    html += '<div class="pr-result-meta">Saved nowhere on our side. Download the Markdown to keep a copy.</div>';
    html += renderDeterministicPanel(payload.deterministic_findings);
    html += '<article class="pr-result-md">' + renderMarkdown(md) + '</article>';
    html += '<div class="pr-result-actions">';
    html += '<button type="button" class="btn btn-primary" id="dl-md">Download Markdown</button>';
    if (payload.annotated_pdf_b64) {
      html += '<button type="button" class="btn btn-primary" id="dl-pdf">Download annotated PDF</button>';
    }
    html += '<button type="button" class="btn btn-secondary" id="print-pdf">Print / Save as PDF</button>';
    html += '<button type="button" class="btn btn-secondary" id="copy-md">Copy to clipboard</button>';
    if (sessionId) {
      html += '<button type="button" class="btn btn-secondary" id="get-invoice">Get invoice for reimbursement</button>';
    }
    if (product === "paper-review") {
      html += '<a class="btn btn-secondary" href="/tools/cover-letter/?utm=after-review">Add a cover letter — $2</a>';
      html += '<a class="btn btn-secondary" href="/tools/paper-review/revision/?utm=after-review">Re-review on revision — $2</a>';
    }
    html += "</div>";

    // Invoice form (hidden by default, revealed by "Get invoice" button)
    if (sessionId) {
      html += '<div id="invoice-pane" class="pr-invoice-pane" hidden>';
      html += '<h3>Invoice for institutional reimbursement</h3>';
      html += '<p>We will email you a Stripe-generated PDF invoice. Optionally add a line for your institution\'s tax ID.</p>';
      html += '<label for="invoice-tax" class="pr-field-label">Institution / tax ID line <span class="pr-field-hint">(optional)</span></label>';
      html += '<input type="text" id="invoice-tax" class="pr-input" placeholder="e.g. University of X, EIN 12-3456789">';
      html += '<div style="margin-top:0.6rem"><button type="button" class="btn btn-primary" id="invoice-send">Send me the invoice</button></div>';
      html += '<p class="pr-field-help" id="invoice-status" aria-live="polite"></p>';
      html += '</div>';
    }
    html += '</div>';
    resultContainer.innerHTML = html;

    var dlBtn = document.getElementById("dl-md");
    if (dlBtn) {
      dlBtn.addEventListener("click", function () {
        var blob = new Blob([md], { type: "text/markdown" });
        var url = URL.createObjectURL(blob);
        var a = document.createElement("a");
        a.href = url; a.download = prettyName + ".md"; a.click();
        URL.revokeObjectURL(url);
      });
    }

    var dlPdf = document.getElementById("dl-pdf");
    if (dlPdf && payload.annotated_pdf_b64) {
      dlPdf.addEventListener("click", function () {
        var blob = base64ToBlob(payload.annotated_pdf_b64, "application/pdf");
        var url = URL.createObjectURL(blob);
        var a = document.createElement("a");
        a.href = url; a.download = prettyName + "-annotated.pdf"; a.click();
        URL.revokeObjectURL(url);
      });
    }

    var printBtn = document.getElementById("print-pdf");
    if (printBtn) {
      // Reuses the already-rendered report HTML — a print stylesheet
      // (paper-review.css, @media print) hides site chrome and the action
      // buttons so only the report prints. "Save as PDF" is a destination
      // in every modern browser's print dialog.
      printBtn.addEventListener("click", function () { window.print(); });
    }

    var copyBtn = document.getElementById("copy-md");
    if (copyBtn) {
      copyBtn.addEventListener("click", function () {
        navigator.clipboard.writeText(md).then(function () {
          var orig = copyBtn.textContent;
          copyBtn.textContent = "Copied!";
          setTimeout(function () { copyBtn.textContent = orig; }, 2000);
        }).catch(function () { copyBtn.textContent = "Copy failed"; });
      });
    }

    var invBtn = document.getElementById("get-invoice");
    var invPane = document.getElementById("invoice-pane");
    if (invBtn && invPane) {
      invBtn.addEventListener("click", function () { invPane.hidden = false; invBtn.style.display = "none"; });
    }
    var invSend = document.getElementById("invoice-send");
    if (invSend) {
      invSend.addEventListener("click", function () {
        var taxLine = (document.getElementById("invoice-tax") || {}).value || "";
        var statusEl = document.getElementById("invoice-status");
        invSend.disabled = true;
        statusEl.innerHTML = '<span class="tool-spinner" aria-hidden="true"></span>Generating invoice…';
        fetch(API_BASE + "/paper-review/invoice", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ session_id: sessionId, tax_id_line: taxLine, token: token }),
        })
          .then(function (resp) {
            if (!resp.ok) return resp.json().then(function (p) { throw p; });
            return resp.json();
          })
          .then(function (data) {
            var link = data.invoice_pdf || data.hosted_invoice_url || "#";
            statusEl.innerHTML = 'Invoice ready: <a href="' + escapeHtml(link) + '" target="_blank" rel="noopener">open PDF</a>. We also emailed it to the address on file.';
          })
          .catch(function (err) {
            invSend.disabled = false;
            statusEl.innerHTML = '<span class="bib-err">' + escapeHtml((err && err.detail) || "Could not generate invoice.") + "</span>";
          });
      });
    }
  }

  // ----- deterministic-checks panel -----
  // Renders the reproducible, no-AI findings (statcheck/GRIM, arithmetic,
  // reporting completeness, reference integrity) as a structured, sortable
  // list above the narrative report. All text is HTML-escaped — the values
  // contain manuscript snippets.
  var SEVERITY_META = {
    error:   { rank: 0, label: "Error",   cls: "pr-det-error" },
    warning: { rank: 1, label: "Warning", cls: "pr-det-warning" },
    info:    { rank: 2, label: "Info",    cls: "pr-det-info" },
  };
  var KIND_LABEL = {
    statcheck: "Statistics", grim: "Statistics", numbers: "Numbers",
    structure: "Structure", openscience: "Open science", text: "Text",
    citation: "References",
  };

  function renderDeterministicPanel(findings) {
    if (!Array.isArray(findings) || findings.length === 0) return "";
    var items = findings.slice().filter(function (f) {
      return f && typeof f === "object" && f.summary;
    });
    if (items.length === 0) return "";
    items.sort(function (a, b) {
      var ra = (SEVERITY_META[a.severity] || SEVERITY_META.info).rank;
      var rb = (SEVERITY_META[b.severity] || SEVERITY_META.info).rank;
      return ra - rb;
    });
    var nErr = items.filter(function (f) { return f.severity === "error"; }).length;
    var nWarn = items.filter(function (f) { return f.severity === "warning"; }).length;
    var nInfo = items.length - nErr - nWarn;

    var counts = [];
    if (nErr) counts.push(nErr + " error" + (nErr > 1 ? "s" : ""));
    if (nWarn) counts.push(nWarn + " warning" + (nWarn > 1 ? "s" : ""));
    if (nInfo) counts.push(nInfo + " note" + (nInfo > 1 ? "s" : ""));

    var h = '<section class="pr-det-panel" aria-label="Verified automated checks">';
    h += '<div class="pr-det-head">';
    h += '<h2 class="pr-det-title">Verified checks <span class="pr-det-badge-auto">automated · reproducible</span></h2>';
    h += '<p class="pr-det-sub">Computed by non-AI engines (p-value recomputation, GRIM, arithmetic, reporting completeness). These are facts, not opinions — ' + escapeHtml(counts.join(", ")) + '.</p>';
    h += '</div><ul class="pr-det-list">';
    items.forEach(function (f) {
      var meta = SEVERITY_META[f.severity] || SEVERITY_META.info;
      var kind = KIND_LABEL[f.kind] || (f.kind || "");
      h += '<li class="pr-det-item ' + meta.cls + '">';
      h += '<div class="pr-det-row">';
      h += '<span class="pr-det-sev">' + escapeHtml(meta.label) + '</span>';
      if (kind) h += '<span class="pr-det-kind">' + escapeHtml(kind) + '</span>';
      h += '<span class="pr-det-summary">' + escapeHtml(f.summary) + '</span>';
      h += '</div>';
      if (f.detail) h += '<div class="pr-det-detail">' + escapeHtml(f.detail) + '</div>';
      h += '</li>';
    });
    h += '</ul></section>';
    return h;
  }

  // ----- tiny zero-dependency Markdown renderer -----
  // Supports: # ## ### headings, **bold**, __bold__, *em*, _em_, `code`,
  // ```fenced code```, > blockquote, unordered (- or *) lists, ordered
  // (1.) lists, paragraphs. Input is HTML-escaped first.
  function renderMarkdown(md) {
    if (!md || typeof md !== "string") return "";
    // Defense in depth: the LLM is instructed server-side to emit plain
    // Markdown only (no images, no links, no raw HTML). The renderer
    // treats output as untrusted regardless.
    //   - Invisible Unicode and C0/C1 controls: stripped.
    //   - Markdown image syntax: converted to inert text. Never emit <img>.
    //   - Markdown link syntax: converted to inert text. Never emit <a>.
    //   - escapeHtml() (below) renders any remaining HTML inert before the
    //     regex transforms run, so injected <script> becomes text.
    md = md.replace(/[\u200B-\u200F\u202A-\u202E\u2060-\u2064\u206A-\u206F\uFEFF\u00AD]/g, "");
    md = md.replace(/[\x00-\x08\x0B\x0C\x0E-\x1F\x7F-\x9F]/g, "");
    if (md.length > 500000) {
      md = md.slice(0, 500000) + "\n\n_[output truncated for display]_";
    }
    md = md.replace(/!\[([^\]]*)\]\([^)]*\)/g, "[image: $1]");
    md = md.replace(/\[([^\]]+)\]\(([^)]+)\)/g, "$1 ($2)");

    // First, extract fenced code blocks and replace with placeholders so the
    // rest of the regex pipeline doesn't munge them.
    var codeBlocks = [];
    md = md.replace(/```(?:\w+)?\n([\s\S]*?)```/g, function (_, code) {
      codeBlocks.push(code);
      return " CODE" + (codeBlocks.length - 1) + " ";
    });

    var s = escapeHtml(md);

    // Inline code
    s = s.replace(/`([^`\n]+)`/g, function (_, c) { return "<code>" + c + "</code>"; });
    // Bold + italic — order matters: bold first
    s = s.replace(/\*\*([^*\n][^*]*?)\*\*/g, "<strong>$1</strong>");
    s = s.replace(/__([^_\n][^_]*?)__/g, "<strong>$1</strong>");
    s = s.replace(/(^|[\s(])\*([^*\n]+?)\*/g, "$1<em>$2</em>");
    s = s.replace(/(^|[\s(])_([^_\n]+?)_/g, "$1<em>$2</em>");

    // Block-level: split into paragraphs by blank line, then within each
    // block detect headings / lists / blockquotes / paragraphs.
    var blocks = s.split(/\n\s*\n/);
    var out = [];
    blocks.forEach(function (block) {
      block = block.replace(/^\n+|\n+$/g, "");
      if (!block) return;
      // Heading
      var h = block.match(/^(#{1,6})\s+(.*)$/);
      if (h) {
        var lvl = h[1].length;
        out.push("<h" + lvl + ">" + h[2].trim() + "</h" + lvl + ">");
        return;
      }
      // Blockquote
      if (/^&gt;\s/.test(block)) {
        var bq = block.split("\n").map(function (l) {
          return l.replace(/^&gt;\s?/, "");
        }).join("<br>");
        out.push("<blockquote>" + bq + "</blockquote>");
        return;
      }
      // Unordered list
      if (/^([-*+])\s+/.test(block.split("\n")[0])) {
        var lis = block.split("\n").map(function (l) {
          var m = l.match(/^[-*+]\s+(.*)$/);
          return m ? "<li>" + m[1] + "</li>" : l;
        }).join("");
        out.push("<ul>" + lis + "</ul>");
        return;
      }
      // Ordered list
      if (/^\d+\.\s+/.test(block.split("\n")[0])) {
        var lis2 = block.split("\n").map(function (l) {
          var m = l.match(/^\d+\.\s+(.*)$/);
          return m ? "<li>" + m[1] + "</li>" : l;
        }).join("");
        out.push("<ol>" + lis2 + "</ol>");
        return;
      }
      // Plain paragraph
      out.push("<p>" + block.replace(/\n/g, "<br>") + "</p>");
    });

    var rendered = out.join("\n");
    // Restore fenced code blocks
    rendered = rendered.replace(/ CODE(\d+) /g, function (_, i) {
      return "<pre><code>" + escapeHtml(codeBlocks[parseInt(i, 10)]) + "</code></pre>";
    });
    return rendered;
  }

  // ----- polling loop -----
  function poll(token, attempt) {
    attempt = attempt || 1;
    if (attempt > MAX_POLLS) {
      showError("Your review is taking longer than expected. It may still be running — refresh this page in a few minutes, or email ben@purplelink.llc.");
      return;
    }
    fetch(API_BASE + "/paper-review/status?token=" + encodeURIComponent(token))
      .then(function (resp) {
        if (resp.status === 404) {
          showError("This review token is not recognised. Either the review has already been downloaded (we keep one copy) or the token is invalid.");
          return null;
        }
        if (!resp.ok) return resp.json().then(function (p) { throw p; });
        return resp.json();
      })
      .then(function (data) {
        if (!data) return;
        setProgress(data.progress_pct, data.stage);
        if (data.status === "done") {
          showResult(data);
          return;
        }
        if (data.status === "error") {
          showError("Your review failed: " + friendlyError(data.error) + ".", data.replacement_token);
          return;
        }
        setTimeout(function () { poll(token, attempt + 1); }, POLL_MS);
      })
      .catch(function (err) {
        // Transient network glitches — retry rather than failing the user.
        setTimeout(function () { poll(token, attempt + 1); }, POLL_MS);
      });
  }

  var token = getToken();
  if (!token) {
    showError("Missing review token. If you've just paid, restart from the Paper Review page.");
  } else {
    setProgress(5, ACTIVE_CONFIG.order[0]);
    poll(token);
  }
})();
