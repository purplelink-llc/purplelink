/* Free Mac wallpaper page: the optional "tell me about the larger pack" form posts to Netlify Forms without leaving
   the page (same pattern as the other waitlists). Without JavaScript the form still posts and returns here. */
(function () {
  'use strict';
  var form = document.getElementById('wp-form');
  if (!form) return;
  form.addEventListener('submit', function (e) {
    e.preventDefault();
    var btn = document.getElementById('wp-submit');
    var status = document.getElementById('wp-status');
    btn.disabled = true;
    fetch('/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: new URLSearchParams(new FormData(form)).toString()
    }).then(function (r) {
      if (!r.ok) throw new Error('bad status');
      form.classList.add('is-done');
      status.hidden = false;
      status.setAttribute('tabindex', '-1');
      status.focus();
    }).catch(function () {
      btn.disabled = false;
      status.textContent = 'That did not go through. Please try again in a moment.';
      status.hidden = false;
    });
  });
})();
