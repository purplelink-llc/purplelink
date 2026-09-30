/* Budgetcast demo page: waitlist submit and the sample forecast chart. */
(function () {
  'use strict';

  // ---- Waitlist form (Netlify Forms, same pattern as the other waitlists) ----
  var form = document.getElementById('bc-form');
  if (form) {
    form.addEventListener('submit', function (e) {
      e.preventDefault();
      var btn = form.querySelector('.bc-submit');
      var status = document.getElementById('bc-status');
      btn.disabled = true;
      var body = new URLSearchParams(new FormData(form)).toString();
      fetch('/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: body
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
  }

  // ---- Sample forecast chart ----
  var host = document.getElementById('bc-chart');
  var sel = document.getElementById('bc-category');
  var table = document.getElementById('bc-table');
  var sum = document.getElementById('bc-chart-sum');
  if (!host || !sel) return;

  var NS = 'http://www.w3.org/2000/svg';
  var MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  var HIST_SHOWN = 12;
  var data;

  function money(n) { return '$' + Math.round(n).toLocaleString('en-US'); }
  function label(ym) { var p = ym.split('-'); return MONTHS[+p[1] - 1] + ' ' + p[0]; }
  function addMonths(ym, k) {
    var p = ym.split('-'); var t = (+p[0]) * 12 + (+p[1] - 1) + k;
    return Math.floor(t / 12) + '-' + ('0' + ((t % 12) + 1)).slice(-2);
  }
  function el(name, attrs, text) {
    var n = document.createElementNS(NS, name);
    for (var k in attrs) n.setAttribute(k, attrs[k]);
    if (text != null) n.textContent = text;
    return n;
  }

  function draw(cat) {
    var hist = data.history[cat].slice(-HIST_SHOWN);
    var fc = data.forecast[cat];
    var n = data.history[cat].length;
    var lastHist = addMonths(data.start, n - 1);
    var histMonths = hist.map(function (_, i) { return addMonths(lastHist, i - hist.length + 1); });
    var all = hist.concat(fc.map(function (r) { return r.p90; }), fc.map(function (r) { return r.p10; }));
    var lo = Math.min.apply(null, all), hi = Math.max.apply(null, all);
    var pad = Math.max((hi - lo) * 0.12, 20);
    lo = Math.max(0, Math.floor((lo - pad) / 50) * 50); hi = Math.ceil((hi + pad) / 50) * 50;

    var W = 640, H = 300, L = 52, R = 14, T = 12, B = 34;
    var total = hist.length + fc.length;
    var x = function (i) { return L + (i * (W - L - R)) / (total - 1); };
    var y = function (v) { return T + (H - T - B) * (1 - (v - lo) / (hi - lo)); };

    var svg = el('svg', { viewBox: '0 0 ' + W + ' ' + H, role: 'img', 'aria-labelledby': 'bc-svg-t bc-svg-d' });
    svg.appendChild(el('title', { id: 'bc-svg-t' }, cat + ', sample household, next 3 months'));
    var f0 = fc[0], f2 = fc[fc.length - 1];
    svg.appendChild(el('desc', { id: 'bc-svg-d' },
      'Synthetic data. Middle estimate ' + money(f0.p50) + ' in ' + label(f0.month) + ' and ' + money(f2.p50) +
      ' in ' + label(f2.month) + '. P10 to P90 range in ' + label(f2.month) + ': ' + money(f2.p10) + ' to ' + money(f2.p90) + '. Full table below.'));

    var step = (hi - lo) / 4;
    for (var g = 0; g <= 4; g++) {
      var gv = lo + step * g;
      svg.appendChild(el('line', { class: g === 0 ? 'axis' : 'grid', x1: L, x2: W - R, y1: y(gv), y2: y(gv) }));
      svg.appendChild(el('text', { x: L - 8, y: y(gv) + 4, 'text-anchor': 'end' }, money(gv)));
    }
    var labelEvery = 3;
    for (var i = 0; i < total; i++) {
      var m = i < hist.length ? histMonths[i] : fc[i - hist.length].month;
      if (i % labelEvery === (total - 1) % labelEvery || i === total - 1) {
        svg.appendChild(el('text', { x: x(i), y: H - 8, 'text-anchor': i === total - 1 ? 'end' : 'middle' }, label(m).replace(' 20', ' \u2019')));
      }
    }

    // history line
    var hp = hist.map(function (v, i) { return (i ? 'L' : 'M') + x(i).toFixed(1) + ' ' + y(v).toFixed(1); }).join(' ');
    svg.appendChild(el('path', { class: 'hist', d: hp }));

    // band, anchored at the last observed month so it opens from the line
    var s = hist.length - 1;
    var top = 'M' + x(s).toFixed(1) + ' ' + y(hist[s]).toFixed(1);
    var bot = '';
    fc.forEach(function (r, k) { top += ' L' + x(s + 1 + k).toFixed(1) + ' ' + y(r.p90).toFixed(1); });
    for (var k = fc.length - 1; k >= 0; k--) bot += ' L' + x(s + 1 + k).toFixed(1) + ' ' + y(fc[k].p10).toFixed(1);
    svg.appendChild(el('path', { class: 'band', d: top + bot + ' Z' }));

    var mid = 'M' + x(s).toFixed(1) + ' ' + y(hist[s]).toFixed(1);
    fc.forEach(function (r, k) { mid += ' L' + x(s + 1 + k).toFixed(1) + ' ' + y(r.p50).toFixed(1); });
    svg.appendChild(el('path', { class: 'mid', d: mid }));
    fc.forEach(function (r, k) { svg.appendChild(el('circle', { class: 'dot', cx: x(s + 1 + k), cy: y(r.p50), r: 3.5 })); });

    host.replaceChildren(svg);

    sum.textContent = 'Sample household, synthetic data. For ' + cat.toLowerCase() + ', the middle estimate for ' +
      label(f2.month) + ' is ' + money(f2.p50) + ', with a P10 to P90 range of ' + money(f2.p10) + ' to ' + money(f2.p90) + '.';

    var rows = '<caption class="bc-vh">' + cat + ': sample past months and projected P10, P50, P90. Synthetic data.</caption>' +
      '<thead><tr><th scope="col">Month</th><th scope="col">Type</th><th scope="col">P10</th><th scope="col">P50</th><th scope="col">P90</th></tr></thead><tbody>';
    hist.forEach(function (v, i) {
      rows += '<tr><th scope="row">' + label(histMonths[i]) + '</th><td>Sample actual</td><td>&ndash;</td><td>' + money(v) + '</td><td>&ndash;</td></tr>';
    });
    fc.forEach(function (r) {
      rows += '<tr><th scope="row">' + label(r.month) + '</th><td>Projection</td><td>' + money(r.p10) + '</td><td>' + money(r.p50) + '</td><td>' + money(r.p90) + '</td></tr>';
    });
    table.innerHTML = rows + '</tbody>';
  }

  fetch('/budgetcast/demo.json').then(function (r) { return r.json(); }).then(function (d) {
    data = d;
    Object.keys(d.forecast).forEach(function (c) {
      var o = document.createElement('option'); o.value = c; o.textContent = c; sel.appendChild(o);
    });
    sel.value = 'Dining out';
    sel.addEventListener('change', function () { draw(sel.value); });
    draw(sel.value);
  }).catch(function () {
    sum.textContent = 'The sample forecast could not be loaded.';
  });
})();
