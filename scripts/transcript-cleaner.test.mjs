// Tests for site/tools/transcript-cleaner/transcript-cleaner-core.js.
// Run: node --test scripts/transcript-cleaner.test.mjs
//
// Every fixture is synthetic. The files in scripts/fixtures/transcript-cleaner/ were written by hand
// from the documented formats (WebVTT voice spans as Microsoft Teams writes them, "Name: text" cue
// payloads as Zoom writes them, SubRip, and speaker-labelled text). No real recording or real
// person is involved, and no real Zoom or Teams export has been tested yet.
import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const FIX = path.join(ROOT, "scripts/fixtures/transcript-cleaner");

function loadUmd(file) {
  const module = { exports: {} };
  new Function("module", "exports", fs.readFileSync(file, "utf8")).call(module.exports, module, module.exports);
  return module.exports;
}
const TC = loadUmd(path.join(ROOT, "site/tools/transcript-cleaner/transcript-cleaner-core.js"));
const fx = (n) => fs.readFileSync(path.join(FIX, n), "utf8");
const words = (s) => s.split(/\s+/).filter(Boolean);
const names = (r) => r.stats.speakers.map((s) => s.name);

// ---------- the three documented formats ----------

test("zoom-style VTT: name labels, merged turns, no header, numbers or times", () => {
  const r = TC.clean(fx("zoom-style.vtt"), "meeting.vtt", { speakers: true, timestamps: false });
  assert.equal(r.stats.format, "vtt");
  assert.equal(r.stats.source, "label");
  assert.deepEqual(names(r), ["Jane Doe", "Alex Sample", "Sam Rivera"]);
  assert.equal(r.txt, [
    "Jane Doe: Thanks for making time today. I would like to start with how you came to the project.",
    "Alex Sample: Sure. I joined in 2021, after the second round of hiring, and I was on the data side at first. Then the team moved and I took over the survey work.",
    "Jane Doe: Did that change how you saw your role? [inaudible]",
    "Alex Sample: Yes. [laughter] Well, mostly. I stopped thinking of it as a side job and said so to my manager.",
    "Sam Rivera: Can I add something here?",
    "Alex Sample: Of course, go ahead.",
  ].join("\n\n") + "\n");
  assert.doesNotMatch(r.txt, /WEBVTT|-->|^\d+$/m);
  assert.equal(r.stats.turns, 6);
});

test("teams-style VTT: voice spans give the speaker; cue ids, NOTE blocks, italics and entities are handled", () => {
  const r = TC.clean(fx("teams-style.vtt"), "teams.vtt", {});
  assert.equal(r.stats.source, "voice");
  assert.deepEqual(names(r), ["Jane Doe", "Alex Sample"]);
  assert.equal(r.txt, [
    "Jane Doe: Thanks for making time today.",
    "Alex Sample: Sure. I joined in 2021 & started on the data side. Then I moved to the survey team, which was a bigger change than I expected.",
    "Jane Doe: Was that your choice?",
    "Alex Sample: Partly. 5 < 6 hires left, so yes.",
  ].join("\n\n") + "\n");
  assert.doesNotMatch(r.txt, /7b1c0e5a|NOTE|Synthetic|<\/?[a-z]/);
});

test("SRT without speakers: indexes, markup and times go; a long pause starts a new paragraph", () => {
  const r = TC.clean(fx("plain.srt"), "talk.srt", {});
  assert.equal(r.stats.format, "srt");
  assert.equal(r.stats.source, "none");
  assert.deepEqual(r.stats.speakers, []);
  assert.equal(r.txt,
    "Welcome back. Today we look at how the survey was built. The first version had forty questions.\n\n" +
    "After the pilot we cut it to twenty-two. Note: that number is from the pilot only. http://example.org: the form is still online.\n");
});

