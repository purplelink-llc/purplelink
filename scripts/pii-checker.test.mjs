// Tests for site/tools/pii-checker/pii-checker-core.js.
// Run: node --test scripts/pii-checker.test.mjs
//
// The cases for the ported rules follow Outbound Veil's own tests (Tests/OutboundVeilTests/RulesTests.swift and
// NoiseFilterTests.swift) so the page and the app agree. Every value here is invented. The phone cases are new:
// the app finds phone numbers with its model, so there is no app test to follow.
import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const module_ = { exports: {} };
new Function("module", "exports", fs.readFileSync(path.join(ROOT, "site/tools/pii-checker/pii-checker-core.js"), "utf8")).call(module_.exports, module_, module_.exports);
const P = module_.exports;

const found = (text, label) => P.detect(text).filter((s) => s.label === label).map((s) => s.text);
const labels = (text) => P.detect(text).map((s) => s.label);

// ---------- validators ----------

test("Luhn", () => {
  assert.equal(P.isLuhnValid("4111111111111111"), true);
  assert.equal(P.isLuhnValid("4111111111111112"), false);
  assert.equal(P.isLuhnValid(""), false);
  assert.equal(P.isLuhnValid("41111111 1111111"), false);
});

test("SSN structure: 000, 666, 900-999, group 00 and serial 0000 are not SSNs", () => {
  assert.equal(P.isValidSSN("472810094"), true);
  for (const bad of ["000121234", "666121234", "900121234", "999121234", "472001234", "472810000", "47281009", "4728100944"]) {
    assert.equal(P.isValidSSN(bad), false, bad);
  }
  assert.equal(P.isValidSSN("899121234"), true);
});

test("IBAN mod 97", () => {
  assert.equal(P.isValidIBAN("GB82 WEST 1234 5698 7654 32"), true);
  assert.equal(P.isValidIBAN("DE89370400440532013000"), true);
  assert.equal(P.isValidIBAN("GB82 WEST 1234 5698 7654 33"), false);
  assert.equal(P.isValidIBAN("GB82"), false);
});

// ---------- the rules, true positives ----------

test("SSN in every separator form", () => {
  for (const form of ["472-81-0094", "472 81 0094", "472.81.0094", "472810094"]) {
    assert.deepEqual(found(`my ssn is ${form} ok`, "SSN"), [form], form);
  }
});

test("card number needs Luhn, in 14, 15 and 16 digits", () => {
  assert.deepEqual(found("card 4111 1111 1111 1111 exp", "CREDIT_CARD"), ["4111 1111 1111 1111"]);
  assert.deepEqual(found("card 4111-1111-1111-1111.", "CREDIT_CARD"), ["4111-1111-1111-1111"]);
  assert.deepEqual(found("amex 3782 822463 10005 end", "CREDIT_CARD"), ["3782 822463 10005"]);
  assert.deepEqual(found("diners 3056 930902 5904", "CREDIT_CARD"), ["3056 930902 5904"]);
  assert.deepEqual(found("card 4111 1111 1111 1112 exp", "CREDIT_CARD"), []);
});

test("a 16-digit card is not carved into an SSN", () => {
  assert.deepEqual(labels("4111 1111 1111 1111"), ["CREDIT_CARD"]);
});

test("email, URL, IP and MAC", () => {
  assert.deepEqual(found("to alex+housing@sub.example.gov.", "EMAIL"), ["alex+housing@sub.example.gov"]);
  assert.deepEqual(found("a@b.co, c.d@e-f.org", "EMAIL"), ["a@b.co", "c.d@e-f.org"]);
  assert.deepEqual(found("see https://example.com/a?b=1 now", "URL"), ["https://example.com/a?b=1"]);
  assert.deepEqual(found("see www.example.com/x?y=2 now", "URL"), ["www.example.com/x?y=2"]);
  assert.deepEqual(found("host 192.168.1.10 up", "IP_ADDRESS"), ["192.168.1.10"]);
  assert.deepEqual(found("host 2001:db8::1 up", "IP_ADDRESS"), ["2001:db8::1"]);
  assert.deepEqual(found("mac aa:bb:cc:dd:ee:ff up", "IP_ADDRESS"), ["aa:bb:cc:dd:ee:ff"]);
});

