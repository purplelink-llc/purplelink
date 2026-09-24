// Response letter template: splits pasted reviewer comments into reviewers
// and numbered comments and writes a response-letter skeleton. Runs in the
// browser; nothing is sent anywhere.
(() => {
  const $ = (id) => document.getElementById(id);
  const input = $("rl-comments");
  if (!input) return;
  const fmt = $("rl-format"), title = $("rl-title"), journal = $("rl-journal"), changes = $("rl-changes");
  const out = $("rl-output"), result = $("rl-result"), status = $("rl-status");

  const REVIEWER = /^\s*(?:#{1,6}\s*)?(?:\*\*)?\s*(reviewer|referee)\s*(?:#|no\.?)?\s*([0-9]+|[a-z])\b[^.!?]{0,30}$/i;
  const EDITOR = /^\s*(?:#{1,6}\s*)?(?:\*\*)?\s*(associate editor|academic editor|handling editor|editor(?:-in-chief)?|ae)\b\s*(?:comments?)?\s*[:.]?\s*(?:\*\*)?\s*$/i;
  const MARKER = /^\s*(?:(?:comment|point|issue|q)\s*)?\(?(\d{1,2}(?:\.\d{1,2})?)[.):]\s+|^\s*[-*•]\s+/i;

  function splitComments(lines) {
    const items = [];
    let cur = null, intro = [];
    const hasMarkers = lines.some((l) => MARKER.test(l));
    if (hasMarkers) {
      for (const l of lines) {
        if (MARKER.test(l)) { if (cur) items.push(cur); cur = [l.replace(MARKER, "")]; }
        else if (cur) cur.push(l);
        else intro.push(l);
      }
      if (cur) items.push(cur);
      const introText = intro.join("\n").trim();
      const texts = items.map((c) => c.join("\n").trim()).filter(Boolean);
      return introText ? [introText, ...texts] : texts;
    }
    return lines.join("\n").split(/\n\s*\n/).map((p) => p.trim()).filter(Boolean);
  }

  function parse(text) {
    const lines = text.replace(/\r\n?/g, "\n").split("\n");
    const sections = [];
    let cur = null;
    for (const l of lines) {
      const r = l.length < 90 && l.match(REVIEWER);
      const e = !r && l.length < 60 && l.match(EDITOR);
      if (r || e) {
        cur = { name: r ? `Reviewer ${r[2].toUpperCase()}` : "Editor", lines: [] };
        sections.push(cur);
      } else {
        if (!cur) { cur = { name: "Reviewer 1", lines: [] }; sections.push(cur); }
        cur.lines.push(l);
      }
    }
    return sections
      .map((s) => ({ name: s.name, comments: splitComments(s.lines) }))
      .filter((s) => s.comments.length);
  }

  const texEscape = (t) => t
    .replace(/\\/g, "\\textbackslash{}")
    .replace(/([&%$#_{}])/g, "\\$1")
    .replace(/~/g, "\\textasciitilde{}")
    .replace(/\^/g, "\\textasciicircum{}");

  function build(sections, format) {
    const t = title.value.trim() || "[Manuscript title]";
    const j = journal.value.trim() || "[Journal]";
    const withChanges = changes.checked;
    const id = (si, ci) => (sections[si].name === "Editor" ? `E.${ci + 1}` : `${sections[si].name.replace("Reviewer ", "")}.${ci + 1}`);
    const intro = "Thank you for the opportunity to revise our manuscript, and thank you to the reviewers for their careful reading. We respond to each comment below. Reviewer comments are quoted, and changes in the revised manuscript are [marked in blue].";
    const out = [];
    if (format === "latex") {
      out.push("\\documentclass[11pt]{article}", "\\usepackage[margin=1in]{geometry}", "\\usepackage{xcolor}", "\\setlength{\\parindent}{0pt}", "\\setlength{\\parskip}{0.6em}", "\\begin{document}", "",
        "\\section*{Response to reviewers}", `\\textbf{Manuscript:} ${texEscape(t)}\\\\`, `\\textbf{Journal:} ${texEscape(j)}`, "", "Dear [Editor],", "", texEscape(intro), "");
      sections.forEach((s, si) => {
        out.push(`\\subsection*{${s.name}}`, "");
        s.comments.forEach((c, ci) => {
          out.push(`\\paragraph{Comment ${id(si, ci)}}`, "\\begin{quote}\\itshape", texEscape(c), "\\end{quote}", "\\textbf{Response.} [Your response]", "");
          if (withChanges) out.push("\\textbf{Changes.} [Section, page and lines, or no change and why]", "");
        });
      });
      out.push("Sincerely,", "", "{[Authors]}", "", "\\end{document}");
    } else if (format === "markdown") {
      out.push("# Response to reviewers", "", `**Manuscript:** ${t}  `, `**Journal:** ${j}`, "", "Dear [Editor],", "", intro, "");
      sections.forEach((s, si) => {
        out.push(`## ${s.name}`, "");
        s.comments.forEach((c, ci) => {
          out.push(`### Comment ${id(si, ci)}`, "", c.split("\n").map((l) => "> " + l).join("\n"), "", "**Response:** [Your response]", "");
          if (withChanges) out.push("**Changes:** [Section, page and lines, or no change and why]", "");
        });
      });
      out.push("Sincerely,", "[Authors]");
    } else {
      out.push("RESPONSE TO REVIEWERS", "", `Manuscript: ${t}`, `Journal: ${j}`, "", "Dear [Editor],", "", intro, "");
      sections.forEach((s, si) => {
        out.push(s.name.toUpperCase(), "");
        s.comments.forEach((c, ci) => {
          out.push(`Comment ${id(si, ci)}:`, c.split("\n").map((l) => "    " + l).join("\n"), "", "Response: [Your response]", "");
          if (withChanges) out.push("Changes: [Section, page and lines, or no change and why]", "");
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
    const n = sections.reduce((k, s) => k + s.comments.length, 0);
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