test("SRT with Name: labels only on the first cue of a turn: the rest stay with that speaker", () => {
  const r = TC.clean(fx("interview.srt"), "i.srt", {});
  assert.equal(r.stats.source, "label");
  assert.equal(r.txt, [
    "Interviewer: Tell me about the first week.",
    "Participant: It was slow at first. Nobody had set up my account yet.",
    "Interviewer: And then?",
    "Participant: Then it got busy.",
  ].join("\n\n") + "\n");
  assert.ok(r.stats.warnings.some((w) => /no speaker name/.test(w)));
});

test("plain text with labels keeps paragraphs and joins repeated speakers", () => {
  const r = TC.clean(fx("labelled.txt"), "notes.txt", {});
  assert.equal(r.stats.format, "text");
  assert.equal(r.txt, [
    "Interviewer: Tell me about the first week.",
    "Participant: It was slow at first. Nobody had set up my account yet.\n\nThe second week was different.",
    "Interviewer: In what way?",
    "Participant: Busier. Much busier.",
  ].join("\n\n") + "\n");
});

test("plain text with one labelled line per turn and no blank lines", () => {
  const r = TC.clean("Interviewer: Hi.\nParticipant: Hello.\nInterviewer: Ready?\nParticipant: Yes.\n", "c.txt", {});
  assert.equal(r.stats.source, "label");
  assert.equal(r.txt, "Interviewer: Hi.\n\nParticipant: Hello.\n\nInterviewer: Ready?\n\nParticipant: Yes.\n");
});

test("text with '[Name] time' headers (the layout of Zoom's audio transcript text file)", () => {
  const r = TC.clean(fx("zoom-audio-transcript.txt"), "audio_transcript.txt", { timestamps: true });
  assert.equal(r.stats.source, "header");
  assert.equal(r.txt, [
    "[00:00:03] Jane Doe: Thanks for making time today.",
    "[00:00:07] Alex Sample: Sure. I joined in 2021. Then the team moved. I took over the survey work.",
    "[00:00:19] Jane Doe: Did that change how you saw your role?",
  ].join("\n\n") + "\n");
});

// ---------- options ----------

test("options: speaker names off keeps the turn breaks", () => {
  const r = TC.clean(fx("teams-style.vtt"), "t.vtt", { speakers: false });
  assert.equal(r.txt.split("\n\n").length, 4);
  assert.doesNotMatch(r.txt, /Jane Doe|Alex Sample/);
  assert.match(r.txt, /^Thanks for making time today\.\n\nSure\./);
});

test("options: a timestamp per turn, with and without names", () => {
  const withNames = TC.clean(fx("teams-style.vtt"), "t.vtt", { timestamps: true });
  assert.match(withNames.txt, /^\[00:00:00\] Jane Doe: Thanks/);
  assert.match(withNames.txt, /\n\n\[00:00:04\] Alex Sample: Sure\./);
  const bare = TC.clean(fx("teams-style.vtt"), "t.vtt", { timestamps: true, speakers: false });
  assert.match(bare.txt, /^\[00:00:00\] Thanks/);
});

test("options: lines are kept one per cue when paragraph merging is off", () => {
  const r = TC.clean(fx("teams-style.vtt"), "t.vtt", { paragraphs: false });
  assert.match(r.txt, /Alex Sample: Sure\. I joined in 2021 & started on the data side\.\nThen I moved to the survey team, which was a bigger change than I expected\.\n\nJane Doe:/);
});

test("options: bracketed sound tags are removed only when asked, and only from a fixed list", () => {
  const src = "WEBVTT\n\n00:00:01.000 --> 00:00:02.000\nAnn Lee: Well [laughter] yes [inaudible 00:00:02] and [NAME] said (crosstalk) that [sic] is wrong.\n\n" +
    "00:00:03.000 --> 00:00:04.000\nAnn Lee: [Music]\n\n00:00:05.000 --> 00:00:06.000\nBo Chan: Fine.\n";
  const off = TC.clean(src, "a.vtt", { tags: false });
  assert.match(off.txt, /\[laughter\].*\[inaudible 00:00:02\].*\(crosstalk\)/);
  const on = TC.clean(src, "a.vtt", { tags: true });
  assert.equal(on.txt, "Ann Lee: Well yes and [NAME] said that [sic] is wrong.\n\nBo Chan: Fine.\n");
  assert.equal(on.stats.tagsRemoved, 4);
  assert.equal(on.stats.emptyDropped, 1);
});