test("the closing full stop of a sentence is not part of a web address", () => {
  assert.deepEqual(found("Open https://example.com/reset?token=abc123.", "URL"), ["https://example.com/reset?token=abc123"]);
});

test("date of birth needs a cue word", () => {
  assert.deepEqual(found("DOB 03/14/1981", "DATE_OF_BIRTH"), ["03/14/1981"]);
  assert.deepEqual(found("He was born on March 3, 1990.", "DATE_OF_BIRTH"), ["March 3, 1990"]);
  assert.deepEqual(found("Date of birth: 1981-03-14", "DATE_OF_BIRTH"), ["1981-03-14"]);
  assert.deepEqual(found("born 14 March 1981", "DATE_OF_BIRTH"), ["14 March 1981"]);
  assert.deepEqual(found("Meeting on 03/14/2026", "DATE_OF_BIRTH"), []);
  assert.deepEqual(found("Invoice dated 2026-10-21, due 2026-11-20", "DATE_OF_BIRTH"), []);
});

test("medical record number needs a cue word and a digit", () => {
  assert.deepEqual(found("MRN: 4482910", "MEDICAL_RECORD_NUMBER"), ["4482910"]);
  assert.deepEqual(found("medical record number is A-558-221", "MEDICAL_RECORD_NUMBER"), ["A-558-221"]);
  assert.deepEqual(found("patient id 77-1290", "MEDICAL_RECORD_NUMBER"), ["77-1290"]);
  assert.deepEqual(found("mrn: pending", "MEDICAL_RECORD_NUMBER"), []);
  assert.deepEqual(found("record 4482910", "MEDICAL_RECORD_NUMBER"), []);
});

test("IBAN needs a valid checksum", () => {
  assert.deepEqual(found("pay GB82 WEST 1234 5698 7654 32 today", "IBAN"), ["GB82 WEST 1234 5698 7654 32"]);
  assert.deepEqual(found("pay GB82 WEST 1234 5698 7654 33 today", "IBAN"), []);
  assert.deepEqual(found("DE89370400440532013000", "IBAN"), ["DE89370400440532013000"]);
});

test("phone numbers: North American and international shapes", () => {
  assert.deepEqual(found("call (404) 555-0182 now", "PHONE"), ["(404) 555-0182"]);
  assert.deepEqual(found("call 404-555-0182 now", "PHONE"), ["404-555-0182"]);
  assert.deepEqual(found("call 404.555.0182 now", "PHONE"), ["404.555.0182"]);
  assert.deepEqual(found("call 404 555 0182 now", "PHONE"), ["404 555 0182"]);
  assert.deepEqual(found("call +1 404 555 0182 now", "PHONE"), ["+1 404 555 0182"]);
  assert.deepEqual(found("call 1-800-555-0199.", "PHONE"), ["1-800-555-0199"]);
  assert.deepEqual(found("ring +44 20 7946 0958 today", "PHONE"), ["+44 20 7946 0958"]);
  assert.deepEqual(found("ring +442079460958 today", "PHONE"), ["+442079460958"]);
});

// ---------- false-positive traps ----------

test("order numbers, ISBNs, versions and times are not reported", () => {
  const traps = [
    "Order #84-2291 shipped on 2026-10-21 at 12:30.",
    "Order 1042938 and ticket 55-8812",
    "ISBN 978-3-16-148410-0",
    "ISBN-10 0-306-40615-2",
    "ISBN 9780306406157",
    "Tracking 1234567890",
    "Version 2.4.1 and build 1.2.3-rc1",
    "Meeting at 12:34 on 03/14/2026",
    "Total $1,234,567.89, 4 items",
    "Part no. 404-555-01",
    "Zip 30303 and 30303-1234",
    "Call me",
    "std::string and Foo::bar are not addresses",
    "Zip+4 30303-1234 and 192.168.1.10 are not Social Security numbers",
  ];
  for (const t of traps) {
    const out = P.detect(t).filter((s) => !(t.includes("192.168.1.10") && s.label === "IP_ADDRESS"));
    assert.deepEqual(out, [], t);
  }
});

