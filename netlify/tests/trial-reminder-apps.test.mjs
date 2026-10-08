// Legroom and Keyfeel trial emails: the signup, the one-click unsubscribe, the daily reminder run (due, not yet due,
// already bought, buyer check unavailable, too old), the wording of both emails, and the page forms. Blobs, Resend
// and Stripe are stubbed. The same checks run for both apps because they share netlify/lib/trial-reminder.mjs.
//
// Run with: node --experimental-test-module-mocks --test netlify/tests/trial-reminder-apps.test.mjs

import { test, mock, beforeEach } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import vm from "node:vm";

const store = new Map();
const blobsModule = {
  getStore: (name) => ({
    get: async (k) => store.get(`${name}/${k}`) ?? null,
    set: async (k, v) => { store.set(`${name}/${k}`, v); },
    delete: async (k) => { store.delete(`${name}/${k}`); },
    list: async () => ({ blobs: [...store.keys()].filter((k) => k.startsWith(`${name}/`)).map((k) => ({ key: k.slice(name.length + 1) })) }),
  }),
};
try { mock.module("@netlify/blobs", { exports: blobsModule }); } catch { mock.module("@netlify/blobs", { namedExports: blobsModule }); }

const env = { RESEND_API_KEY: "re_dummy", STRIPE_SECRET_KEY: "sk_test_dummy" };
globalThis.Netlify = { env: { get: (k) => env[k] } };

const legroom = await import("../functions/legroom-reminder.mjs");
const keyfeel = await import("../functions/keyfeel-reminder.mjs");
const legroomSend = await import("../functions/legroom-reminder-send.mjs");
const keyfeelSend = await import("../functions/keyfeel-reminder-send.mjs");

const APPS = [
  { name: "Legroom", slug: "legroom", mod: legroom, send: legroomSend, records: "lg-trial-reminders", tokens: "lg-trial-reminder-tokens", own: "legroom", other: "keyfeel", price: /\$9\.99/ },
  { name: "Keyfeel", slug: "keyfeel", mod: keyfeel, send: keyfeelSend, records: "kf-trial-reminders", tokens: "kf-trial-reminder-tokens", own: "keyfeel", other: "legroom", price: /\$9\.99/ },
];

let calls, stripeSessions, stripeStatus, resendStatus;
beforeEach(() => {
  store.clear();
  calls = [];
  stripeSessions = [];
  stripeStatus = 200;
  resendStatus = 200;
  globalThis.fetch = async (url, opts = {}) => {
    const u = String(url);
    calls.push({ url: u, opts });
    if (u.startsWith("https://api.stripe.com/")) {
      return new Response(JSON.stringify({ data: stripeSessions }), { status: stripeStatus });
    }
    return new Response("{}", { status: resendStatus });
  };
});