test("render can be called again on one parse with different options", () => {
  const doc = TC.parse(fx("teams-style.vtt"), "t.vtt");
  const a = TC.render(doc, { speakers: true });
  const b = TC.render(doc, { speakers: false });
  assert.notEqual(a.txt, b.txt);
  assert.equal(TC.render(doc, { speakers: true }).txt, a.txt);
});

// ---------- the wording is never changed ----------

test("wording check: the words in the output are the words in the cues, in order", () => {
  for (const f of ["zoom-style.vtt", "teams-style.vtt", "plain.srt", "interview.srt"]) {
    const raw = fx(f).replace(/\r/g, "");
    const lines = raw.split("\n");
    const payload = [];
    let inCue = false;
    for (const l of lines) {
      if (/-->/.test(l)) { inCue = true; continue; }
      if (l.trim() === "") { inCue = false; continue; }
      if (inCue) payload.push(l);
    }
    let expected = payload.join(" ")
      .replace(/<\/?[a-z][^>]*>/gi, "").replace(/\{\\[^}]*\}/g, "")
      .replace(/&amp;/g, "&").replace(/&lt;/g, "<");
    const out = TC.clean(fx(f), f, { speakers: true, timestamps: false });
    // Remove only the labels the cleaner reports.
    let got = out.txt;
    for (const n of names(out)) got = got.split(n + ": ").join("");
    for (const n of names(out)) expected = expected.split(n + ": ").join("");
    assert.deepEqual(words(got), words(expected), f);
  }
});

// ---------- edge cases ----------

test("BOM and CRLF line endings read the same as clean LF", () => {
  const crlf = "﻿" + fx("teams-style.vtt").replace(/\n/g, "\r\n");
  assert.equal(TC.clean(crlf, "t.vtt", {}).txt, TC.clean(fx("teams-style.vtt"), "t.vtt", {}).txt);
  const cr = fx("zoom-style.vtt").replace(/\n/g, "\r");
  assert.equal(TC.clean(cr, "z.vtt", {}).txt, TC.clean(fx("zoom-style.vtt"), "z.vtt", {}).txt);
});

test("UTF-8 and UTF-16 files with a byte order mark are decoded", () => {
  const text = fx("teams-style.vtt");
  const utf8 = Buffer.concat([Buffer.from([0xef, 0xbb, 0xbf]), Buffer.from(text, "utf8")]);
  assert.equal(TC.decodeBytes(new Uint8Array(utf8)), text);
  const u16 = Buffer.concat([Buffer.from([0xff, 0xfe]), Buffer.from(text, "utf16le")]);
  assert.equal(TC.decodeBytes(new Uint8Array(u16)), text);
  const be = Buffer.from(text, "utf16le");
  be.swap16();
  assert.equal(TC.decodeBytes(new Uint8Array(Buffer.concat([Buffer.from([0xfe, 0xff]), be]))), text);
  assert.equal(TC.clean(TC.decodeBytes(new Uint8Array(u16)), "t.vtt", {}).stats.source, "voice");
});

