// Response letter template: splits pasted reviewer comments into reviewers
// and numbered comments and writes a response-letter skeleton. Runs in the
// browser; nothing is sent anywhere.
(() => {
  const $ = (id) => document.getElementById(id);
  const input = $("rl-comments");
  if (!input) return;
  const fmt = $("rl-format"), title = $("rl-title"), journal = $("rl-journal"), changes = $("rl-changes");
  const out = $("rl-output"), result = $("rl-result"), status = $("rl-status");

  const REVIEWER = /^\s*(?:#{1,6}\s*)?(?:\*\*)?\s*(?:comments?\s+(?:from|by|of)\s+(?:the\s+)?)?(reviewer|referee)\s*(?:#|no\.?)?\s*([0-9]+|[a-z])\b(?:'s)?[^.!?]{0,30}$/i;
  const EDITOR = /^\s*(?:#{1,6}\s*)?(?:\*\*)?\s*(?:comments?\s+(?:from|by|of)\s+(?:the\s+)?)?(associate editor|academic editor|handling editor|guest editor|editor(?:-in-chief)?|ae)(?:'s)?\b\s*(?:comments?(?:\s+to\s+(?:the\s+)?authors?)?)?\s*[:.]?\s*(?:\*\*)?\s*$/i;
  const GROUP = /^\s*(?:#{1,6}\s*)?(?:\*\*)?\s*(major|minor|general|specific|other|additional)\s+(?:comments?|issues|points|concerns|revisions)\s*[:.]?\s*(?:\*\*)?\s*$/i;
  const NUMBERED = /^\s*(?:(?:comment|point|issue|q)\s*)?\(?(\d{1,2}(?:\.\d{1,2})?)[.):]\s+/i;
  const BULLET = /^\s*[-*\u2022]\s+/;
  const LETTERED = /^\s*\(?([a-h]|i{1,3}|iv|v|vi{0,3})\)\s+/i;

  // Comments of one reviewer: [{text, num, group, summary}]. The reviewer's
  // own numbers are kept; bullets are numbered in order; letters split only
  // when a section has no numbers (otherwise they are sub-points).
  function splitComments(lines) {
    const hasNum = lines.some((l) => NUMBERED.test(l));
    const hasBullet = lines.some((l) => BULLET.test(l));
    const useLetters = !hasNum && !hasBullet && lines.some((l) => LETTERED.test(l));
    const marker = (l) => {
      let m = l.match(NUMBERED); if (m) return { num: m[1], rest: l.replace(NUMBERED, "") };
      if (BULLET.test(l)) return { num: "", rest: l.replace(BULLET, "") };
      if (useLetters && LETTERED.test(l)) return { num: "", rest: l.replace(LETTERED, "") };
      return null;
    };
    const items = [];
    let cur = null, group = "", intro = [];
    const push = () => { if (cur && cur.lines.join("").trim()) items.push(cur); cur = null; };
    const anyMarker = hasNum || hasBullet || useLetters;
    if (!anyMarker) {
      const paras = [];
      let buf = [];
      for (const l of lines.concat([""])) {
        const g = l.match(GROUP);
        if (g) { if (buf.join("").trim()) paras.push({ lines: buf, group }); buf = []; group = g[1].toLowerCase(); continue; }
        if (!l.trim()) { if (buf.join("").trim()) paras.push({ lines: buf, group }); buf = []; }
        else buf.push(l);
      }
      return paras.map((p) => ({ text: p.lines.join("\n").trim(), num: "", group: p.group, summary: false }));
    }
    for (const l of lines) {
      const g = l.match(GROUP);
      if (g) { push(); group = g[1].toLowerCase(); continue; }
      const m = marker(l);
      if (m) { push(); cur = { lines: [m.rest], num: m.num, group }; }
      else if (cur) cur.lines.push(l);
      else intro.push(l);
    }
    push();
    const out = [];
    const introText = intro.join("\n").trim();
    if (introText) out.push({ text: introText, num: "", group: "", summary: true });
    items.forEach((c) => out.push({ text: c.lines.join("\n").trim(), num: c.num, group: c.group, summary: false }));
    return out;
  }

  function parse(text) {
    const lines = text.replace(/\r\n?/g, "\n").split("\n");
    const sections = [];
    let cur = null;
    for (const l of lines) {
      const r = l.length < 90 && l.match(REVIEWER);
      const e = !r && l.length < 70 && l.match(EDITOR);
      if (r || e) {
        cur = { name: r ? `Reviewer ${r[2].toUpperCase()}` : "Editor", lines: [] };
        sections.push(cur);
      } else {
        if (!cur) { cur = { name: "Reviewer 1", lines: [] }; sections.push(cur); }
        cur.lines.push(l);
      }
    }
    // Merge sections that share a name (a letter that repeats a heading).
    const merged = [];
    for (const s of sections) {
      const prev = merged.find((m) => m.name === s.name);
      if (prev) prev.lines.push("", ...s.lines); else merged.push(s);
    }
    return merged
      .map((s) => {
        const comments = splitComments(s.lines);
        let n = 0;
        comments.forEach((c) => {
          if (c.summary) { c.id = "summary"; return; }
          if (c.num) { c.id = c.num; const k = parseInt(c.num, 10); if (k > n) n = k; }
          else { n += 1; c.id = String(n); }
        });
        return { name: s.name, comments };
      })
      .filter((s) => s.comments.length);
  }

  const texEscape = (t) => t
    .replace(/\\/g, "\u0000")
    .replace(/([&%$#_{}])/g, "\\$1")
    .replace(/~/g, "\\textasciitilde{}")
    .replace(/\^/g, "\\textasciicircum{}")
    .replace(/\u0000/g, "\\textbackslash{}");

  function build(sections, format) {
    const t = title.value.trim() || "[Manuscript title]";
    const j = journal.value.trim() || "[Journal]";
    const withChanges = changes.checked;
    const prefix = (s) => (s.name === "Editor" ? "E" : s.name.replace("Reviewer ", ""));
    // "Comment 2.3 (major)", or "Summary" for a reviewer's opening paragraph.
    const head = (s, c) => (c.summary ? "Summary" : `Comment ${c.id.includes(".") ? c.id : prefix(s) + "." + c.id}${c.group ? " (" + c.group + ")" : ""}`);
    const reply = (c) => (c.summary ? "[Optional: thank the reviewer; no point-by-point reply needed]" : "[Your response]");
    const intro = "Thank you for the opportunity to revise our manuscript, and thank you to the reviewers for their careful reading. We respond to each comment below. Reviewer comments are quoted, and changes in the revised manuscript are [marked in blue].";
    const out = [];
    if (format === "latex") {
      out.push("\\documentclass[11pt]{article}", "\\usepackage[margin=1in]{geometry}", "\\usepackage{xcolor}", "\\setlength{\\parindent}{0pt}", "\\setlength{\\parskip}{0.6em}", "\\begin{document}", "",
        "\\section*{Response to reviewers}", `\\textbf{Manuscript:} ${texEscape(t)}\\\\`, `\\textbf{Journal:} ${texEscape(j)}`, "", "Dear [Editor],", "", texEscape(intro), "");
      sections.forEach((s) => {
        out.push(`\\subsection*{${s.name}}`, "");
        s.comments.forEach((c) => {
          out.push(`\\paragraph{${head(s, c)}}`, "\\begin{quote}\\itshape", texEscape(c.text), "\\end{quote}", `\\textbf{Response.} ${texEscape(reply(c))}`, "");
          if (withChanges && !c.summary) out.push("\\textbf{Changes.} [Section, page and lines, or no change and why]", "");
        });
      });
      out.push("Sincerely,", "", "{[Authors]}", "", "\\end{document}");
    } else if (format === "markdown") {
      out.push("# Response to reviewers", "", `**Manuscript:** ${t}  `, `**Journal:** ${j}`, "", "Dear [Editor],", "", intro, "");
      sections.forEach((s) => {
        out.push(`## ${s.name}`, "");
        s.comments.forEach((c) => {
          out.push(`### ${head(s, c)}`, "", c.text.split("\n").map((l) => "> " + l).join("\n"), "", `**Response:** ${reply(c)}`, "");
          if (withChanges && !c.summary) out.push("**Changes:** [Section, page and lines, or no change and why]", "");
        });
      });
      out.push("Sincerely,", "[Authors]");
    } else {
      out.push("RESPONSE TO REVIEWERS", "", `Manuscript: ${t}`, `Journal: ${j}`, "", "Dear [Editor],", "", intro, "");
      sections.forEach((s) => {
        out.push(s.name.toUpperCase(), "");
        s.comments.forEach((c) => {
          out.push(`${head(s, c)}:`, c.text.split("\n").map((l) => "    " + l).join("\n"), "", `Response: ${reply(c)}`, "");
          if (withChanges && !c.summary) out.push("Changes: [Section, page and lines, or no change and why]", "");
        });
      });
      out.push("Sincerely,", "[Authors]");
    }
    return out.join("\n") + "\n";
  }

  function run() {
    const sections = parse(input.value);
    if (!sections.length) {
      result.hidden = true;
      status.textContent = input.value.trim() ? "No comments found. Paste the reviewers' text as it appears in the decision letter." : "";
      return;
    }
    out.textContent = build(sections, fmt.value);
    result.hidden = false;
    const n = sections.reduce((k, s) => k + s.comments.filter((c) => !c.summary).length, 0);
    status.textContent = `${n} comment${n === 1 ? "" : "s"} from ${sections.map((s) => s.name).join(", ")}. Check the split, then answer every one.`;
  }

  $("rl-run").addEventListener("click", run);
  [fmt, changes].forEach((el) => el.addEventListener("change", () => { if (!result.hidden) run(); }));
  [title, journal].forEach((el) => el.addEventListener("input", () => { if (!result.hidden) run(); }));

  $("rl-copy").addEventListener("click", async () => {
    try { await navigator.clipboard.writeText(out.textContent); $("rl-copy").textContent = "Copied"; }
    catch (e) { $("rl-copy").textContent = "Copy failed"; }
    setTimeout(() => { $("rl-copy").textContent = "Copy"; }, 1600);
  });
  $("rl-download").addEventListener("click", () => {
    const ext = { latex: "tex", markdown: "md", text: "txt" }[fmt.value] || "txt";
    const blob = new Blob([out.textContent], { type: "text/plain;charset=utf-8" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `response-to-reviewers.${ext}`;
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(a.href), 1000);
    if (window.plTrack) window.plTrack("response_template_download", fmt.value);
  });

  // Exposed for tests.
  window.__responseLetter = { parse, build };
})();
