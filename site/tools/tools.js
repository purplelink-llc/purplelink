// Shared client logic for purplelink LaTeX tool pages.
// The Modal endpoint base is defined ONCE here.
const API_BASE = "https://ben-ampel--purplelink-latextools-web.modal.run";
const MAX_TEX_BYTES = 5 * 1024 * 1024;   // 5 MB for a single .tex file
const MAX_ZIP_BYTES = 10 * 1024 * 1024;  // 10 MB for a project .zip
const MAX_BIB_BYTES = 2 * 1024 * 1024;   // 2 MB for a .bib file
const MAX_DOCX_BYTES = 5 * 1024 * 1024;  // 5 MB for a .docx file
const MAX_DOC2MD_BYTES = 20 * 1024 * 1024; // 20 MB for file-to-markdown uploads

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
  zone.setAttribute("tabindex", "0");
  zone.setAttribute("role", "button");
  zone.addEventListener("keydown", (e) => {
    if (e.key === "Enter" || e.key === " ") { e.preventDefault(); input.click(); }
  });
  zone.addEventListener("dragover", (e) => { e.preventDefault(); zone.classList.add("dragover"); });
  zone.addEventListener("dragleave", (e) => {
    if (zone.contains(e.relatedTarget)) return;
    zone.classList.remove("dragover");
  });
  zone.addEventListener("drop", (e) => {
    e.preventDefault();
    zone.classList.remove("dragover");
    if (e.dataTransfer.files.length) { input.files = e.dataTransfer.files; onFile(input.files[0]); }
  });
  input.addEventListener("change", () => { if (input.files.length) onFile(input.files[0]); });
}

function validClientSide(file, statusEl) {
  const name = file.name.toLowerCase();
  const isTex = name.endsWith(".tex");
  const isZip = name.endsWith(".zip");
  if (!isTex && !isZip) { statusEl.textContent = "Please choose a .tex file or a project .zip."; return false; }
  const maxBytes = isZip ? MAX_ZIP_BYTES : MAX_TEX_BYTES;
  if (file.size > maxBytes) { statusEl.textContent = `File is too large (max ${isZip ? "10" : "5"} MB).`; return false; }
  if (file.size === 0) { statusEl.textContent = "That file is empty."; return false; }
  return true;
}

function validDocxClientSide(file, statusEl) {
  if (!file.name.toLowerCase().endsWith(".docx")) { statusEl.textContent = "Please choose a .docx file."; return false; }
  if (file.size === 0) { statusEl.textContent = "That file is empty."; return false; }
  if (file.size > MAX_DOCX_BYTES) { statusEl.textContent = "File is too large (max 5 MB)."; return false; }
  return true;
}

function validBibClientSide(file, statusEl) {
  if (!file.name.toLowerCase().endsWith(".bib")) { statusEl.textContent = "Please choose a .bib file."; return false; }
  if (file.size === 0) { statusEl.textContent = "That file is empty."; return false; }
  if (file.size > MAX_BIB_BYTES) { statusEl.textContent = "File is too large (max 2 MB)."; return false; }
  return true;
}

function renderError(resultEl, status, payload) {
  if (status === 429) { resultEl.innerHTML = '<div class="tool-error" role="alert">You\'ve reached the daily limit. Please try again tomorrow.</div>'; return; }
  if (payload && payload.error === "timeout") { resultEl.innerHTML = '<div class="tool-error" role="alert">Compilation took too long (over 60s). Your document may have an infinite loop or be too large for the free tool.</div>'; return; }
  if (payload && payload.errors && payload.errors.length) {
    const lines = payload.errors.map((e) => `Line ${e.line}: ${escapeHtml(e.message)}`).join("\n");
    let html = `<div class="tool-error" role="alert">Compilation failed:\n${lines}</div>`;
    if (payload.log) {
      html += `<details style="margin-top:0.75rem"><summary style="cursor:pointer;font-size:0.85rem;color:#9ca3af">Full compile log</summary><pre style="font-size:0.72rem;white-space:pre-wrap;overflow-x:auto;max-height:22rem;overflow-y:auto;background:#0a0a0a;padding:0.75rem;border-radius:4px;color:#d4d4d4;margin-top:0.4rem">${escapeHtml(payload.log)}</pre></details>`;
    }
    resultEl.innerHTML = html;
    return;
  }
  const detail = payload && payload.detail ? escapeHtml(payload.detail) : "Something went wrong. Please try again.";
  resultEl.innerHTML = `<div class="tool-error" role="alert">${detail}</div>`;
}

function showPdf(resultEl, blob, downloadName) {
  const url = URL.createObjectURL(blob);
  resultEl.dataset.blobUrl = url;
  resultEl.innerHTML =
    `<a class="btn btn-primary" href="${url}" download="${escapeHtml(downloadName)}">Download ${escapeHtml(downloadName)}</a>` +
    `<div class="tool-preview"><iframe title="PDF preview" src="${url}"></iframe></div>`;
}

// POST a FormData; on a file response, offer a download link (no preview).
async function postForDownload(path, formData, statusEl, resultEl, downloadName, mime) {
  statusEl.innerHTML = '<span class="tool-spinner" aria-hidden="true"></span>Working… this can take up to a minute.';
  const prevUrl = resultEl.dataset.blobUrl;
  if (prevUrl) { URL.revokeObjectURL(prevUrl); delete resultEl.dataset.blobUrl; }
  resultEl.innerHTML = "";
  try {
    const resp = await fetch(API_BASE + path, { method: "POST", body: formData });
    const ctype = resp.headers.get("content-type") || "";
    if (resp.ok && ctype.includes(mime)) {
      const blob = await resp.blob();
      const url = URL.createObjectURL(blob);
      resultEl.dataset.blobUrl = url;
      statusEl.textContent = "Done.";
      resultEl.innerHTML =
        `<a class="btn btn-primary" href="${url}" download="${escapeHtml(downloadName)}">Download ${escapeHtml(downloadName)}</a>`;
    } else {
      let payload = null;
      try { payload = await resp.json(); } catch (_) {}
      statusEl.textContent = "";
      renderError(resultEl, resp.status, payload);
    }
  } catch (_) {
    statusEl.textContent = "";
    resultEl.innerHTML = '<div class="tool-error" role="alert">Network error. Please check your connection and try again.</div>';
  }
}

// POST a FormData to API_BASE+path; on PDF success call showPdf, else renderError.
async function postForPdf(path, formData, statusEl, resultEl, downloadName) {
  statusEl.innerHTML = '<span class="tool-spinner" aria-hidden="true"></span>Working… this can take up to a minute.';
  const prevUrl = resultEl.dataset.blobUrl;
  if (prevUrl) { URL.revokeObjectURL(prevUrl); delete resultEl.dataset.blobUrl; }
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
    resultEl.innerHTML = '<div class="tool-error" role="alert">Network error. Please check your connection and try again.</div>';
  }
}