test("empty and whitespace-only cues are dropped; an empty file gives a warning, not a crash", () => {
  const src = "WEBVTT\n\n1\n00:00:01.000 --> 00:00:02.000\n\n2\n00:00:02.000 --> 00:00:03.000\n   \n\n3\n00:00:03.000 --> 00:00:04.000\n<v Ann Lee></v>\n\n4\n00:00:04.000 --> 00:00:05.000\n<v Ann Lee>Hello.</v>\n";
  const r = TC.clean(src, "e.vtt", {});
  assert.equal(r.txt, "Ann Lee: Hello.\n");
  const none = TC.clean("", "e.txt", {});
  assert.equal(none.txt, "");
  assert.ok(none.stats.warnings.length >= 1);
  assert.equal(TC.clean("WEBVTT\n\n", "e.vtt", {}).txt, "");
  assert.doesNotThrow(() => TC.clean(null, "n.txt", {}));
});

test("multi-line cues are joined with a space; extra spaces are collapsed", () => {
  const src = "WEBVTT\n\n00:00:01.000 --> 00:00:04.000\n<v Ann Lee>one two\nthree   four\n  five</v>\n";
  assert.equal(TC.clean(src, "m.vtt", {}).txt, "Ann Lee: one two three four five\n");
});

test("missing speakers: a cue with no name stays with the speaker above; text before any speaker has none", () => {
  const src = "WEBVTT\n\n00:00:00.000 --> 00:00:01.000\nIntro line with no speaker.\n\n" +
    "00:00:01.000 --> 00:00:02.000\n<v Ann Lee>First.</v>\n\n00:00:02.000 --> 00:00:03.000\nSecond with no tag.\n\n" +
    "00:00:03.000 --> 00:00:04.000\n<v Bo Chan>Third.</v>\n";
  const r = TC.clean(src, "m.vtt", {});
  assert.equal(r.txt, "Intro line with no speaker.\n\nAnn Lee: First. Second with no tag.\n\nBo Chan: Third.\n");
  assert.deepEqual(names(r), ["Ann Lee", "Bo Chan"]);
});

test("overlapping speakers: two voices in one cue, and overlapping time ranges, keep file order", () => {
  const src = "WEBVTT\n\n00:00:01.000 --> 00:00:05.000\n<v Ann Lee>I think so</v>\n<v Bo Chan>Yes, me too</v>\n\n" +
    "00:00:03.000 --> 00:00:06.000\n<v Ann Lee>and then we left.</v>\n\n00:00:04.000 --> 00:00:07.000\n<v Bo Chan>Right.</v>\n";
  const r = TC.clean(src, "o.vtt", {});
  assert.equal(r.txt, "Ann Lee: I think so\n\nBo Chan: Yes, me too\n\nAnn Lee: and then we left.\n\nBo Chan: Right.\n");
  assert.equal(r.stats.turns, 4);
  assert.ok(r.stats.warnings.some((w) => /before the previous speaker/.test(w)), r.stats.warnings.join("|"));
});

test("two labelled lines in one cue are two speakers", () => {
  const src = "WEBVTT\n\n00:00:01.000 --> 00:00:03.000\nAnn Lee: Ready?\nBo Chan: Yes.\n\n00:00:03.000 --> 00:00:04.000\nAnn Lee: Go.\n\n00:00:04.000 --> 00:00:05.000\nBo Chan: Done.\n";
  assert.equal(TC.clean(src, "l.vtt", {}).txt, "Ann Lee: Ready?\n\nBo Chan: Yes.\n\nAnn Lee: Go.\n\nBo Chan: Done.\n");
});

test("a speaker with a lowercase display name is read when the file labels most cues", () => {
  const src = "WEBVTT\n\n00:00:01.000 --> 00:00:02.000\nben: hi\n\n00:00:02.000 --> 00:00:03.000\niPhone: hello\n\n00:00:03.000 --> 00:00:04.000\nben: ok\n";
  assert.equal(TC.clean(src, "l.vtt", {}).txt, "ben: hi\n\niPhone: hello\n\nben: ok\n");
});

