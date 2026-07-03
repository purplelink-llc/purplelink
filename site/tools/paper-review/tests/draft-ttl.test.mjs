// Regression test: localStorage draft autosave in paid-tool-upload.js must
// expire and purge rather than persisting sensitive pasted manuscript/review
// text indefinitely. Exercises the real file via a minimal DOM/localStorage
// vm shim (no JS test framework is present in this repo).
//
// Run with: node site/tools/paper-review/tests/draft-ttl.test.mjs
import fs from "node:fs";
import path from "node:path";
import vm from "node:vm";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const SRC_PATH = path.join(__dirname, "..", "paid-tool-upload.js");
const src = fs.readFileSync(SRC_PATH, "utf8");

function makeEl(id) {
  return {
    id,
    value: "",
    files: null,
    textContent: "",
    hidden: false,
    listeners: {},
    classList: { toggle() {} },
    addEventListener(ev, fn) {
      (this.listeners[ev] = this.listeners[ev] || []).push(fn);
    },
  };
}

function makeStorage() {
  const store = new Map();
  return {
    getItem: (k) => (store.has(k) ? store.get(k) : null),
    setItem: (k, v) => store.set(k, String(v)),
    removeItem: (k) => store.delete(k),
  };
}

function makeSandbox({ search = "" } = {}) {
  const elements = {
    "redeem-status": makeEl("redeem-status"),
    "upload-form": makeEl("upload-form"),
    "submit-btn": makeEl("submit-btn"),
    status: makeEl("status"),
    "reviewer-input": makeEl("reviewer-input"),
    "response-input": makeEl("response-input"),
  };
  const localStorage = makeStorage();
  const sandbox = {
    window: {
      location: { search },
      localStorage,
      addEventListener() {},
    },
    document: { getElementById: (id) => elements[id] || null },
    URLSearchParams,
    fetch: () => new Promise(() => {}), // overridden per-test
    API_BASE: "https://api.example.com",
    wireDropzone: () => {},
    escapeHtml: (s) => s,
    console,
  };
  vm.createContext(sandbox);
  vm.runInContext(src, sandbox, { filename: "paid-tool-upload.js" });
  return { sandbox, elements, localStorage };
}

let failures = 0;
function assert(cond, msg) {
  if (!cond) {
    failures++;
    console.error("FAIL:", msg);
  } else {
    console.log("PASS:", msg);
  }
}

// Mirrors site/tools/response-review/upload.js's field config, the exact
// call path in the confirmed finding.
const RESPONSE_REVIEW_CFG = {
  productCategory: "response-review",
  submitPath: "/response-review/submit",
  fields: [
    { type: "textarea", name: "reviewer_comments", elementId: "reviewer-input", required: true },
    { type: "textarea", name: "author_response", elementId: "response-input", required: true },
  ],
};

function stubSuccessfulRedeem(sandbox) {
  sandbox.fetch = () =>
    Promise.resolve({
      ok: true,
      status: 200,
      json: () => Promise.resolve({ token: "tok123", category: "response-review" }),
    });
}

// --- saveDraft() writes a timestamped, namespaced draft ---
{
  const { sandbox, elements, localStorage } = makeSandbox({ search: "?session_id=abc" });
  sandbox.window.setupPaidToolUpload(RESPONSE_REVIEW_CFG);

  elements["reviewer-input"].value = "Reviewer said the method is flawed.";
  elements["reviewer-input"].listeners.input.forEach((fn) => fn());

  const raw = localStorage.getItem("purplelink-draft:response-review");
  assert(!!raw, "draft is written to localStorage on input");
  const parsed = JSON.parse(raw);
  assert(typeof parsed.savedAt === "number", "draft stores a savedAt timestamp");
  assert(
    parsed.fields["reviewer-input"] === "Reviewer said the method is flawed.",
    "draft stores field value under fields{}"
  );
}

async function testExpiryEndToEnd() {
  // Case A: draft older than the TTL is NOT restored and is purged on load.
  {
    const { sandbox, elements, localStorage } = makeSandbox({ search: "?session_id=abc" });
    const key = "purplelink-draft:response-review";
    const old = {
      savedAt: Date.now() - 49 * 60 * 60 * 1000, // 49h old, TTL is 48h
      fields: { "reviewer-input": "stale sensitive text" },
    };
    localStorage.setItem(key, JSON.stringify(old));
    stubSuccessfulRedeem(sandbox);
    sandbox.window.setupPaidToolUpload(RESPONSE_REVIEW_CFG);
    await new Promise((r) => setTimeout(r, 20));
    assert(elements["reviewer-input"].value === "", "expired draft is NOT restored into the textarea");
    assert(localStorage.getItem(key) === null, "expired draft is purged from localStorage on load");
  }

  // Case B: draft within the TTL is restored and left in place.
  {
    const { sandbox, elements, localStorage } = makeSandbox({ search: "?session_id=abc" });
    const key = "purplelink-draft:response-review";
    const fresh = { savedAt: Date.now() - 60 * 1000, fields: { "reviewer-input": "fresh text" } };
    localStorage.setItem(key, JSON.stringify(fresh));
    stubSuccessfulRedeem(sandbox);
    sandbox.window.setupPaidToolUpload(RESPONSE_REVIEW_CFG);
    await new Promise((r) => setTimeout(r, 20));
    assert(elements["reviewer-input"].value === "fresh text", "fresh (within-TTL) draft IS restored");
    assert(localStorage.getItem(key) !== null, "fresh draft remains in localStorage");
  }

  // Case C: pre-fix legacy drafts (no savedAt field at all) are treated as
  // expired -- purged, not restored -- rather than restored forever.
  {
    const { sandbox, elements, localStorage } = makeSandbox({ search: "?session_id=abc" });
    const key = "purplelink-draft:response-review";
    const legacy = { "reviewer-input": "old-format sensitive text", "response-input": "" };
    localStorage.setItem(key, JSON.stringify(legacy));
    stubSuccessfulRedeem(sandbox);
    sandbox.window.setupPaidToolUpload(RESPONSE_REVIEW_CFG);
    await new Promise((r) => setTimeout(r, 20));
    assert(elements["reviewer-input"].value === "", "legacy (no savedAt) draft is NOT restored");
    assert(localStorage.getItem(key) === null, "legacy draft is purged from localStorage on load");
  }
}

await testExpiryEndToEnd();

if (failures > 0) {
  console.error(`\n${failures} test(s) failed.`);
  process.exit(1);
} else {
  console.log("\nAll draft-TTL regression tests passed.");
}
