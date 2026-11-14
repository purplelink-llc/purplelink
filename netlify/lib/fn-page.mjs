/**
 * Shared HTML shell for pages that a Netlify function renders (unsubscribe, billing links,
 * signup confirmation). Uses the site's own stylesheet and fonts, so no inline styles.
 */

export function escapeHtml(v) {
  return String(v).replace(/[&<>"'`]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;", "`": "&#96;" }[c]))
}

/**
 * Extra same-origin stylesheets for a page: `options.styles` is a list of paths like "/labs/plan.css". Anything that is
 * not a plain site path (an absolute URL, a protocol-relative one, a quote or angle bracket) is dropped, so the CSP
 * (style-src 'self') is never asked for another origin.
 */
function extraStyles(styles) {
  if (!Array.isArray(styles)) return ""
  return styles
    .filter((h) => typeof h === "string" && /^\/[A-Za-z0-9._\/-]*\.css$/.test(h) && !h.startsWith("//"))
    .map((h) => `\n    <link rel="stylesheet" href="${h}">`)
    .join("")
}

export function page(title, heading, bodyHtml, status = 200, options = {}) {
  return new Response(`<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>${title} | Purplelink LLC</title>
    <link rel="icon" href="/assets/purplelink-logo.png" type="image/png">
    <meta name="theme-color" content="#19141d">
    <link rel="preload" href="/assets/fonts/fraunces-latin.woff2" as="font" type="font/woff2" crossorigin>
    <link rel="preload" href="/assets/fonts/plus-jakarta-sans-latin.woff2" as="font" type="font/woff2" crossorigin>
    <link rel="stylesheet" href="/styles.css">${extraStyles(options?.styles)}
    <script src="/site.js" defer></script>
  </head>
  <body>
    <a class="skip-link" href="#main-content">Skip to content</a>
    <header class="topbar">
      <a class="brand" href="/" aria-label="Purplelink home">
        <img src="/assets/purplelink-mark.svg" alt="" width="30" height="30">
        <span>Purplelink</span>
      </a>
      <nav aria-label="Primary navigation">
        <a href="/#software">Software</a>
        <a href="/#projects">Products</a>
        <a href="/tools/">Tools</a>
        <a href="/changelog/">Changelog</a>
        <a href="/about/">About</a>
        <a href="/#contact">Contact</a>
      </nav>
    </header>
    <div id="main-content" class="post-hero">
      <h1>${heading}</h1>
      ${bodyHtml}
    </div>
    <footer class="footer">
      <div class="footer-top">
        <div class="footer-brand">
          <img src="/assets/purplelink-mark.svg" alt="" width="26" height="26">
          <span>Purplelink LLC</span>
        </div>
        <span class="footer-loc">Atlanta, Georgia · Est. 2026</span>
      </div>
      <nav class="footer-links" aria-label="Footer navigation">
        <a href="/about/">About</a>
        <a href="/press/">Press</a>
        <a href="/privacy/">Privacy</a>
        <a href="/terms/">Terms</a>
        <a href="/blog/">Blog</a>
        <a href="/guides/">Guides</a>
        <a href="/changelog/">Changelog</a>
      </nav>
    </footer>
  </body>
</html>`, {
    status,
    headers: {
      "Content-Type": "text/html; charset=utf-8",
      "Cache-Control": "no-store",
      "Referrer-Policy": "no-referrer",
      "X-Robots-Tag": "noindex",
    },
  })
}