test("false labels: times, links, 'Note:' and one-off prefixes are not speakers", () => {
  const src = "1\n00:00:01,000 --> 00:00:02,000\nAt 10:30 we met.\n\n2\n00:00:02,000 --> 00:00:03,000\nNote: this one is odd.\n\n" +
    "3\n00:00:03,000 --> 00:00:04,000\nhttps://example.org is the page.\n\n4\n00:00:04,000 --> 00:00:05,000\nThe rule was: be quick.\n";
  const r = TC.clean(src, "n.srt", {});
  assert.equal(r.stats.source, "none");
  assert.equal(r.txt, "At 10:30 we met. Note: this one is odd. https://example.org is the page. The rule was: be quick.\n");
});

test("one speaker label repeated on its own is not enough in an otherwise unlabelled file", () => {
  const lines = [];
  for (let i = 0; i < 8; i++) lines.push(`${i + 1}\n00:00:${String(i * 2).padStart(2, "0")},000 --> 00:00:${String(i * 2 + 1).padStart(2, "0")},500\n${i === 3 || i === 6 ? "Question: is this a speaker" : "Plain words here"}`);
  assert.equal(TC.clean(lines.join("\n\n") + "\n", "q.srt", {}).stats.source, "none");
});

test("timing lines with settings, hour-less times, comma or dot milliseconds", () => {
  const src = "WEBVTT\n\n01:02.500 --> 01:04.000 align:start position:0%\n<v Ann Lee>Short form.</v>\n\n1:00:00.000 --> 1:00:02,000\n<v Ann Lee>Hour form.</v>\n";
  const r = TC.clean(src, "t.vtt", { timestamps: true });
  assert.equal(r.txt, "[00:01:02] Ann Lee: Short form. Hour form.\n");
  const r2 = TC.clean(src.replace("<v Ann Lee>Hour", "<v Bo Chan>Hour"), "t.vtt", { timestamps: true });
  assert.match(r2.txt, /\[01:00:00\] Bo Chan: Hour form\./);
});

test("NOTE, STYLE and REGION blocks and the header text are ignored", () => {
  const src = "WEBVTT - Interview\nKind: captions\n\nSTYLE\n::cue { color: red }\n\nREGION\nid:r1\n\nNOTE\nthis is a comment\nover two lines\n\n00:00:01.000 --> 00:00:02.000\n<v Ann Lee>Kept.</v>\n";
  assert.equal(TC.clean(src, "n.vtt", {}).txt, "Ann Lee: Kept.\n");
});

test("a cue number glued to the cue above (no blank line) is not read as words", () => {
  const src = "1\n00:00:01,000 --> 00:00:02,000\nAnn Lee: First.\n2\n00:00:02,000 --> 00:00:03,000\nAnn Lee: Second.\n";
  assert.equal(TC.clean(src, "g.srt", {}).txt, "Ann Lee: First. Second.\n");
});

test("a stray blank line inside a cue joins the rest of the text to that cue, with a warning", () => {
  const src = "1\n00:00:01,000 --> 00:00:03,000\nFirst part\n\nsecond part\n\n2\n00:00:04,000 --> 00:00:05,000\nNext.\n";
  const r = TC.clean(src, "b.srt", {});
  assert.equal(r.txt, "First part second part Next.\n");
  assert.ok(r.stats.warnings.some((w) => /blank line inside a cue/.test(w)));
});