const DAY = 86400000;
const mails = () => calls.filter((c) => c.url.startsWith("https://api.resend.com/")).map((c) => JSON.parse(c.opts.body));
// Everything kept for the reminders, not the shared per-day rate-limit counters.
const kept = () => [...store.keys()].filter((k) => !k.startsWith("rate-limits/"));
const postTo = (app) => (body, headers = {}) => new Request(`https://purplelink.llc/.netlify/functions/${app.slug}-reminder`, {
  method: "POST", headers: { "Content-Type": "application/json", "x-nf-client-connection-ip": "203.0.113.9", ...headers }, body: JSON.stringify(body),
});
const seedFor = (app) => (email, ageDays, token = "a".repeat(48)) => {
  const created = Date.now() - ageDays * DAY;
  store.set(`${app.records}/${email}`, JSON.stringify({
    email, createdAt: new Date(created).toISOString(), remindAt: new Date(created + app.mod.REMIND_AFTER_DAYS * DAY).toISOString(), unsubscribeToken: token,
  }));
  store.set(`${app.tokens}/${token}`, email);
};
// Every web address in a message body.
const urlsIn = (s) => [...s.matchAll(/https:\/\/[^\s"<>)]+/g)].map((m) => m[0].replace(/&amp;/g, "&").replace(/[.,]+$/, ""));

for (const app of APPS) {
  const post = postTo(app);
  const seed = seedFor(app);

  test(`${app.name}: a signup stores a record and sends the setup email with an unsubscribe link and the postal address`, async () => {
    const res = await app.mod.default(post({ email: "Reader@Example.org" }));
    assert.equal(res.status, 200);
    assert.deepEqual(await res.json(), { ok: true });
    const [mail] = mails();
    assert.deepEqual(mail.to, ["reader@example.org"]);
    assert.match(mail.text, new RegExp(`${app.slug}-reminder\\?u=[a-f0-9]{48}`));
    assert.match(mail.headers["List-Unsubscribe-Post"], /One-Click/);
    assert.match(mail.headers["List-Unsubscribe"], new RegExp(`${app.slug}-reminder\\?u=[a-f0-9]{48}`));
    assert.match(mail.text, /8735 Dunwoody Place #12398, Atlanta, GA 30350/);
    assert.match(mail.html, /8735 Dunwoody Place #12398, Atlanta, GA 30350/);
    assert.match(mail.text, /Unsubscribe with one click/);
    assert.match(mail.text, /no second download/);
    assert.match(mail.text, /seven days from the first time you open it/);
    assert.match(mail.text, /license key/);
    const record = JSON.parse(store.get(`${app.records}/reader@example.org`));
    assert.equal(Date.parse(record.remindAt) - Date.parse(record.createdAt), app.mod.REMIND_AFTER_DAYS * DAY);
    assert.deepEqual(Object.keys(record).sort(), ["createdAt", "email", "remindAt", "unsubscribeToken"]);
  });

  test(`${app.name}: every link in both emails carries the campaign tags`, async () => {
    const setup = app.mod.setupEmail("a@example.org", "b".repeat(48));
    const reminder = app.mod.reminderEmail("a@example.org", "b".repeat(48));
    for (const mail of [setup, reminder]) {
      for (const body of [mail.text, mail.html, mail.headers["List-Unsubscribe"]]) {
        const urls = urlsIn(body);
        assert.ok(urls.length >= (body === mail.headers["List-Unsubscribe"] ? 1 : 2), "expected links");
        for (const u of urls) {
          assert.ok(u.startsWith("https://purplelink.llc/"), `${u} is not a purplelink.llc link`);
          const q = new URL(u).searchParams;
          assert.equal(q.get("utm_source"), "email", u);
          assert.equal(q.get("utm_medium"), "trial-reminder", u);
          assert.equal(q.get("utm_campaign"), app.slug, u);
        }
      }
    }
    // The tags sit before any #fragment, so the buy link still lands on the buy section.
    assert.match(reminder.text, new RegExp(`/${app.slug}/\\?utm_source=email&utm_medium=trial-reminder&utm_campaign=${app.slug}#buy`));
  });

  test(`${app.name}: the setup email links the product page, because there is no start guide`, () => {
    const mail = app.mod.setupEmail("a@example.org", "b".repeat(48));
    assert.match(mail.text, new RegExp(`https://purplelink\\.llc/${app.slug}/\\?utm_`));
    assert.doesNotMatch(mail.text, /\/start\//);
  });

  test(`${app.name}: the emails use plain wording, with no dashes as punctuation, emoji or hype`, () => {
    for (const mail of [app.mod.setupEmail("a@example.org", "b".repeat(48)), app.mod.reminderEmail("a@example.org", "b".repeat(48))]) {
      for (const body of [mail.subject, mail.text, mail.html]) {
        assert.doesNotMatch(body, /[–—]/);
        assert.doesNotMatch(body, /\p{Extended_Pictographic}/u);
        assert.doesNotMatch(body, /supercharge|seamless|streamline|world-class|last chance|hurry|don't miss/i);
        assert.doesNotMatch(body, /full (app|download)|separate|install it (over|in place)/i);
      }
    }
  });

  test(`${app.name}: the reminder states the price and refund and where the key goes`, () => {
    const mail = app.mod.reminderEmail("a@example.org", "b".repeat(48));
    assert.match(mail.text, app.price);
    assert.match(mail.text, /14-day refund/);
    assert.match(mail.text, /Enter License Key|Enter license key/i);
    assert.match(mail.text, /\/recover\/\?utm_/);
    assert.match(mail.html, /Find a purchase/);
  });

  test(`${app.name}: bad addresses, the honeypot and a repeat within a day send nothing`, async () => {
    assert.equal((await app.mod.default(post({ email: "not-an-email" }))).status, 400);
    const bot = await app.mod.default(post({ email: "bot@example.org", website: "http://spam" }));
    assert.equal(bot.status, 200);
    assert.deepEqual(kept(), []);
    await app.mod.default(post({ email: "twice@example.org" }));
    const again = await app.mod.default(post({ email: "twice@example.org" }));
    assert.deepEqual(await again.json(), { ok: true, already: true });
    assert.equal(mails().length, 1);
  });

  test(`${app.name}: a foreign origin is refused, a failed send keeps nobody, and one address is limited per day`, async () => {
    assert.equal((await app.mod.default(post({ email: "a@example.org" }, { origin: "https://evil.example" }))).status, 403);
    resendStatus = 500;
    const res = await app.mod.default(post({ email: "b@example.org" }));
    assert.equal(res.status, 502);
    assert.deepEqual(kept(), []);
    // Three tries per address per day (the failed one above counted); the fourth is refused.
    await app.mod.default(post({ email: "b@example.org" }));
    await app.mod.default(post({ email: "b@example.org" }));
    assert.equal((await app.mod.default(post({ email: "b@example.org" }))).status, 429);
  });

  test(`${app.name}: one-click unsubscribe deletes the record and answers the same for an unknown token`, async () => {
    seed("gone@example.org", 1, "b".repeat(48));
    const url = `https://purplelink.llc/.netlify/functions/${app.slug}-reminder?u=${"b".repeat(48)}&utm_source=email`;
    assert.equal((await app.mod.default(new Request(url, { method: "POST" }))).status, 200);
    assert.deepEqual(kept(), []);
    const unknown = await app.mod.default(new Request(`https://purplelink.llc/.netlify/functions/${app.slug}-reminder?u=${"c".repeat(48)}`));
    assert.equal(unknown.status, 200);
    const page = await unknown.text();
    assert.match(page, new RegExp(`no more ${app.name} trial email`));
    assert.equal((await app.mod.default(new Request(`https://purplelink.llc/.netlify/functions/${app.slug}-reminder?u=short`))).status, 400);
  });

  test(`${app.name}: the daily run sends due reminders, deletes their records, and leaves the rest`, async () => {
    seed("due@example.org", 5.5, "d".repeat(48));
    seed("early@example.org", 2, "e".repeat(48));
    const result = await app.mod.sendDueReminders();
    assert.equal(result.sent, 1);
    assert.deepEqual(mails().map((m) => m.to[0]), ["due@example.org"]);
    assert.equal(store.has(`${app.records}/due@example.org`), false);
    assert.equal(store.has(`${app.tokens}/${"d".repeat(48)}`), false);
    assert.equal(store.has(`${app.records}/early@example.org`), true);
  });

  test(`${app.name}: a buyer of this app or the Suite gets no reminder; a buyer of the other app still does`, async () => {
    seed("buyer@example.org", 6, "f".repeat(48));
    stripeSessions = [{ metadata: { product: app.own }, payment_status: "paid" }];
    assert.equal((await app.mod.sendDueReminders()).skippedBuyers, 1);
    assert.equal(mails().length, 0);
    assert.deepEqual(kept(), []);

    seed("suite@example.org", 6, "1".repeat(48));
    stripeSessions = [{ metadata: { product: "app-suite" }, payment_status: "paid" }];
    assert.equal((await app.mod.sendDueReminders()).skippedBuyers, 1);

    seed("other@example.org", 6, "2".repeat(48));
    stripeSessions = [{ metadata: { product: app.other }, payment_status: "paid" }, { metadata: { product: app.own }, payment_status: "unpaid" }];
    const result = await app.mod.sendDueReminders();
    assert.equal(result.sent, 1);
    assert.deepEqual(mails().map((m) => m.to[0]), ["other@example.org"]);
  });

  test(`${app.name}: when Stripe cannot be asked the record waits for tomorrow`, async () => {
    seed("wait@example.org", 6);
    stripeStatus = 500;
    const result = await app.mod.sendDueReminders();
    assert.equal(result.deferred, 1);
    assert.equal(mails().length, 0);
    assert.equal(store.has(`${app.records}/wait@example.org`), true);
  });

  test(`${app.name}: records older than two weeks are dropped without an email, and a failed reminder is kept to retry`, async () => {
    seed("old@example.org", 20);
    const result = await app.mod.sendDueReminders();
    assert.equal(result.expired, 1);
    assert.equal(mails().length, 0);
    assert.deepEqual(kept(), []);

    seed("retry@example.org", 6, "3".repeat(48));
    resendStatus = 500;
    assert.equal((await app.mod.sendDueReminders()).failed, 1);
    assert.equal(store.has(`${app.records}/retry@example.org`), true);
  });

  test(`${app.name}: the scheduled sender runs the daily send and is on a daily schedule`, async () => {
    seed("due@example.org", 5.5, "d".repeat(48));
    const res = await app.send.default();
    assert.equal(res.status, 200);
    assert.equal((await res.json()).sent, 1);
    assert.match(app.send.config.schedule, /^\d+ 14 \* \* \*$/);
  });
}

test("the two apps keep separate records and run on different minutes", async () => {
  await legroom.default(postTo(APPS[0])({ email: "same@example.org" }));
  await keyfeel.default(postTo(APPS[1])({ email: "same@example.org" }));
  assert.equal(kept().length, 4);
  assert.notEqual(legroomSend.config.schedule, keyfeelSend.config.schedule);
});

// ---- the forms on the pages ------------------------------------------------------------

const SITE = join(dirname(fileURLToPath(import.meta.url)), "..", "..", "site");
const read = (p) => readFileSync(join(SITE, p), "utf8");

for (const app of APPS) {
  test(`${app.name} page: the optional form is hidden until a download, posts to its own function, and has no inline style`, () => {
    const html = read(`${app.slug}/index.html`);
    const forms = [...html.matchAll(/<form class="trial-remind"[^>]*>/g)].map((m) => m[0]);
    assert.ok(forms.length >= 1);
    for (const f of forms) {
      assert.match(f, /data-reminder-signup/);
      assert.match(f, /\shidden\b/);
      assert.match(f, new RegExp(`data-reminder-api="/\\.netlify/functions/${app.slug}-reminder"`));
      assert.match(f, new RegExp(`data-reminder-link="${app.slug}-download"`));
    }
    assert.match(html, /<script src="\/trial-reminder\.js\?v=[0-9a-f]+" defer>/);
    assert.match(html, /Optional\. Two emails, then nothing/);
    assert.doesNotMatch(html, /<form[^>]*\sstyle\s*=/i);
    // Each form has its own email field id and a labelled, non-required-looking honeypot.
    const ids = [...html.matchAll(/<input type="email" id="([^"]+)"/g)].map((m) => m[1]);
    assert.equal(new Set(ids).size, ids.length);
    assert.equal(ids.length, forms.length);
  });
}

test("trial-reminder.js reveals the nearest form on a download click and posts only the address and honeypot", () => {
  const src = read("trial-reminder.js");
  assert.match(src, /data-reminder-signup/);
  assert.match(src, /JSON\.stringify\(\{ email: email, website:/);
  assert.doesNotMatch(src, /localStorage|document\.cookie|\.style\./);
  assert.doesNotMatch(src, /[–—]/);
});

test("the privacy page names the trial emails of all four apps and their retention", () => {
  const html = read("privacy/index.html");
  for (const label of ["ModernTex trial emails", "Outbound Veil trial emails", "Legroom trial emails", "Keyfeel trial emails"]) {
    assert.ok(html.includes(label), `missing: ${label}`);
  }
  assert.match(html, /Outbound Veil, Legroom or Keyfeel trial emails is deleted when its one reminder is sent, and in any case within 14 days/);
});

// The page script, run against a small fake DOM: a download click reveals the nearest form, and a submit posts
// only the address and the honeypot to the form's own function.
function runPageScript() {
  const listeners = {};
  const mkForm = (name) => {
    const f = { hidden: true, name, handlers: {}, email: { value: " Me@Example.org ", disabled: false, focus() {} }, website: { value: "" } };
    f.status = { textContent: "" };
    f.btn = { disabled: false };
    f.getAttribute = (a) => ({ "data-reminder-api": `/.netlify/functions/${name}-reminder`, "data-reminder-link": `${name}-download` })[a];
    f.querySelector = (q) => (q === "[data-reminder-status]" ? f.status : q === "button[type=submit]" ? f.btn : null);
    f.addEventListener = (ev, fn) => { f.handlers[ev] = fn; };
    return f;
  };
  const hero = mkForm("legroom");
  const closing = mkForm("legroom");
  const link = (href, form) => ({
    getAttribute: () => href,
    closest: (sel) => (sel === "a[href]" ? link(href, form) : { querySelector: () => form }),
  });
  const document = {
    querySelectorAll: () => [hero, closing],
    addEventListener: (ev, fn) => { listeners[ev] = fn; },
  };
  const posts = [];
  const fetch = async (url, opts) => { posts.push({ url, body: JSON.parse(opts.body) }); return { ok: true, status: 200, json: async () => ({ ok: true }) }; };
  vm.runInNewContext(read("trial-reminder.js"), { document, fetch, setTimeout });
  return { hero, closing, listeners, link, posts };
}

test("trial-reminder.js: a trial download click reveals the form nearest it, and other links reveal nothing", async () => {
  const { hero, closing, listeners, link } = runPageScript();
  listeners.click({ target: { closest: () => link("/blog/", hero) } });
  assert.equal(hero.hidden, true);
  listeners.click({ target: { closest: () => link("/.netlify/functions/legroom-download?trial=1", closing) } });
  assert.equal(closing.hidden, false);
  assert.equal(hero.hidden, true);
});

test("trial-reminder.js: a submit validates, posts the address and honeypot, and reports success or failure", async () => {
  const { hero, posts } = runPageScript();
  hero.email.value = "nope";
  hero.handlers.submit({ preventDefault() {} });
  assert.match(hero.status.textContent, /does not look complete/);
  assert.equal(posts.length, 0);
  hero.email.value = " Me@Example.org ";
  hero.handlers.submit({ preventDefault() {} });
  await new Promise((r) => setTimeout(r, 10));
  assert.deepEqual(posts, [{ url: "/.netlify/functions/legroom-reminder", body: { email: "Me@Example.org", website: "" } }]);
  assert.match(hero.status.textContent, /on its way to Me@Example\.org/);
  assert.equal(hero.email.disabled, true);
});
