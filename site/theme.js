/* Theme: dark is the default. A visitor can opt into light from the footer;
   the choice is remembered. Loaded in <head> without defer so a saved light
   choice is applied before first paint (dark needs no attribute, so the
   default never flashes). Storage can throw in private windows: every access
   is wrapped and the page works without it. */
(() => {
  'use strict';
  const KEY = 'pl-theme';
  const root = document.documentElement;
  const read = () => { try { return localStorage.getItem(KEY); } catch (e) { return null; } };
  const write = (v) => { try { localStorage.setItem(KEY, v); } catch (e) { /* ignore */ } };
  // Browser chrome follows the page: the meta tag ships dark (the default) and is switched with the theme.
  const chrome = { dark: '#19141d', light: '#fbf9fe' };
  let fadeTimer = 0;
  const apply = (t) => {
    if (t === 'light') root.setAttribute('data-theme', 'light');
    else root.removeAttribute('data-theme');
    const meta = document.querySelector('meta[name="theme-color"]');
    if (meta) meta.setAttribute('content', t === 'light' ? chrome.light : chrome.dark);
  };
  apply(read());

  const sync = (btn) => {
    const light = root.getAttribute('data-theme') === 'light';
    btn.textContent = light ? 'Use dark theme' : 'Use light theme';
  };
  document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('[data-theme-toggle]').forEach((btn) => {
      btn.hidden = false;
      sync(btn);
      btn.addEventListener('click', () => {
        const next = root.getAttribute('data-theme') === 'light' ? 'dark' : 'light';
        write(next);
        // Cross-fade colours for a moment so the page does not jump from near-black to near-white in one frame
        // (styles.css .theme-fade). Only on a click, never on load, so a saved choice still paints first time.
        root.classList.add('theme-fade');
        clearTimeout(fadeTimer);
        fadeTimer = setTimeout(() => root.classList.remove('theme-fade'), 320);
        apply(next);
        document.querySelectorAll('[data-theme-toggle]').forEach(sync);
      });
    });
  });
})();

/* Black Friday 2026 bar (code BLACKFRIDAY26, experiment black-friday-promo-2026). Decided here, in the blocking
   <head> script, so styles.css can reserve the bar's height before first paint and the page never shifts when it
   fills in. English pages only, never on receipt or account pages, gone for good once dismissed, and it switches
   itself off at 2026-12-01 00:00 US Eastern (05:00 UTC), the same moment the Stripe code expires. Delete after then. */
(() => {
  'use strict';
  const END = Date.UTC(2026, 11, 1, 5, 0, 0);
  const KEY = 'pl-bf26-hidden';
  const root = document.documentElement;
  const path = location.pathname;
  if (Date.now() >= END) return;
  if (!/^en\b/i.test(root.lang || '')) return;
  if (/\/(success|recover|manage|upload|packs|setup|not-now|uninstalled)\//.test(path) || path.startsWith('/stats/')) return;
  try { if (localStorage.getItem(KEY) === '1') return; } catch (e) { /* storage blocked: show it */ }
  root.classList.add('pl-bf26');

  const close = (bar) => {
    bar.remove();
    root.classList.remove('pl-bf26');
    try { localStorage.setItem(KEY, '1'); } catch (e) { /* ignore */ }
  };
  const place = () => {
    if (!document.body || document.querySelector('.bf26-bar')) return;
    // A page without styles.css would show the bar unstyled: skip it (and drop the reserved space with it).
    if (!document.querySelector('link[rel="stylesheet"][href*="styles.css"]')) { root.classList.remove('pl-bf26'); return; }
    const bar = document.createElement('aside');
    bar.className = 'bf26-bar';
    bar.setAttribute('aria-label', 'Black Friday offer');
    const text = document.createElement('p');
    text.className = 'bf26-text';
    text.appendChild(document.createTextNode('Black Friday: '));
    const link = document.createElement('a');
    link.href = '/products/';
    link.textContent = 'any Mac app';
    text.appendChild(link);
    text.appendChild(document.createTextNode(' is 20% off with code '));
    const code = document.createElement('strong');
    code.className = 'bf26-code';
    code.textContent = 'BLACKFRIDAY26';
    text.appendChild(code);
    text.appendChild(document.createTextNode(', through November 30.'));
    const hide = document.createElement('button');
    hide.type = 'button';
    hide.className = 'bf26-hide';
    hide.setAttribute('aria-label', 'Hide the Black Friday offer');
    hide.textContent = 'Hide';
    hide.addEventListener('click', () => {
      // Keep keyboard users on the page instead of dropping focus to <body>.
      const next = document.querySelector('.skip-link') || document.querySelector('.topbar a[href], header a[href], a[href]');
      close(bar);
      if (next && typeof next.focus === 'function') next.focus({ preventScroll: true });
    });
    bar.addEventListener('keydown', (e) => { if (e.key === 'Escape') hide.click(); });
    bar.appendChild(text);
    bar.appendChild(hide);
    document.body.insertBefore(bar, document.body.firstChild);
    try { window.plTrack && window.plTrack('promo_view', 'bf26'); } catch (e) { /* ignore */ }
    link.addEventListener('click', () => { try { window.plTrack && window.plTrack('promo_click', 'bf26'); } catch (e) { /* ignore */ } });
  };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', place); else place();
})();
