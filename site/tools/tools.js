// Shared client logic for purplelink LaTeX tool pages.
// The Modal endpoint base is defined ONCE here.
const API_BASE = "https://ben-ampel--purplelink-latextools-web.modal.run";
const MAX_BYTES = 5 * 1024 * 1024;

function escapeHtml(s) {
  const d = document.createElement("div");
  d.textContent = s;
  return d.innerHTML;
}

// Wire a dropzone+file input to a hidden chosen-file store.
function wireDropzone(zoneId, inputId, onFile) {
  const zone = document.getElementById(zoneId);
  const input = document.getElementById(inputId);
  zone.addEventListener("click", () => input.click());
  zone.addEventListener("dragover", (e) => { e.preventDefault(); zone.classList.add("dragover"); });
  zone.addEventListener("dragleave", () => zone.classList.remove("dragover"));
  zone.addEventListener("drop", (e) => {
    e.preventDefault();
    zone.classList.remove("dragover");
    if (e.dataTransfer.files.length) { input.files = e.dataTransfer.files; onFile(input.files[0]); }
  });
  input.addEventListener("change", () => { if (input.files.length) onFile(input.files[0]); });
}

function validClientSide(file, statusEl) {
  if (!file.name.toLowerCase().endsWith(".tex")) { statusEl.textContent = "Please choose a .tex file."; return false; }
  if (file.size > MAX_BYTES) { statusEl.textContent = "File is too large (max 5 MB)."; return false; }
  if (file.size === 0) { statusEl.textContent = "That file is empty."; return false; }
  return true;
}

function renderError(resultEl, status, payload) {
  if (status === 429) { resultEl.innerHTML = '<div class="tool-error">You\'ve reached the daily limit. Please try again tomorrow.</div>'; return; }
  if (payload && payload.error === "timeout") { resultEl.innerHTML = '<div class="tool-error">Compilation took too long (over 60s). Your document may have an infinite loop or be too large for the free tool.</div>'; return; }
  if (payload && payload.errors && payload.errors.length) {
    const lines = payload.errors.map((e) => `Line ${e.line}: ${escapeHtml(e.message)}`).join("\n");
    resultEl.innerHTML = `<div class="tool-error">Compilation failed:\n${lines}</div>`;
    return;
  }
  const detail = payload && payload.detail ? escapeHtml(payload.detail) : "Something went wrong. Please try again.";
  resultEl.innerHTML = `<div class="tool-error">${detail}</div>`;
}

function showPdf(resultEl, blob, downloadName) {
  const url = URL.createObjectURL(blob);
  resultEl.innerHTML =
    `<a class="btn btn-primary" href="${url}" download="${downloadName}">Download ${downloadName}</a>` +
    `<div style="margin-top:14px"><iframe title="PDF preview" src="${url}"></iframe></div>`;
}

// POST a FormData to API_BASE+path; on PDF success call showPdf, else renderError.
async function postForPdf(path, formData, statusEl, resultEl, downloadName) {
  statusEl.textContent = "Working… this can take up to a minute.";
  resultEl.innerHTML = "";
  try {
    const resp = await fetch(API_BASE + path, { method: "POST", body: formData });
    const ctype = resp.headers.get("content-type") || "";
    if (resp.ok && ctype.includes("application/pdf")) {
      const blob = await resp.blob();
      statusEl.textContent = "Done.";
      showPdf(resultEl, blob, downloadName);
    } else {
      let payload = null;
      try { payload = await resp.json(); } catch (_) {}
      statusEl.textContent = "";
      renderError(resultEl, resp.status, payload);
    }
  } catch (_) {
    statusEl.textContent = "";
    resultEl.innerHTML = '<div class="tool-error">Network error. Please check your connection and try again.</div>';
  }
}