test("SSN-shaped numbers that cannot be SSNs are not reported", () => {
  for (const t of ["000-12-3456", "666-12-3456", "900-12-3456", "987-65-4321", "472-00-1234", "472-81-0000"]) {
    assert.deepEqual(found(`ref ${t} end`, "SSN"), [], t);
  }
});

test("16-digit numbers that fail Luhn are not cards, and are not read as anything else", () => {
  assert.deepEqual(P.detect("4111 1111 1111 1112"), []);
  assert.deepEqual(P.detect("1234 5678 9012 3456"), []);
});

test("a ten-digit run is not an SSN, and a bare ten-digit run is not a phone number", () => {
  assert.deepEqual(found("call 404 555 0182 now", "SSN"), []);
  assert.deepEqual(found("number 4045550182", "PHONE"), []);
});

test("phone shapes that cannot be North American numbers are not reported", () => {
  for (const t of ["call 123-456-7890", "call 404-155-0182", "ref 12-404-555-0182-9", "id 404-555-01825", "x 404-555-0182-9"]) {
    assert.deepEqual(found(t, "PHONE"), [], t);
  }
});

test("web addresses with nothing sensitive in them are not reported", () => {
  for (const u of ["https://example.com/changelog", "www.example.com", "https://docs.python.org/3/library/re.html#match", "http://example.com/"]) {
    assert.equal(P.isLowRiskURL(u), true, u);
    assert.deepEqual(P.detect(`see ${u} now`), [], u);
  }
});

test("web addresses with a query string, a login or a token path are reported", () => {
  for (const u of ["https://example.com/reset?token=abc", "https://user:pw@example.com/", "https://example.com/?q=x", "https://example.com/s/a1b2c3d4e5f6a7b8c9d0e1f2g3"]) {
    assert.equal(P.isLowRiskURL(u), false, u);
    assert.deepEqual(found(`see ${u} now`, "URL"), [u], u);
  }
  assert.deepEqual(labels("see https://user:pw@example.com/ now"), ["URL"], "the email inside the address is not reported twice");
});

test("a four-part version number looks like an IPv4 address, as it does in the app", () => {
  assert.deepEqual(found("version 10.2.1.4", "IP_ADDRESS"), ["10.2.1.4"]);
  assert.deepEqual(found("version 10.2.1", "IP_ADDRESS"), []);
  assert.deepEqual(found("version 10.2.1.256", "IP_ADDRESS"), []);
});

// ---------- offsets, invisible characters, overlaps ----------

test("offsets are UTF-16 offsets in the original text", () => {
  const text = "héllo \u{1F600} 472-81-0094";
  const s = P.detect(text).find((x) => x.label === "SSN");
  assert.equal(s.start, text.indexOf("472-81-0094"));
  assert.equal(s.end, s.start + 11);
  assert.equal(text.slice(s.start, s.end), "472-81-0094");
});

test("zero-width characters between the digits do not hide a number", () => {
  const raw = "ssn 472​-81‍-0094 ok";
  const s = P.detect(raw);
  assert.equal(s.length, 1);
  assert.equal(s[0].label, "SSN");
  assert.equal(raw.slice(s[0].start, s[0].end), "472​-81‍-0094");
  assert.equal(P.stripInvisible("a­b\u{E0041}c").text, "abc");
  assert.equal(P.stripInvisible("plain \u{1F600}").identity, true);
});

test("overlaps: the longer span wins on a tie, a contained span is absorbed, a partial overlap keeps the union", () => {
  const sp = (s, e, l, score = 1) => ({ start: s, end: e, label: l, score, source: "pattern", text: "" });
  assert.deepEqual(P.mergeSpans([sp(0, 5, "PHONE"), sp(0, 8, "SSN")]).map((x) => x.label), ["SSN"]);
  assert.deepEqual(P.mergeSpans([sp(0, 10, "PHONE", 0.6), sp(2, 8, "SSN", 1)]).map((x) => x.label), ["SSN"]);
  const u = P.mergeSpans([sp(0, 6, "EMAIL"), sp(4, 10, "URL", 0.9)]);
  assert.equal(u.length, 1);
  assert.deepEqual([u[0].start, u[0].end, u[0].label], [0, 10, "EMAIL"]);
  assert.deepEqual(P.mergeSpans([sp(10, 12, "URL"), sp(0, 2, "EMAIL")]).map((x) => x.start), [0, 10]);
});

