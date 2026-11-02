// "Send to my Mac" (netlify/functions/send-to-mac.mjs): the fixed email, the honeypot, validation, the rate limits
// (per IP, per address, all sends; fail closed), product news off unless asked for and kept only after the confirm
// button, the unsubscribe, and the attribution carried into the emailed link. Blobs and Resend are stubbed. The Reddit
// click ids here are made up and never reach Reddit.
//
// Run with: node --experimental-test-module-mocks --test netlify/tests/send-to-mac.test.mjs

import { test, mock, beforeEach } from "node:test";
import assert from "node:assert/strict";

const store = new Map();
let storeDown = false;
const blobsModule = {
  getStore: (name) => ({
    get: async (k) => { if (storeDown) throw new Error("down"); return store.get(`${name}/${k}`) ?? null; },
    set: async (k, v) => { if (storeDown) throw new Error("down"); store.set(`${name}/${k}`, v); },
    delete: async (k) => { store.delete(`${name}/${k}`); },
    list: async () => ({ blobs: [...store.keys()].filter((k) => k.startsWith(`${name}/`)).map((k) => ({ key: k.slice(name.length + 1) })) }),
  }),
};
try { mock.module("@netlify/blobs", { exports: blobsModule }); } catch { mock.module("@netlify/blobs", { namedExports: blobsModule }); }

const env = { RESEND_API_KEY: "re_dummy", SUBSCRIBE_SECRET: "test-secret" };
globalThis.Netlify = { env: { get: (k) => env[k] } };
process.env.SUBSCRIBE_SECRET = "test-secret";
const mod = await import("../functions/send-to-mac.mjs");
const { default: handler, PER_IP_DAILY, PER_EMAIL_DAILY, ALL_DAILY, NEWS_STORE, attributionQuery, cleanAttribution, newsUnsubscribeToken } = mod;
const confirm = (await import("../functions/confirm-signup.mjs")).default;

let calls, resendStatus, logged;
const origError = console.error;
beforeEach(() => {
  store.clear();
  storeDown = false;
  calls = [];
  resendStatus = 200;
  logged = [];
  console.error = (...a) => { logged.push(a.join(" ")); };
  globalThis.fetch = async (url, opts = {}) => {
    calls.push({ url: String(url), opts });
    return new Response("{}", { status: resendStatus });
  };
});

let ipN = 0;
const post = (body, headers = {}) => new Request("https://purplelink.llc/.netlify/functions/send-to-mac", {
  method: "POST",
  headers: { "Content-Type": "application/json", Origin: "https://purplelink.llc", "x-nf-client-connection-ip": `203.0.113.${(ipN++ % 250) + 1}`, ...headers },
  body: typeof body === "string" ? body : JSON.stringify(body),
});
const mails = () => calls.filter((c) => c.url === "https://api.resend.com/emails").map((c) => JSON.parse(c.opts.body));
const kept = () => [...store.keys()].filter((k) => !k.startsWith("rate-limits/"));
const OK = { email: "Reader@Example.org", product: "moderntex" };

