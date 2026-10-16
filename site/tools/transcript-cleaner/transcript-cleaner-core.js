/* Transcript Cleaner core. Pure functions: no DOM, no network, no storage.
   The same file runs in the page, in a Web Worker and under node --test.

   It reads WebVTT (.vtt), SubRip (.srt) and plain text with speaker labels, and
   removes the structure around the words: the WEBVTT header, cue numbers, time
   ranges and caption markup. It joins what one speaker said in a row. It never
   summarises, corrects or rewords. The only edits to the words themselves are
   joining line wraps with a space, collapsing runs of spaces, decoding the five
   HTML entities WebVTT uses, and (only if asked) removing a fixed list of
   bracketed sound tags such as [inaudible]. */
(function (root, factory) {
  var api = factory();
  if (typeof module === "object" && module && module.exports) module.exports = api;
  else root.TranscriptClean = api;
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  // Without speaker names, a silence longer than this starts a new paragraph.
  var PAUSE_SECONDS = 3;

  // ---------- reading bytes ----------
  // Returns text from raw bytes, honouring a UTF-8 or UTF-16 byte order mark.
  function decodeBytes(bytes) {
    var enc = "utf-8";
    if (bytes.length >= 2 && bytes[0] === 0xff && bytes[1] === 0xfe) enc = "utf-16le";
    else if (bytes.length >= 2 && bytes[0] === 0xfe && bytes[1] === 0xff) enc = "utf-16be";
    return new TextDecoder(enc).decode(bytes);
  }

  function normalize(text) {
    text = String(text == null ? "" : text);
    while (text.charCodeAt(0) === 0xfeff) text = text.slice(1);
    return text.indexOf("\r") === -1 ? text : text.replace(/\r\n?/g, "\n");
  }

  // ---------- timestamps ----------
  var TIME = "(?:\\d+:)?\\d{1,2}:\\d{2}(?:[.,]\\d{1,3})?";
  var TIMING_RE = new RegExp("^\\s*(" + TIME + ")\\s*-->\\s*(" + TIME + ")(?:\\s.*)?$");
  var TIMING_ANY_RE = new RegExp("^\\s*" + TIME + "\\s*-->\\s*" + TIME, "m");

  function toSeconds(s) {
    var parts = s.replace(",", ".").split(":");
    var sec = 0;
    for (var i = 0; i < parts.length; i++) sec = sec * 60 + parseFloat(parts[i]);
    return sec;
  }
  function pad2(n) { return n < 10 ? "0" + n : String(n); }
  function formatTime(sec) {
    sec = Math.max(0, Math.floor(sec));
    return pad2(Math.floor(sec / 3600)) + ":" + pad2(Math.floor((sec % 3600) / 60)) + ":" + pad2(sec % 60);
  }

  // ---------- format detection ----------
  function extOf(name) {
    var m = /\.([A-Za-z0-9]+)$/.exec(name || "");
    return m ? m[1].toLowerCase() : "";
  }
  function detectFormat(text, name) {
    var head = text.slice(0, 4000);
    if (/^\s*WEBVTT/.test(head)) return "vtt";
    var sample = text.slice(0, 60000);
    if (TIMING_ANY_RE.test(sample)) {
      if (extOf(name) === "vtt" || /<v[\s.][^>]*>/.test(sample)) return "vtt";
      return "srt";
    }
    return "text";
  }

  // ---------- markup ----------
  var ENTITIES = { amp: "&", lt: "<", gt: ">", nbsp: " ", lrm: "‎", rlm: "‏" };
  function decodeEntities(s) {
    return s.indexOf("&") === -1 ? s : s.replace(/&(amp|lt|gt|nbsp|lrm|rlm);/g, function (m, k) { return ENTITIES[k]; });
  }
  function collapse(s) { return s.replace(/\s+/g, " ").trim(); }

  var VTT_IGNORED_TAGS = { c: 1, i: 1, b: 1, u: 1, ruby: 1, rt: 1, lang: 1 };

  // One cue payload (array of lines) to [{voice, text}] pieces. Voice spans give
  // the speaker; other WebVTT tags (italic, class, timestamp) are removed.
  function vttSegments(lines) {
    var s = lines.join("\n");
    if (s.indexOf("<") === -1) return [{ voice: null, text: decodeEntities(s) }];
    var out = [], voice = null, buf = "", idx = 0;
    function flush() {
      if (buf !== "") out.push({ voice: voice, text: decodeEntities(buf) });
      buf = "";
    }
    for (;;) {
      var lt = s.indexOf("<", idx);
      if (lt === -1) { buf += s.slice(idx); break; }
      buf += s.slice(idx, lt);
      var gt = s.indexOf(">", lt);
      if (gt === -1) { buf += s.slice(lt); break; }
      var tag = s.slice(lt + 1, gt);
      idx = gt + 1;
      var vm = /^v(?:\.[^\s]*)*(?:\s+([\s\S]*))?$/.exec(tag);
      if (vm) {
        flush();
        voice = vm[1] ? collapse(decodeEntities(vm[1])) || null : null;
      } else if (tag === "/v") {
        flush();
        voice = null;
      } else {
        var nm = /^\/?([A-Za-z]+)/.exec(tag);
        if ((nm && VTT_IGNORED_TAGS[nm[1].toLowerCase()]) || /^\d+:\d\d/.test(tag)) continue;
        buf += s.slice(lt, gt + 1); // not a WebVTT tag: keep the text as written
      }
    }
    flush();
    return out;
  }

  var SRT_TAG_RE = /<\/?(?:i|b|u|s|em|strong|font|c|span)(?:\s[^>]*)?>|\{\\[^}]*\}/gi;
  function stripSrtMarkup(line) { return line.indexOf("<") === -1 && line.indexOf("{") === -1 ? line : line.replace(SRT_TAG_RE, ""); }

  // ---------- speaker labels ("Name: text") ----------
  var LABEL_RE = /^\s*([^\s:][^:]{0,58}?):(?:\s+([\s\S]*)|)$/;
  var PARTICLES = { de: 1, da: 1, di: 1, del: 1, della: 1, van: 1, von: 1, der: 1, den: 1, la: 1, le: 1, el: 1, al: 1, bin: 1, ibn: 1, of: 1, ten: 1, ter: 1 };
  var NOT_SPEAKERS = {
    note: 1, notes: 1, example: 1, warning: 1, tip: 1, http: 1, https: 1, ftp: 1, mailto: 1, file: 1, ps: 1, nb: 1,
    important: 1, summary: 1, transcript: 1, title: 1, date: 1, time: 1, duration: 1, location: 1, participants: 1,
    attendees: 1, subject: 1, topic: 1, agenda: 1, re: 1, fwd: 1, source: 1, caption: 1, language: 1, kind: 1
  };
  function validLabel(label) {
    if (label.length > 50) return false;
    if (!/^[\p{L}\p{N}]/u.test(label)) return false;
    if (/^\d+$/.test(label)) return false;
    if (/[?!;"\u201c\u201d<>{}\[\]|\\@#$%^*=~`]/.test(label)) return false;
    if (NOT_SPEAKERS[label.toLowerCase()]) return false;
    return label.split(/\s+/).length <= 6;
  }
  // Names usually start every word with a capital letter. Used where the file gives weaker evidence.
  function capitalised(label) {
    var words = label.split(/\s+/);
    for (var i = 0; i < words.length; i++) {
      var c = words[i].charAt(0);
      if (c !== c.toUpperCase() && !PARTICLES[words[i].toLowerCase()]) return false;
    }
    return true;
  }
  // {label, rest} when the line starts with a speaker-like label, else null.
  function splitLabel(line) {
    var m = LABEL_RE.exec(line);
    if (!m) return null;
    var label = collapse(m[1]);
    if (!validLabel(label)) return null;
    return { label: label, rest: m[2] || "" };
  }

  // units: arrays of lines (one per cue or paragraph). Returns an object used as
  // a set of the labels to trust, or null. Labels are trusted when most units
  // start with one (then only labels seen at the start of a unit count), or when
  // at least two different capitalised labels each repeat 3 times.
  function acceptLabels(units) {
    var counts = Object.create(null), starts = Object.create(null), labelled = 0, total = 0, names = [];
    for (var u = 0; u < units.length; u++) {
      var lines = units[u];
      if (!lines.length) continue;
      total++;
      for (var i = 0; i < lines.length; i++) {
        var m = splitLabel(lines[i]);
        if (!m) continue;
        if (!counts[m.label]) { counts[m.label] = 0; names.push(m.label); }
        counts[m.label]++;
        if (i === 0) { labelled++; starts[m.label] = true; }
      }
    }
    if (!names.length) return null;
    var keep = null;
    if (labelled >= 2 && labelled / total >= 0.5) keep = names.filter(function (k) { return starts[k]; });
    else {
      var strong = names.filter(function (k) { return counts[k] >= 3 && capitalised(k); });
      if (strong.length >= 2) keep = strong;
    }
    if (!keep || !keep.length) return null;
    var set = Object.create(null);
    keep.forEach(function (k) { set[k] = true; });
    return set;
  }

  // A cue's lines to [{speaker, text}] using trusted labels.
  function labelledSegments(lines, accepted) {
    var out = [], speaker = null, buf = [];
    function flush() { if (buf.length) out.push({ speaker: speaker, text: buf.join(" ") }); buf = []; }
    for (var i = 0; i < lines.length; i++) {
      var m = accepted ? splitLabel(lines[i]) : null;
      if (m && accepted[m.label]) { flush(); speaker = m.label; buf.push(m.rest); }
      else buf.push(lines[i]);
    }
    flush();
    return out;
  }

  // ---------- cue formats (VTT, SRT) ----------
  function parseCues(lines, warnings) {
    var cues = [], cur = null, last = null, ignoreBlock = false, joined = 0;
    for (var i = 0; i < lines.length; i++) {
      var line = lines[i];
      if (line.trim() === "") { cur = null; ignoreBlock = false; continue; }
      var tm = TIMING_RE.exec(line);
      if (tm) {
        // A cue written straight after another with no blank line between: its number belongs to this cue.
        if (cur && cur.lines.length && /^\d+$/.test(cur.lines[cur.lines.length - 1].trim())) cur.lines.pop();
        cur = { start: toSeconds(tm[1]), end: toSeconds(tm[2]), lines: [] };
        cues.push(cur);
        last = cur;
        ignoreBlock = false;
        continue;
      }
      if (cur) { cur.lines.push(line); continue; }
      if (ignoreBlock) continue;
      if (/^(WEBVTT|NOTE|STYLE|REGION)(\s|$)/.test(line)) { ignoreBlock = true; continue; }
      var next = i + 1 < lines.length ? lines[i + 1] : "";
      if (TIMING_RE.test(next)) continue; // a cue number or identifier
      if (last) { last.lines.push(line); joined++; } // text after a stray blank line inside a cue
    }
    if (joined) warnings.push(joined + " line" + (joined === 1 ? "" : "s") + " after a blank line inside a cue " + (joined === 1 ? "was" : "were") + " joined to the cue above.");
    return cues;
  }

  function parseCueFormat(lines, fmt, warnings) {
    var cues = parseCues(lines, warnings);
    // 1. Remove markup, find voice spans.
    var segsPerCue = [], hasVoice = false;
    for (var c = 0; c < cues.length; c++) {
      var segs;
      if (fmt === "vtt") {
        segs = vttSegments(cues[c].lines);
      } else {
        segs = [{ voice: null, text: cues[c].lines.map(stripSrtMarkup).join("\n") }];
      }
      segs = segs.map(function (s) { return { voice: s.voice, lines: s.text.split("\n") }; });
      for (var k = 0; k < segs.length; k++) if (segs[k].voice) hasVoice = true;
      segsPerCue.push(segs);
    }
    // 2. Without voice spans, trust "Name:" labels only when the file shows a pattern of them.
    var accepted = null;
    if (!hasVoice) {
      var units = [];
      for (c = 0; c < segsPerCue.length; c++) {
        var ls = [];
        segsPerCue[c].forEach(function (s) { s.lines.forEach(function (l) { if (l.trim() !== "") ls.push(l); }); });
        units.push(ls);
      }
      accepted = acceptLabels(units);
    }
    var pieces = [], source = hasVoice ? "voice" : accepted ? "label" : "none";
    var prevEnd = null, prevSpeaker = null, overlaps = 0;
    for (c = 0; c < cues.length; c++) {
      var cue = cues[c], first = true, cueSpeaker = null;
      segsPerCue[c].forEach(function (s) {
        var lns = s.lines.filter(function (l) { return l.trim() !== ""; });
        if (!lns.length) return;
        var parts;
        if (s.voice) parts = [{ speaker: s.voice, text: lns.join(" ") }];
        else parts = labelledSegments(lns, accepted);
        parts.forEach(function (p) {
          var speaker = p.speaker;
          if (first) cueSpeaker = speaker;
          pieces.push({
            speaker: speaker, text: p.text, start: cue.start, end: cue.end,
            brk: first && speaker == null && prevEnd != null && cue.start - prevEnd > PAUSE_SECONDS
          });
          first = false;
        });
      });
      if (!first) {
        if (prevEnd != null && cue.start < prevEnd - 0.001 && cueSpeaker != null && prevSpeaker != null && cueSpeaker !== prevSpeaker) overlaps++;
        prevEnd = cue.end;
        if (cueSpeaker != null) prevSpeaker = cueSpeaker;
      }
    }
    return { pieces: pieces, source: source, cues: cues.length, overlaps: overlaps, hasTimes: true };
  }

  // ---------- plain text ----------
  // "[Jane Doe] 00:01:02" or "Jane Doe 0:12" on a line of its own, then the words below.
  var HEADER_RE = new RegExp("^\\s*(\\[[^\\]\\n]{1,50}\\]|[^\\s\\[\\]:][^\\[\\]:\\n]{0,48}?)\\s+[\\[(]?(" + "(?:\\d+:)?\\d{1,2}:\\d{2}(?:[.,]\\d{1,3})?" + ")[\\])]?\\s*$");
  function splitHeader(line) {
    var m = HEADER_RE.exec(line);
    if (!m) return null;
    var bracketed = m[1].charAt(0) === "[";
    var label = collapse(bracketed ? m[1].slice(1, -1) : m[1]);
    if (!validLabel(label)) return null;
    return { label: label, time: toSeconds(m[2]), bracketed: bracketed };
  }

  function parseText(lines, warnings) {
    var i, n = 0, bracketed = 0, firstIsHeader = false, seenFirst = false;
    for (i = 0; i < lines.length; i++) {
      if (lines[i].trim() === "") continue;
      var h = splitHeader(lines[i]);
      if (h) { n++; if (h.bracketed) bracketed++; }
      if (!seenFirst) { seenFirst = true; firstIsHeader = !!h; }
    }
    var headerStyle = n >= 3 || bracketed >= 1 || (n >= 2 && firstIsHeader);
    var accepted = null;
    if (!headerStyle) {
      var units = [], block = [];
      for (i = 0; i < lines.length; i++) {
        if (lines[i].trim() === "") { if (block.length) units.push(block); block = []; }
        else block.push(lines[i]);
      }
      if (block.length) units.push(block);
      // Labels count whether the turns are separated by blank lines or written one per line.
      accepted = acceptLabels(units);
      if (!accepted) {
        var perLine = [];
        for (i = 0; i < lines.length; i++) if (lines[i].trim() !== "") perLine.push([lines[i]]);
        accepted = acceptLabels(perLine);
      }
    }
    var pieces = [], speaker = null, time = null, brk = false, seenBody = false, headers = 0;
    for (i = 0; i < lines.length; i++) {
      var line = lines[i];
      if (line.trim() === "") { if (seenBody) brk = true; continue; }
      if (headerStyle) {
        var hd = splitHeader(line);
        if (hd) { speaker = hd.label; time = hd.time; brk = false; seenBody = false; headers++; continue; }
      } else if (accepted) {
        var m = splitLabel(line);
        if (m && accepted[m.label]) {
          speaker = m.label;
          if (m.rest.trim() !== "") { pieces.push({ speaker: speaker, text: m.rest, start: null, end: null, brk: false }); seenBody = true; brk = false; }
          else { brk = false; seenBody = false; }
          continue;
        }
      }
      pieces.push({ speaker: speaker, text: line, start: headerStyle ? time : null, end: null, brk: brk });
      seenBody = true; brk = false;
    }
    var source = headerStyle ? "header" : accepted ? "label" : "none";
    return { pieces: pieces, source: source, cues: headers, overlaps: 0, hasTimes: headerStyle && headers > 0 };
  }

  // ---------- parse ----------
  // Reads text into pieces: {speaker, text, start, end, brk}. Independent of the output options.
  function parse(input, name) {
    var text = normalize(input);
    var warnings = [];
    var format = detectFormat(text, name);
    var lines = text.split("\n");
    var r = format === "text" ? parseText(lines, warnings) : parseCueFormat(lines, format, warnings);
    var pieces = r.pieces, inherited = 0, leading = 0, cur = null;
    for (var i = 0; i < pieces.length; i++) {
      var p = pieces[i];
      if (p.speaker != null) cur = p.speaker;
      else if (cur != null) { p.speaker = cur; inherited++; }
      else leading++;
    }
    if (format !== "text" && r.cues === 0) warnings.push("No timed cues were found in this file.");
    if (/\u0000/.test(text.slice(0, 4096))) warnings.push("This file contains binary data. It may not be a text file.");
    if (!pieces.length && !warnings.length) warnings.push("The file has no readable text.");
    if (r.overlaps) warnings.push(r.overlaps + " cue" + (r.overlaps === 1 ? "" : "s") + " start" + (r.overlaps === 1 ? "s" : "") + " before the previous speaker's cue ends. They are kept in file order.");
    if (inherited && format !== "text" && r.source !== "none") warnings.push(inherited + " piece" + (inherited === 1 ? "" : "s") + " of text had no speaker name and " + (inherited === 1 ? "was" : "were") + " kept with the speaker above.");
    return {
      format: format, source: r.source, pieces: pieces, cues: r.cues, overlaps: r.overlaps,
      inherited: inherited, leadingUnlabelled: leading, hasTimes: r.hasTimes, warnings: warnings
    };
  }

  // ---------- sound tags ----------
  var TAG_WORDS = [
    "inaudible", "unintelligible", "indistinct", "indistinct chatter", "crosstalk", "cross-talk", "cross talk",
    "overlapping speech", "overlapping voices", "overlapping", "laughter", "laughs", "laughing", "laugh", "chuckles", "chuckle",
    "giggles", "applause", "clapping", "music", "silence", "pause", "long pause", "noise", "background noise", "static",
    "sighs", "sigh", "coughs", "cough", "clears throat", "blank_audio", "blank audio", "no audio", "audio cuts out"
  ];
  var TAG_BODY = "(?:" + TAG_WORDS.map(function (w) { return w.replace(/[-\/\\^$*+?.()|[\]{}]/g, "\\$&"); }).join("|") +
    ")(?:\\s*[:?]?\\s*(?:\\d{1,2}:)?\\d{1,2}:\\d{2}(?:[.,]\\d+)?)?\\s*\\??";
  var TAG_RE = new RegExp("\\[\\s*" + TAG_BODY + "\\s*\\]|\\(\\s*" + TAG_BODY + "\\s*\\)", "gi");

  // ---------- output ----------
  // Markdown: escape what would turn plain words into formatting. Words are otherwise left as they are.
  function mdInline(s) { return s.replace(/[\\`*_<]/g, "\\$&"); }
  function mdLead(s) {
    return s.replace(/^(\s*)(?:([#>+\-])|(\d+)([.)]))/, function (m, sp, mark, num, dot) { return sp + (mark ? "\\" + mark : num + "\\" + dot); });
  }

  // output: "text" (readable text, the default), "qda" (NVivo for Mac and MAXQDA) or "nvivo-tsv" (NVivo for Windows).
  var DEFAULTS = { speakers: true, timestamps: false, paragraphs: true, tags: false, output: "text" };

  // ---------- timestamped output for NVivo and MAXQDA ----------
  // Layouts are taken from the programs' own help pages (read 2026-10-16), not from an import test:
  // - NVivo 15 for Mac imports a .txt whose paragraphs end with a timestamp, with an optional
  //   "Speaker: " before the text; its example uses the f4/f5 form #00:00:11-2# (11.2 seconds).
  //   A timestamp is the end time of the text before it and the start time of the text after it.
  // - MAXQDA (Import > Transcripts) reads #hh:mm:ss-x# (the f4 and f5transcript form) and wants a
  //   timestamp at least at the end of each paragraph. It drops a timestamp earlier than the one
  //   before it, so the times written here never go backwards.
  // - NVivo 15 for Windows imports a .txt only as delimited lines. Each line here is
  //   timespan TAB speaker TAB text, the layout NVivo Transcription exports, with the timespan
  //   written as 00:02:00.0-00:10:00.0. Every line has the same two tabs, as the help asks.
  function tenths(sec) {
    var t = Math.max(0, Math.round(sec * 10));
    var s = Math.floor(t / 10);
    return { hms: pad2(Math.floor(s / 3600)) + ":" + pad2(Math.floor((s % 3600) / 60)) + ":" + pad2(s % 60), d: t % 10 };
  }
  function f5Time(sec) { var x = tenths(sec); return "#" + x.hms + "-" + x.d + "#"; }
  function nvivoTime(sec) { var x = tenths(sec); return x.hms + "." + x.d; }

  // Counts and details both renderers report: speaker names in first-seen order with their turn counts.
  function baseStats(doc, turns, removed, dropped) {
    var counts = Object.create(null), order = [];
    turns.forEach(function (turn) {
      if (turn.speaker == null) return;
      if (!counts[turn.speaker]) { counts[turn.speaker] = 0; order.push(turn.speaker); }
      counts[turn.speaker]++;
    });
    return {
      format: doc.format, source: doc.source, cues: doc.cues, turns: turns.length,
      speakers: order.map(function (n) { return { name: n, turns: counts[n] }; }),
      tagsRemoved: removed, emptyDropped: dropped, hasTimes: doc.hasTimes, warnings: doc.warnings.slice()
    };
  }

  function renderTimed(doc, o, turns, removed, dropped) {
    // One unit per paragraph of a turn, or per cue when paragraphs are not joined.
    var units = [];
    turns.forEach(function (turn) {
      turn.paras.forEach(function (lines, q) {
        var times = turn.times[q];
        if (o.paragraphs) {
          var start = null, end = null;
          times.forEach(function (x) {
            if (start == null && x.start != null) start = x.start;
            if (x.end != null && (end == null || x.end > end)) end = x.end;
          });
          units.push({ speaker: turn.speaker, text: lines.join(" "), start: start, end: end });
        } else {
          lines.forEach(function (ln, j) { units.push({ speaker: turn.speaker, text: ln, start: times[j].start, end: times[j].end }); });
        }
      });
    });
    // A file with start times only (text with "[Name] 00:01:02" headers): a unit ends where the next one starts.
    // A next start earlier than this one is a mistake in the file: it is counted, and never used as an end.
    var backwards = 0;
    for (var i = units.length - 1, nextStart = null; i >= 0; i--) {
      var st = units[i].start;
      if (st != null && nextStart != null && nextStart < st) backwards++;
      if (units[i].end == null && nextStart != null && (st == null || nextStart > st)) units[i].end = nextStart;
      if (st != null) nextStart = st;
    }
    var out = [], last = null, colons = 0, noEnd = 0, sameTime = 0, untimed = 0, startOnly = 0;
    units.forEach(function (u) {
      var name = o.speakers && u.speaker != null ? u.speaker : null;
      if (o.output === "qda") {
        // MAXQDA drops a time earlier than the one above it, so a turn that ends at or before the turn above
        // (people talking over each other) takes that turn's time and is counted, since it then spans no audio.
        var t = u.end;
        if (t == null) noEnd++;
        else if (last != null && t <= last) { t = last; sameTime++; }
        if (t != null) last = t;
        // NVivo for Mac reads text before the first colon and space as the speaker, which matters only when no name is written.
        if (!name && /:\s/.test(u.text)) colons++;
        out.push((name ? name + ": " : "") + u.text + (t != null ? " " + f5Time(t) : ""));
      } else {
        // Each line carries its own start and end, so overlapping turns keep their real times.
        var s = u.start != null ? u.start : last, span = "";
        if (s == null) untimed++;
        else {
          span = nvivoTime(s);
          if (u.end != null && u.end > s) { span += "-" + nvivoTime(u.end); last = u.end; }
          else { startOnly++; last = s; }
        }
        out.push(span + "\t" + (name || "") + "\t" + u.text);
      }
    });
    var txt = !out.length ? "" : o.output === "qda" ? out.join("\n\n") + "\n" : out.join("\r\n") + "\r\n";
    var stats = baseStats(doc, turns, removed, dropped);
    var qda = o.output === "qda";
    stats.output = o.output;
    stats.units = units.length;
    stats.colonRows = qda ? colons : 0;
    stats.untimedRows = qda ? (doc.hasTimes ? noEnd : units.length) : untimed;
    stats.sameTimeRows = qda ? sameTime : 0;
    stats.startOnlyRows = qda || !doc.hasTimes ? 0 : startOnly;
    stats.backwardsTimes = doc.hasTimes ? backwards : 0;
    return { txt: txt, md: txt, stats: stats };
  }

  // Turns the parsed pieces into text. opts: speakers, timestamps, paragraphs, tags, output.
  function render(doc, o) {
    o = Object.assign({}, DEFAULTS, o || {});
    var turns = [], cur = null, removed = 0, dropped = 0, carry = false;
    var pieces = doc.pieces;
    for (var i = 0; i < pieces.length; i++) {
      var p = pieces[i], t = p.text;
      if (o.tags && /[\[(]/.test(t)) {
        TAG_RE.lastIndex = 0;
        t = t.replace(TAG_RE, function () { removed++; return " "; });
      }
      t = collapse(t);
      if (t === "") { dropped++; if (p.brk) carry = true; continue; }
      // With no speaker names, a pause or blank line starts a new turn, so each paragraph can carry its own time.
      var tm = { start: p.start, end: p.end };
      if (!cur || p.speaker !== cur.speaker || ((p.brk || carry) && p.speaker == null)) {
        cur = { speaker: p.speaker, start: p.start, paras: [[t]], times: [[tm]] };
        turns.push(cur);
      } else if (p.brk || carry) { cur.paras.push([t]); cur.times.push([tm]); }
      else { cur.paras[cur.paras.length - 1].push(t); cur.times[cur.times.length - 1].push(tm); }
      carry = false;
    }
    if (o.output === "qda" || o.output === "nvivo-tsv") return renderTimed(doc, o, turns, removed, dropped);
    var join = o.paragraphs ? " " : "\n";
    var txt = [], md = [];
    for (var k = 0; k < turns.length; k++) {
      var turn = turns[k];
      var showTime = o.timestamps && turn.start != null;
      var showName = o.speakers && turn.speaker != null;
      var tsText = showTime ? "[" + formatTime(turn.start) + "]" : "";
      var paras = turn.paras.map(function (lines) { return lines.join(join); });
      var prefixTxt = tsText + (showTime && showName ? " " : "") + (showName ? turn.speaker + ":" : "");
      var prefixMd = tsText + (showTime && showName ? " " : "") + (showName ? "**" + mdInline(turn.speaker) + ":**" : "");
      var block = [], blockMd = [];
      for (var q = 0; q < paras.length; q++) {
        var body = paras[q], withPrefix = q === 0 && prefixTxt !== "";
        block.push(withPrefix ? prefixTxt + " " + body : body);
        var mdLines = body.split("\n").map(function (ln, li) { ln = mdInline(ln); return withPrefix && li === 0 ? ln : mdLead(ln); });
        blockMd.push((withPrefix ? prefixMd + " " : "") + mdLines.join("  \n"));
      }
      txt.push(block.join("\n\n"));
      md.push(blockMd.join("\n\n"));
    }
    return {
      txt: txt.length ? txt.join("\n\n") + "\n" : "",
      md: md.length ? md.join("\n\n") + "\n" : "",
      stats: baseStats(doc, turns, removed, dropped)
    };
  }

  function clean(input, name, opts) { return render(parse(input, name), opts); }

  return {
    PAUSE_SECONDS: PAUSE_SECONDS, DEFAULTS: DEFAULTS,
    decodeBytes: decodeBytes, normalize: normalize, detectFormat: detectFormat,
    parse: parse, render: render, clean: clean, formatTime: formatTime, toSeconds: toSeconds
  };
});