test("a long run of address characters with no @ is checked in linear time", () => {
  const t0 = Date.now();
  P.detect("a.".repeat(60000) + "b");
  P.detect("a-b".repeat(40000) + "@");
  assert.ok(Date.now() - t0 < 2000, "took " + (Date.now() - t0) + " ms");
});

// ---------- placeholders ----------

test("redaction: typed placeholders, same value same placeholder, numbered in reading order", () => {
  const text = "Mail zed@example.com or amy@example.com. SSN 472-81-0094, again 472 81 0094. Call (404) 555-0182 or +44 20 7946 0958, or (404) 555-0182. Write ZED@EXAMPLE.COM.";
  const r = P.check(text);
  assert.equal(r.redacted,
    "Mail [EMAIL_1] or [EMAIL_2]. SSN [SSN_1], again [SSN_1]. Call [PHONE_1] or [PHONE_2], or [PHONE_1]. Write [EMAIL_1].");
  assert.equal(r.total, 8);
  assert.deepEqual(r.groups.map((g) => [g.label, g.count, g.placeholders]), [
    ["SSN", 2, ["[SSN_1]"]],
    ["EMAIL", 3, ["[EMAIL_1]", "[EMAIL_2]"]],
    ["PHONE", 3, ["[PHONE_1]", "[PHONE_2]"]],
  ]);
});

test("redaction leaves text with no findings exactly as it was", () => {
  const t = "Nothing here.\n\nJust a note, 3 items, version 2.4.1.\n";
  const r = P.check(t);
  assert.equal(r.total, 0);
  assert.equal(r.redacted, t);
  assert.deepEqual(r.groups, []);
});

test("redacted text contains none of the matched values", () => {
  const text = "ssn 472-81-0094 card 4111 1111 1111 1111 mail jo@example.com dob 03/14/1981 mrn 4482910 iban GB82 WEST 1234 5698 7654 32 ip 192.168.1.10";
  const r = P.check(text);
  for (const s of r.spans) assert.ok(!r.redacted.includes(s.text), s.text);
  assert.equal(r.redacted, "ssn [SSN_1] card [CREDIT_CARD_1] mail [EMAIL_1] dob [DATE_OF_BIRTH_1] mrn [MEDICAL_RECORD_NUMBER_1] iban [IBAN_1] ip [IP_ADDRESS_1]");
});

test("names are not found, and the check says nothing about them", () => {
  const r = P.check("Jordan Sample, born in Atlanta, works as a lighthouse keeper in a town of 400.");
  assert.equal(r.total, 0);
});

test("every label has a display name, and the groups follow the label order", () => {
  for (const l of P.LABELS) assert.ok(P.DISPLAY[l], l);
  const r = P.check("ip 192.168.1.10 ssn 472-81-0094");
  assert.deepEqual(r.groups.map((g) => g.label), ["SSN", "IP_ADDRESS"]);
});

test("empty and non-string input", () => {
  assert.deepEqual(P.detect(""), []);
  assert.deepEqual(P.detect(null), []);
  assert.equal(P.check("").redacted, "");
});

test("a file with a UTF-16 byte order mark is decoded", () => {
  const bytes = new Uint8Array([0xff, 0xfe, 0x61, 0x00, 0x40, 0x00, 0x62, 0x00, 0x2e, 0x00, 0x63, 0x00, 0x6f, 0x00]);
  assert.equal(P.decodeBytes(bytes).replace(/^﻿/, ""), "a@b.co");
});

test("an IPv4 address and a ZIP+4 are not read as Social Security numbers (this differs from the app on purpose)", () => {
  assert.deepEqual(labels("host 192.168.1.10 up"), ["IP_ADDRESS"]);
  assert.deepEqual(found("ZIP 30303-1234", "SSN"), []);
  assert.deepEqual(found("ssn 472-81-0094", "SSN"), ["472-81-0094"]);
  assert.deepEqual(found("ssn 472-81.0094", "SSN"), [], "mixed separators are not one of the written forms");
});
