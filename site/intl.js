/* Localized pages (/de/, /fr/, /ja/, /zh-cn/).
   1. The theme toggle: theme.js sets an English label on load and on every click. Its handlers run first, so
      this script rewrites the label afterwards, from data-label-light / data-label-dark on the button.
   2. Copy buttons on code blocks in the guides, in the page's language (site.js does the same job in English
      and is not loaded on these guides). */
(() => {
  'use strict';
  const root = document.documentElement;
  const label = (btn) => {
    const light = root.getAttribute('data-theme') === 'light';
    const text = light ? btn.getAttribute('data-label-dark') : btn.getAttribute('data-label-light');
    if (text) btn.textContent = text;
  };
  document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('[data-theme-toggle][data-label-light]').forEach((btn) => {
      label(btn);
      btn.addEventListener('click', () => label(btn));
    });
  });

  const TEXT = {
    de: { copy: 'Kopieren', copied: 'Kopiert', live: 'In die Zwischenablage kopiert', fail: 'Markieren und kopieren', failLive: 'Kopieren nicht möglich. Markieren Sie den Code und kopieren Sie ihn.' },
    fr: { copy: 'Copier', copied: 'Copié', live: 'Copié dans le presse-papiers', fail: 'Sélectionner et copier', failLive: 'Copie impossible. Sélectionnez le code et copiez-le.' },
    ja: { copy: 'コピー', copied: 'コピーしました', live: 'クリップボードにコピーしました', fail: '選択してコピー', failLive: 'コピーできませんでした。コードを選択してコピーしてください。' },
    'zh-Hans': { copy: '复制', copied: '已复制', live: '已复制到剪贴板', fail: '请选中后复制', failLive: '无法复制。请选中代码后手动复制。' },
  };
  const t = TEXT[root.getAttribute('lang')];
  if (!t || !navigator.clipboard) return;
  document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('.post-body pre').forEach((pre) => {
      if ((pre.textContent.match(/\n/g) || []).length < 3) return;
      const text = pre.innerText;
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'code-copy';
      btn.textContent = t.copy;
      const live = document.createElement('span');
      live.className = 'visually-hidden';
      live.setAttribute('role', 'status');
      btn.addEventListener('click', () => {
        navigator.clipboard.writeText(text).then(() => {
          btn.textContent = t.copied;
          live.textContent = t.live;
          setTimeout(() => { btn.textContent = t.copy; live.textContent = ''; }, 1600);
        }, () => { btn.textContent = t.fail; live.textContent = t.failLive; });
      });
      pre.classList.add('has-copy');
      pre.appendChild(btn);
      pre.appendChild(live);
    });
  });
})();