test("markdown: names in bold, special characters escaped, hard breaks when lines are kept", () => {
  const src = "WEBVTT\n\n00:00:01.000 --> 00:00:02.000\n<v Ann_Lee>Use *this* and a_b and `code`.</v>\n\n00:00:02.000 --> 00:00:03.000\n<v Bo Chan># not a heading\n- not a list</v>\n";
  const r = TC.clean(src, "m.vtt", { paragraphs: false });
  assert.match(r.md, /^\*\*Ann\\_Lee:\*\* Use \\\*this\\\* and a\\_b and \\`code\\`\./);
  assert.match(r.md, /\*\*Bo Chan:\*\* # not a heading\n?/);
  const two = "WEBVTT\n\n00:00:01.000 --> 00:00:02.000\n<v Ann Lee>one</v>\n\n00:00:02.000 --> 00:00:03.000\n<v Ann Lee>- two</v>\n\n00:00:03.000 --> 00:00:04.000\n<v Ann Lee>1. three</v>\n";
  const r2 = TC.clean(two, "m.vtt", { paragraphs: false });
  assert.equal(r2.md, "**Ann Lee:** one  \n\\- two  \n1\\. three\n");
});

test("plain text: one block of unlabelled paragraphs keeps its paragraphs and wording", () => {
  const r = TC.clean("First paragraph line one.\nline two.\n\nSecond paragraph.\n", "p.txt", {});
  assert.equal(r.stats.source, "none");
  assert.equal(r.txt, "First paragraph line one. line two.\n\nSecond paragraph.\n");
  const lines = TC.clean("First paragraph line one.\nline two.\n\nSecond paragraph.\n", "p.txt", { paragraphs: false });
  assert.equal(lines.txt, "First paragraph line one.\nline two.\n\nSecond paragraph.\n");
});

test("format detection by header, by timing lines and by file name", () => {
  assert.equal(TC.detectFormat("WEBVTT\n\n", "x.txt"), "vtt");
  assert.equal(TC.detectFormat("1\n00:00:01,000 --> 00:00:02,000\nhi", "x.txt"), "srt");
  assert.equal(TC.detectFormat("00:00:01.000 --> 00:00:02.000\n<v A>hi</v>", "x.vtt"), "vtt");
  assert.equal(TC.detectFormat("just words", "x.srt"), "text");
});

test("a VTT cue's literal angle brackets that are not WebVTT tags stay as written", () => {
  const src = "WEBVTT\n\n00:00:01.000 --> 00:00:02.000\n<v Ann Lee>use <script> carefully and a <b>bold</b> word</v>\n";
  assert.equal(TC.clean(src, "a.vtt", {}).txt, "Ann Lee: use <script> carefully and a bold word\n");
});

// ---------- size ----------

test("a very large file (about 250,000 cues, 37 MB) cleans in a few seconds", () => {
  const parts = ["WEBVTT\n\n"];
  const sp = ["Jane Doe", "Alex Sample", "Sam Rivera"];
  for (let i = 0; i < 250000; i++) {
    const t = i * 2, h = String(Math.floor(t / 3600)).padStart(2, "0"), m = String(Math.floor((t % 3600) / 60)).padStart(2, "0"), s = String(t % 60).padStart(2, "0");
    const s2 = String((t + 1) % 60).padStart(2, "0");
    parts.push(`${i + 1}\n${h}:${m}:${s}.000 --> ${h}:${m}:${s2}.500\n${sp[Math.floor(i / 3) % 3]}: Cue number ${i} has some ordinary words in it, so the file is about the size of a long recording.\n\n`);
  }
  const big = parts.join("");
  assert.ok(big.length > 30e6, "fixture is " + big.length);
  const t0 = process.hrtime.bigint();
  const r = TC.clean(big, "big.vtt", { timestamps: true, tags: true });
  const ms = Number(process.hrtime.bigint() - t0) / 1e6;
  assert.equal(r.stats.cues, 250000);
  assert.equal(r.stats.turns, Math.ceil(250000 / 3));
  assert.match(r.txt, /^\[00:00:00\] Jane Doe: Cue number 0 has some/);
  assert.ok(ms < 8000, "took " + Math.round(ms) + " ms");
  console.log("  large file: " + Math.round(ms) + " ms for " + (big.length / 1e6).toFixed(1) + " MB");
});

test("a file of one enormous line does not hang", () => {
  const line = "word ".repeat(2_000_000);
  const t0 = Date.now();
  const r = TC.clean(line, "one.txt", {});
  assert.ok(Date.now() - t0 < 3000);
  assert.equal(r.txt.length, line.trim().length + 1);
});