test("a request sends one fixed ModernTex email to that address and keeps nothing", async () => {
  const res = await handler(post(OK));
  assert.equal(res.status, 200);
  assert.deepEqual(await res.json(), { ok: true });
  const [mail, ...rest] = mails();
  assert.equal(rest.length, 0);
  assert.deepEqual(mail.to, ["Reader@Example.org"]);
  assert.equal(mail.from, "Benjamin Ampel <orders@purplelink.llc>");
  assert.equal(mail.reply_to, "ben@purplelink.llc");
  assert.equal(mail.subject, "ModernTex: the download link for your Mac");
  assert.match(mail.text, /https:\/\/purplelink\.llc\/moderntex\/\?utm_source=send-to-mac&utm_medium=email&utm_campaign=send-to-mac#buy/);
  assert.match(mail.text, /seven days/);
  assert.match(mail.text, /\$19\.99/);
  assert.match(mail.text, /macOS 14 or later/);
  assert.match(mail.text, /the address was not kept/);
  assert.ok(!mail.headers, "no List-Unsubscribe on a one-off transactional email");
  assert.ok(!/confirm-signup/.test(mail.text), "no news link unless asked");
  assert.deepEqual(kept(), []);
});

test("nothing from the request but the address reaches the email", async () => {
  const res = await handler(post({ ...OK, name: "<b>Click http://evil.example</b>", subject: "Win", message: "evil.example", ft: "<script>", fc: "x y", rdt: "a b" }));
  assert.equal(res.status, 200);
  const [mail] = mails();
  const all = JSON.stringify(mail);
  for (const planted of ["evil.example", "<script", "Win"]) assert.ok(!all.includes(planted), planted);
  assert.match(mail.text, /utm_source=send-to-mac&utm_medium=email/);
});

test("the honeypot answers ok and sends and counts nothing", async () => {
  const res = await handler(post({ ...OK, website: "http://spam.example" }));
  assert.equal(res.status, 200);
  assert.equal(mails().length, 0);
  assert.equal(store.size, 0);
});

test("validation: bad JSON, bad address, unknown product, oversize body", async () => {
  assert.equal((await handler(post("{not json"))).status, 400);
  assert.equal((await handler(post("[1,2]"))).status, 400);
  for (const email of ["", "no-at-sign", "a@b", "a b@c.org", "x@y.org\nBcc: z@w.org", `${"a".repeat(250)}@b.org`, 42]) {
    const res = await handler(post({ ...OK, email }));
    assert.equal(res.status, 400, String(email));
    assert.equal((await res.json()).error, "invalid_email");
  }
  for (const product of ["", "keyfeel-pro", "__proto__", "constructor", null]) {
    const res = await handler(post({ ...OK, product }));
    assert.equal(res.status, 400, String(product));
    assert.equal((await res.json()).error, "invalid_product");
  }
  assert.equal((await handler(post({ ...OK, pad: "x".repeat(2100) }))).status, 413);
  assert.equal(mails().length, 0);
});

test("the origin must be this site: a missing or foreign Origin is refused", async () => {
  assert.equal((await handler(post(OK, { Origin: "https://evil.example" }))).status, 403);
  const noOrigin = new Request("https://purplelink.llc/.netlify/functions/send-to-mac", {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(OK),
  });
  assert.equal((await handler(noOrigin)).status, 403);
  assert.equal((await handler(post(OK, { Origin: "https://www.purplelink.llc" }))).status, 200);
  assert.equal((await handler(new Request("https://purplelink.llc/.netlify/functions/send-to-mac"))).status, 405);
});

test("per-IP limit: the sixth request from one IP in a day is refused", async () => {
  const ip = { "x-nf-client-connection-ip": "198.51.100.7" };
  for (let i = 0; i < PER_IP_DAILY; i++) assert.equal((await handler(post({ ...OK, email: `r${i}@example.org` }, ip))).status, 200);
  const res = await handler(post({ ...OK, email: "other@example.org" }, ip));
  assert.equal(res.status, 429);
  assert.equal(mails().length, PER_IP_DAILY);
});

test("per-address limit: the third request for one address in a day sends nothing and looks the same", async () => {
  for (let i = 0; i < PER_EMAIL_DAILY; i++) assert.equal((await handler(post(OK))).status, 200);
  // A different case is the same address.
  const res = await handler(post({ ...OK, email: "READER@example.ORG" }));
  assert.equal(res.status, 200);
  assert.deepEqual(await res.json(), { ok: true });
  assert.equal(mails().length, PER_EMAIL_DAILY);
});

test("all-sends limit: past the daily total every request is refused", async () => {
  for (let i = 0; i < ALL_DAILY; i++) await handler(post({ ...OK, email: `n${i}@example.org` }));
  assert.equal(mails().length, ALL_DAILY);
  const res = await handler(post({ ...OK, email: "late@example.org" }));
  assert.equal(res.status, 429);
  assert.equal(mails().length, ALL_DAILY);
});

test("rate-limit keys hold no address or IP", async () => {
  await handler(post(OK, { "x-nf-client-connection-ip": "198.51.100.99" }));
  const keys = [...store.keys()].join(" ");
  assert.ok(!/reader|example|198\.51/i.test(keys), keys);
});

test("fail closed: when the rate-limit store is down nothing is sent", async () => {
  storeDown = true;
  const res = await handler(post(OK));
  assert.equal(res.status, 503);
  assert.equal(mails().length, 0);
});

test("a refused send answers 502 and keeps nothing", async () => {
  resendStatus = 422;
  const res = await handler(post({ ...OK, news: true }));
  assert.equal(res.status, 502);
  assert.deepEqual(kept(), []);
});

test("product news is off by default: missing, false, \"true\", 1 and \"on\" add no confirm link", async () => {
  for (const news of [undefined, false, "true", 1, "on", "yes", {}]) {
    calls = [];
    await handler(post({ ...OK, email: `opt${String(news).replace(/\W/g, "")}@example.org`, news }));
    const [mail] = mails();
    assert.ok(mail, String(news));
    assert.ok(!/confirm-signup/.test(mail.text), String(news));
  }
  assert.deepEqual(kept(), []);
});

test("news: true adds a confirm link and stores nothing until the confirm button is pressed", async () => {
  await handler(post({ ...OK, news: true }));
  const [mail] = mails();
  const m = /https:\/\/purplelink\.llc\/\.netlify\/functions\/confirm-signup\?t=(\S+)/.exec(mail.text);
  assert.ok(m, mail.text);
  assert.deepEqual(kept(), []);
  const token = decodeURIComponent(m[1]);

  // Opening the link (a GET, as a mail scanner would) changes nothing.
  const view = await confirm(new Request(`https://purplelink.llc/.netlify/functions/confirm-signup?t=${encodeURIComponent(token)}`));
  assert.equal(view.status, 200);
  assert.match(await view.text(), /news about new Purplelink apps/);
  assert.deepEqual(kept(), []);

  // The button stores the record.
  const press = await confirm(new Request("https://purplelink.llc/.netlify/functions/confirm-signup", {
    method: "POST", headers: { "Content-Type": "application/x-www-form-urlencoded" }, body: new URLSearchParams({ t: token }).toString(),
  }));
  assert.equal(press.status, 200);
  const rec = JSON.parse(store.get(`${NEWS_STORE}/reader@example.org`));
  assert.equal(rec.email, "reader@example.org");
  assert.deepEqual(rec.products, ["moderntex"]);
  assert.equal(rec.source, "send-to-mac");
  assert.ok(rec.confirmedAt);
  assert.deepEqual(Object.keys(rec).sort(), ["confirmedAt", "email", "products", "source"]);
});

test("unsubscribe: GET only shows a button, POST deletes, a wrong token is refused", async () => {
  store.set(`${NEWS_STORE}/reader@example.org`, JSON.stringify({ email: "reader@example.org", products: ["moderntex"] }));
  const tok = newsUnsubscribeToken("reader@example.org", "test-secret");
  const url = `https://purplelink.llc/.netlify/functions/send-to-mac?u=${tok}&e=reader%40example.org`;
  const get = await handler(new Request(url, { headers: { Accept: "text/html" } }));
  assert.equal(get.status, 200);
  assert.match(await get.text(), /<form method="post"/);
  assert.ok(store.has(`${NEWS_STORE}/reader@example.org`));

  const bad = await handler(new Request(url.replace(tok, "0".repeat(64)), { method: "POST" }));
  assert.equal(bad.status, 400);
  assert.ok(store.has(`${NEWS_STORE}/reader@example.org`));

  const oneClick = await handler(new Request(url, { method: "POST", body: "List-Unsubscribe=One-Click" }));
  assert.equal(oneClick.status, 200);
  assert.ok(!store.has(`${NEWS_STORE}/reader@example.org`));
});

test("attribution: each first-touch shape becomes a link that reads back as the same channel", () => {
  const q = (ft, fc = "", rdt = "") => Object.fromEntries(new URLSearchParams(attributionQuery({ ft, fc, rdt })));
  assert.deepEqual(q("paid:reddit", "mtx-ad-test", "TEST_CLICK_ID.not-real"), {
    utm_source: "reddit", utm_medium: "paid", utm_campaign: "send-to-mac", utm_content: "mtx-ad-test", rdt_cid: "TEST_CLICK_ID.not-real",
  });
  assert.deepEqual(q("tool:bib-cleaner"), { utm_source: "tool-bib-cleaner", utm_medium: "send-to-mac", utm_campaign: "send-to-mac" });
  assert.deepEqual(q("chatgpt.com"), { utm_source: "chatgpt.com", utm_medium: "send-to-mac", utm_campaign: "send-to-mac" });
  assert.deepEqual(q("direct"), { utm_source: "send-to-mac", utm_medium: "email", utm_campaign: "send-to-mac" });
  assert.deepEqual(q(""), { utm_source: "send-to-mac", utm_medium: "email", utm_campaign: "send-to-mac" });
});

test("attribution values outside their allow-lists are dropped, not errors", async () => {
  assert.deepEqual(cleanAttribution({ ft: "paid:reddit\"><x", fc: "a/b", rdt: "x".repeat(200) }), { ft: "", fc: "", rdt: "" });
  assert.deepEqual(cleanAttribution({ ft: 5, fc: null }), { ft: "", fc: "", rdt: "" });
  const res = await handler(post({ ...OK, ft: "paid:reddit", fc: "mtx-ad-test", rdt: "TEST_CLICK_ID.not-real" }));
  assert.equal(res.status, 200);
  assert.match(mails()[0].text, /utm_source=reddit&utm_medium=paid&utm_campaign=send-to-mac&utm_content=mtx-ad-test&rdt_cid=TEST_CLICK_ID\.not-real#buy/);
});

test("the address never appears in logs", async () => {
  resendStatus = 500;
  await handler(post({ ...OK, news: true }));
  storeDown = true;
  await handler(post(OK));
  console.error = origError;
  assert.ok(logged.length >= 2);
  assert.ok(!logged.some((l) => /reader@example\.org/i.test(l)), logged.join("\n"));
});
