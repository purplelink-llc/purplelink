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
    btn.setAttribute('aria-pressed', light ? 'true' : 'false');
  };
  document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('[data-theme-toggle]').forEach((btn) => {
      btn.hidden = false;
      sync(btn);
      btn.addEventListener('click', () => {
        const next = root.getAttribute('data-theme') === 'light' ? 'dark' : 'light';
        write(next);
        apply(next);
        document.querySelectorAll('[data-theme-toggle]').forEach(sync);
      });
    });
  });
})();
