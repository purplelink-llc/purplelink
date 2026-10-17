// The unsubscribe confirmation escapes the address (S-09); subscribe rejects markup characters.
//
// Run with: node --experimental-test-module-mocks --test netlify/tests/unsubscribe-escape.test.mjs

import { test, mock } from "node:test";
import assert from "node:assert/strict";
import { createHmac } from "node:crypto";

const deleted = [];
const blobsModule = {
  getStore: () => ({
    get: async () => null,
    set: async () => {},
    delete: async (k) => { deleted.push(k); },
  }),
};
try { mock.module("@netlify/blobs", { exports: blobsModule }); } catch { mock.module("@netlify/blobs", { namedExports: blobsModule }); }
process.env.SUBSCRIBE_SECRET = "unit-test-secret";

const unsubscribe = (await import("../functions/unsubscribe.mjs")).default;
const subscribe = (await import("../functions/subscribe.mjs")).default;

test("the address is HTML-escaped on the confirmation page", async () => {
  const email = `x"><img src=x onerror=alert(1)>@example.com`;
  const token = createHmac("sha256", process.env.SUBSCRIBE_SECRET).update(email).digest("hex");
  const url = `https://purplelink.llc/.netlify/functions/unsubscribe?email=${encodeURIComponent(email)}&token=${token}`;
  // GET only shows the confirm page (it must not delete); the escaping applies there and after the POST.
  const confirm = await unsubscribe(new Request(url));
  const confirmHtml = await confirm.text();
  assert.equal(confirm.status, 200);
  assert.equal(confirmHtml.includes("<img src=x"), false);
  assert.ok(confirmHtml.includes("&lt;img src=x onerror=alert(1)&gt;@example.com"));
  assert.deepEqual(deleted, []);
  const res = await unsubscribe(new Request(url, { method: "POST" }));
  const html = await res.text();
  assert.equal(res.status, 200);
  assert.equal(html.includes("<img src=x"), false);
  assert.ok(html.includes("&lt;img src=x onerror=alert(1)&gt;@example.com"));
  assert.deepEqual(deleted, [email]);
});

test("subscribe is retired: it answers 410 even for markup characters", async () => {
  for (const email of ['a<b>@example.com', "a@example.com"]) {
    const res = await subscribe(new Request("https://purplelink.llc/.netlify/functions/subscribe", {
      method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ email }),
    }));
    assert.equal(res.status, 410, email);
  }
});
