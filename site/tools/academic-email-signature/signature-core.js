// Academic email signature: pure logic, no DOM. Loaded by the page and by the node test.
// Everything that reaches the HTML output goes through esc() or a validator below.
(function (root) {
  "use strict";

  var ORCID_ICON_URL = "https://purplelink.llc/assets/orcid-id-16.png";
  var MAX_FIELD = 300;

  var SANS = "Arial, Helvetica, sans-serif";
  var SERIF = "Georgia, 'Times New Roman', serif";

  function esc(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function clean(s) {
    // One line, no control characters, bounded length.
    return String(s == null ? "" : s)
      .replace(/[\u0000-\u001f\u007f]+/g, " ")
      .replace(/\s+/g, " ")
      .trim()
      .slice(0, MAX_FIELD);
  }

  // ORCID iD: 15 digits plus a check character (0-9 or X), ISO 7064 MOD 11-2.
  function orcidCheckChar(first15) {
    var total = 0;
    for (var i = 0; i < 15; i++) total = (total + Number(first15.charAt(i))) * 2;
    var result = (12 - (total % 11)) % 11;
    return result === 10 ? "X" : String(result);
  }

  // Returns { ok, id, url, error }. Accepts bare digits, hyphenated, or an orcid.org URL.
  function parseOrcid(input) {
    var s = clean(input);
    if (!s) return { ok: false, empty: true };
    s = s.replace(/^https?:\/\/(www\.)?orcid\.org\//i, "").replace(/^orcid(\s*iD)?\s*[:#]?\s*/i, "").replace(/\/+$/, "");
    var compact = s.replace(/[-\s]/g, "").toUpperCase();
    if (!/^\d{15}[\dX]$/.test(compact)) {
      return { ok: false, error: "An ORCID iD has 16 characters: 15 digits and a last digit or X, like 0000-0002-1825-0097." };
    }
    if (orcidCheckChar(compact.slice(0, 15)) !== compact.charAt(15)) {
      return { ok: false, error: "The last character does not match the other digits, so this iD has a typo." };
    }
    var id = compact.replace(/^(.{4})(.{4})(.{4})(.{4})$/, "$1-$2-$3-$4");
    return { ok: true, id: id, url: "https://orcid.org/" + id };
  }

  // http(s) only. Adds https:// to a bare domain. Returns a normalised absolute URL or "".
  function safeWebUrl(input) {
    var s = clean(input);
    if (!s || /\s/.test(s) || s.charAt(0) === "/") return "";
    if (/^[a-z][a-z0-9+.-]*:/i.test(s) && !/^https?:\/\//i.test(s)) return "";
    if (!/^https?:\/\//i.test(s)) s = "https://" + s;
    var u;
    try { u = new URL(s); } catch (e) { return ""; }
    if (u.protocol !== "https:" && u.protocol !== "http:") return "";
    if (!/^[^.\s]+(\.[^.\s]+)*\.[a-z][a-z0-9-]*$/i.test(u.hostname)) return "";
    if (u.username || u.password) return "";
    return u.href;
  }

  function urlLabel(url) {
    return url.replace(/^https?:\/\//i, "").replace(/^www\./i, "").replace(/\/+$/, "");
  }

  // Google Scholar profile link only.
  function parseScholar(input) {
    var s = clean(input);
    if (!s) return { ok: false, empty: true };
    var url = safeWebUrl(s);
    var host = "";
    try { host = new URL(url).hostname; } catch (e) { host = ""; }
    if (!url || !/^scholar\.google\.[a-z.]{2,}$/i.test(host)) {
      return { ok: false, error: "Use the link to your Google Scholar profile, like https://scholar.google.com/citations?user=..." };
    }
    return { ok: true, url: url };
  }

  function normalizeDoi(input) {
    var s = clean(input);
    if (!s) return "";
    s = s.replace(/^doi:\s*/i, "").replace(/^https?:\/\/(dx\.)?doi\.org\//i, "");
    try { s = decodeURIComponent(s); } catch (e) { /* keep as typed */ }
    if (!/^10\.\d{4,9}\/\S+$/.test(s)) return "";
    // Percent-encode anything that could break out of an attribute or a tag.
    var enc = s.replace(/[^A-Za-z0-9\-._~:\/?#@!$()*+,;=%\[\]]/g, function (c) {
      return encodeURIComponent(c);
    });
    return "https://doi.org/" + enc;
  }

  function parseEmail(input) {
    var s = clean(input);
    if (!s) return "";
    return /^[^\s@<>"'(),;:\\]+@[^\s@<>"'(),;:\\]+\.[^\s@<>"'(),;:\\]+$/.test(s) ? s : "";
  }

  function parsePhone(input) {
    var s = clean(input);
    if (!s) return { text: "", href: "" };
    var digits = s.replace(/[^\d+]/g, "");
    if (digits.replace(/\D/g, "").length < 5) return { text: s, href: "" };
    return { text: s, href: "tel:" + digits.replace(/(?!^)\+/g, "") };
  }

  var PRESETS = {
    phd: {
      label: "PhD student",
      title: "PhD Candidate",
      order: ["orcid", "scholar", "website"],
      hints: { title: "PhD Candidate", dept: "Department of Sociology", website: "Lab or personal site" }
    },
    postdoc: {
      label: "Postdoc",
      title: "Postdoctoral Researcher",
      order: ["website", "scholar", "orcid"],
      hints: { title: "Postdoctoral Researcher", dept: "Department of Sociology", website: "Lab or personal site" }
    },
    faculty: {
      label: "Faculty",
      title: "Associate Professor",
      order: ["website", "orcid", "scholar"],
      hints: { title: "Associate Professor", dept: "Department of Sociology", website: "Lab or personal site" }
    }
  };

  var ACCENTS = [
    { name: "Purple", value: "#5b2a86" },
    { name: "Blue", value: "#1f4e8c" },
    { name: "Teal", value: "#1b6b5a" },
    { name: "Burgundy", value: "#8a2d3b" },
    { name: "Graphite", value: "#3a3a3a" }
  ];

  function hexToRgb(hex) {
    var m = /^#([0-9a-f]{6})$/i.exec(hex || "");
    if (!m) return null;
    var n = parseInt(m[1], 16);
    return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
  }
  function luminance(rgb) {
    var c = rgb.map(function (v) {
      v /= 255;
      return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4);
    });
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2];
  }
  // WCAG contrast ratio of a hex colour on white.
  function contrastOnWhite(hex) {
    var rgb = hexToRgb(hex);
    if (!rgb) return 0;
    return 1.05 / (luminance(rgb) + 0.05);
  }
  function safeColor(hex, fallback) {
    return /^#[0-9a-f]{6}$/i.test(hex || "") ? hex.toLowerCase() : fallback;
  }

  function st(o) {
    var out = [];
    for (var k in o) if (Object.prototype.hasOwnProperty.call(o, k) && o[k] !== null && o[k] !== "") out.push(k + ":" + o[k]);
    return out.join(";") + ";";
  }

  // Turn raw form values into validated, display-ready pieces.
  function normalize(f) {
    f = f || {};
    var errors = {};
    var n = {
      name: clean(f.name),
      pronouns: clean(f.pronouns),
      title: clean(f.title),
      dept: clean(f.dept),
      institution: clean(f.institution),
      email: "",
      phone: parsePhone(f.phone),
      orcid: null,
      scholar: null,
      website: "",
      paperTitle: clean(f.paperTitle),
      paperDoi: "",
      paperUrl: "",
      office: clean(f.office),
      hoursNote: clean(f.hoursNote),
      custom: clean(f.custom)
    };
    if (clean(f.email)) {
      n.email = parseEmail(f.email);
      if (!n.email) errors.email = "That does not look like an email address.";
    }
    if (clean(f.orcid)) {
      n.orcid = parseOrcid(f.orcid);
      if (!n.orcid.ok) errors.orcid = n.orcid.error;
    }
    if (clean(f.scholar)) {
      n.scholar = parseScholar(f.scholar);
      if (!n.scholar.ok) errors.scholar = n.scholar.error;
    }
    if (clean(f.website)) {
      n.website = safeWebUrl(f.website);
      if (!n.website) errors.website = "Use a web address that starts with http or https, like https://example.edu/lab.";
    }
    if (clean(f.paperDoi)) {
      n.paperDoi = normalizeDoi(f.paperDoi);
      if (!n.paperDoi) {
        n.paperUrl = safeWebUrl(f.paperDoi);
        if (!n.paperUrl) errors.paperDoi = "Enter a DOI like 10.1000/xyz123, or a web address.";
      }
    }
    n.errors = errors;
    return n;
  }

  // Build the pieces once, then lay them out per template.
  // opts: template, accent, font ("sans"|"serif"), size (13|14), inheritColor, icon, preview, preset
  function build(fields, opts) {
    opts = opts || {};
    var n = normalize(fields);
    var accent = safeColor(opts.accent, "#5b2a86");
    var inherit = !!opts.inheritColor;
    var useIcon = !!opts.icon;
    var iconSrc = opts.preview && opts.origin ? opts.origin + "/assets/orcid-id-16.png" : ORCID_ICON_URL;
    var font = opts.font === "serif" ? SERIF : SANS;
    var size = opts.size === 13 ? 13 : 14;
    var small = size - 2;
    var template = ["minimal", "classic", "compact", "twocol"].indexOf(opts.template) >= 0 ? opts.template : "classic";
    var preset = PRESETS[opts.preset] || PRESETS.faculty;

    var main = inherit ? null : "#222222";
    var soft = inherit ? null : "#595959";

    var base = { "font-family": font, "font-size": size + "px", "line-height": "1.45", color: main, margin: "0", padding: "0" };
    var cell = function (extra) {
      var o = { "font-family": font, "font-size": size + "px", "line-height": "1.45", color: main, padding: "0" };
      for (var k in extra) o[k] = extra[k];
      return st(o);
    };
    var linkStyle = st({ color: accent, "text-decoration": "none" });

    function link(href, text) {
      return '<a href="' + esc(href) + '" style="' + linkStyle + '">' + esc(text) + "</a>";
    }

    // Pieces: html and plain text for each.
    var P = {};
    var nameHtml = '<span style="' + st({ "font-weight": "bold", "font-size": size + 2 + "px", color: template === "minimal" ? main : accent }) + '">' + esc(n.name) + "</span>";
    if (n.pronouns) nameHtml += ' <span style="' + st({ color: soft, "font-size": small + "px" }) + '">(' + esc(n.pronouns) + ")</span>";
    if (n.name) P.name = { html: nameHtml, text: n.name + (n.pronouns ? " (" + n.pronouns + ")" : "") };

    var roleParts = [n.title, n.dept].filter(Boolean);
    if (roleParts.length) P.role = { html: esc(roleParts.join(", ")), text: roleParts.join(", ") };
    if (n.institution) P.inst = { html: esc(n.institution), text: n.institution };

    if (n.email) P.email = { html: link("mailto:" + n.email, n.email), text: n.email };
    if (n.phone.text) {
      P.phone = { html: n.phone.href ? link(n.phone.href, n.phone.text) : esc(n.phone.text), text: n.phone.text };
    }

    if (n.orcid && n.orcid.ok) {
      var oh;
      if (useIcon) {
        oh = '<a href="' + esc(n.orcid.url) + '" style="' + linkStyle + '"><img src="' + esc(iconSrc) + '" width="16" height="16" alt="ORCID iD" style="' +
          st({ border: "0", width: "16px", height: "16px", "vertical-align": "middle", "margin-right": "4px" }) + '">' + esc(n.orcid.url) + "</a>";
      } else {
        oh = "ORCID iD: " + link(n.orcid.url, n.orcid.url);
      }
      P.orcid = { html: oh, text: "ORCID iD: " + n.orcid.url };
    }
    if (n.scholar && n.scholar.ok) P.scholar = { html: link(n.scholar.url, "Google Scholar"), text: "Google Scholar: " + n.scholar.url };
    if (n.website) P.website = { html: link(n.website, urlLabel(n.website)), text: urlLabel(n.website) };

    var paperLink = n.paperDoi || n.paperUrl;
    if (n.paperTitle || paperLink) {
      var ph = '<span style="' + st({ color: soft }) + '">Latest paper: </span>' + esc(n.paperTitle);
      var pt = "Latest paper: " + n.paperTitle;
      if (paperLink) {
        var lbl = urlLabel(paperLink);
        ph += (n.paperTitle ? " " : "") + link(paperLink, lbl);
        pt += (n.paperTitle ? " " : "") + paperLink;
      }
      P.paper = { html: ph, text: pt.trim() };
    }
    if (n.office) P.office = { html: '<span style="' + st({ color: soft }) + '">Office hours: </span>' + esc(n.office), text: "Office hours: " + n.office };
    if (n.hoursNote) P.hours = { html: '<span style="' + st({ color: soft, "font-size": small + "px", "font-style": "italic" }) + '">' + esc(n.hoursNote) + "</span>", text: n.hoursNote };
    if (n.custom) P.custom = { html: '<span style="' + st({ color: soft, "font-size": small + "px" }) + '">' + esc(n.custom) + "</span>", text: n.custom };

    var ids = preset.order.filter(function (k) { return P[k]; });
    var SEP = '<span style="' + st({ color: soft }) + '"> &middot; </span>';

    function tr(htmlInner, extra) {
      return '<tr><td style="' + cell(extra || { padding: "0 0 2px 0" }) + '">' + htmlInner + "</td></tr>";
    }
    function table(rows, extra) {
      return '<table cellpadding="0" cellspacing="0" border="0" style="' +
        st({ "border-collapse": "collapse", "font-family": font, "font-size": size + "px", color: main }) + (extra || "") + '">' + rows.join("") + "</table>";
    }

    var rows = [];
    var html;

    if (template === "compact") {
      var rest = [n.title, n.dept, n.institution].filter(Boolean).join(", ");
      var line1 = P.name ? P.name.html + (rest ? SEP.replace("&middot;", "|") + esc(rest) : "") : esc(rest);
      if (line1) rows.push(tr(line1));
      var l2 = [P.email, P.phone].concat(ids.map(function (k) { return P[k]; })).filter(Boolean).map(function (p) { return p.html; });
      if (l2.length) rows.push(tr(l2.join(SEP)));
      ["paper", "office", "hours", "custom"].forEach(function (k) {
        if (P[k]) rows.push(tr(P[k].html, { padding: "2px 0 0 0", "font-size": k === "hours" || k === "custom" ? small + "px" : size + "px" }));
      });
      html = table(rows);
    } else if (template === "twocol") {
      var left = [];
      if (P.name) left.push(tr(P.name.html));
      if (P.role) left.push(tr(P.role.html));
      if (P.inst) left.push(tr(P.inst.html));
      var right = [];
      [P.email, P.phone].concat(ids.map(function (k) { return P[k]; })).filter(Boolean).forEach(function (p) { right.push(tr(p.html)); });
      var cols = [];
      if (left.length) cols.push('<td valign="top" style="' + cell({ padding: "0 14px 0 0", "border-right": right.length ? "2px solid " + accent : null }) + '">' + table(left) + "</td>");
      if (right.length) cols.push('<td valign="top" style="' + cell({ padding: left.length ? "0 0 0 14px" : "0" }) + '">' + table(right) + "</td>");
      var tail = [];
      ["paper", "office", "hours", "custom"].forEach(function (k) {
        if (P[k]) tail.push(tr(P[k].html, { padding: "2px 0 0 0", "font-size": k === "hours" || k === "custom" ? small + "px" : size + "px" }));
      });
      var outer = [];
      if (cols.length) outer.push("<tr>" + cols.join("") + "</tr>");
      if (tail.length) outer.push('<tr><td colspan="' + Math.max(cols.length, 1) + '" style="' + cell({ padding: "8px 0 0 0" }) + '">' + table(tail) + "</td></tr>");
      html = outer.length ? table(outer) : "";
    } else {
      // minimal and classic share one stack of rows.
      if (P.name) rows.push(tr(P.name.html));
      if (P.role) rows.push(tr(P.role.html));
      if (P.inst) rows.push(tr(P.inst.html));
      var contact = [P.email, P.phone].filter(Boolean).map(function (p) { return p.html; });
      if (contact.length) rows.push(tr(contact.join(SEP), { padding: "6px 0 2px 0" }));
      var idHtml = ids.map(function (k) { return P[k].html; });
      if (idHtml.length) rows.push(tr(idHtml.join(SEP)));
      ["paper", "office", "hours", "custom"].forEach(function (k, i) {
        if (P[k]) rows.push(tr(P[k].html, { padding: (i === 0 || !rows.length ? "6px" : "2px") + " 0 2px 0", "font-size": k === "hours" || k === "custom" ? small + "px" : size + "px" }));
      });
      if (template === "classic" && rows.length) {
        html = '<table cellpadding="0" cellspacing="0" border="0" style="' + st({ "border-collapse": "collapse" }) + '"><tr><td style="' +
          cell({ "border-top": "2px solid " + accent, padding: "8px 0 0 0" }) + '">' + table(rows) + "</td></tr></table>";
      } else {
        html = rows.length ? table(rows) : "";
      }
    }

    // Plain text, in the same order for every template.
    var t = [];
    if (P.name) t.push(P.name.text);
    var roleInst = [n.title, n.dept, n.institution].filter(Boolean).join(", ");
    if (roleInst) t.push(roleInst);
    [P.email, P.phone].filter(Boolean).forEach(function (p) { t.push(p.text); });
    ids.forEach(function (k) { t.push(P[k].text); });
    ["paper", "office", "hours", "custom"].forEach(function (k) { if (P[k]) t.push(P[k].text); });
    var text = t.join("\n");
    // Leading "-- " separator, the plain-text signature convention.
    if (text) text = "-- \n" + text;

    return { html: html, text: text, errors: n.errors, empty: !html, normalized: n, base: st(base) };
  }

  // A full document for the preview frame (never copied).
  function previewDocument(fragment, dark) {
    var bg = dark ? "#1b1b1f" : "#ffffff";
    var fg = dark ? "#e8e6ea" : "#222222";
    return "<!doctype html><html><head><meta charset=\"utf-8\"><meta name=\"color-scheme\" content=\"" + (dark ? "dark" : "light") + "\">" +
      "<style>html,body{margin:0;background:" + bg + ";color:" + fg + ";}body{padding:14px 16px;}</style></head><body>" + fragment + "</body></html>";
  }

  var api = {
    esc: esc, clean: clean, parseOrcid: parseOrcid, orcidCheckChar: orcidCheckChar, safeWebUrl: safeWebUrl,
    parseScholar: parseScholar, normalizeDoi: normalizeDoi, parseEmail: parseEmail, parsePhone: parsePhone,
    contrastOnWhite: contrastOnWhite, safeColor: safeColor, normalize: normalize, build: build,
    previewDocument: previewDocument, PRESETS: PRESETS, ACCENTS: ACCENTS, ORCID_ICON_URL: ORCID_ICON_URL
  };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.SignatureCore = api;
})(typeof window !== "undefined" ? window : this);
