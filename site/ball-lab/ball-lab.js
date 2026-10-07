/* Ball Lab: a free ball-physics toy. Two modes, both drawn on one canvas, no libraries, no assets, no network.
   Sandbox:     tap to drop balls; flip gravity, hold the magnet, shake, explode. Collisions play notes.
   Polyrhythm:  nine balls bounce at slightly different rates and all land together every 40 seconds.
   Sound starts on the first tap (browsers require a gesture). Everything is deterministic enough to test: see window.BallLab. */
(function () {
  "use strict";

  var canvas = document.getElementById("bl-canvas");
  if (!canvas) return;
  var ctx = canvas.getContext("2d");
  var COLORS = ["#ff4d6d", "#ff8a3d", "#ffd23f", "#7ee081", "#4dd0e1", "#6c8cff", "#b57bff", "#ff7bd0"];
  var SCALE = [0, 2, 4, 7, 9, 12, 14, 16, 19, 21];          // major pentatonic, in semitones above C4
  var MAX_BALLS = 140, REST = 0.9, G_FACTOR = 1.25;         // gravity is G_FACTOR * canvas heights per second squared
  var POLY_N = 9, POLY_PERIOD = 40;                         // polyrhythm: ball i makes (20 + i) bounces per 40 s, so all land together

  var W = 0, H = 0, DPR = 1;
  var mode = "sandbox", gravSign = 1, magnet = false, paused = false, speed = 1;
  var balls = [], pointer = { x: 0, y: 0, down: false, inside: false };
  var sprites = {}, audio = null, muted = false, voices = 0, lastNoteAt = 0, notesThisWindow = 0;
  var polyT = 0, flash = 0, hits = 0;

  /* ---------- sprites: a soft glow and a bright core per colour, drawn once ---------- */
  function sprite(color) {
    if (sprites[color]) return sprites[color];
    var s = document.createElement("canvas"); s.width = s.height = 96;
    var g = s.getContext("2d"), grad = g.createRadialGradient(48, 48, 2, 48, 48, 48);
    grad.addColorStop(0, color + "cc"); grad.addColorStop(0.3, color + "55"); grad.addColorStop(1, color + "00");
    g.fillStyle = grad; g.fillRect(0, 0, 96, 96);
    sprites[color] = s; return s;
  }

  /* ---------- sound ---------- */
  function ensureAudio() {
    if (audio || muted) return;
    var AC = window.AudioContext || window.webkitAudioContext;
    if (!AC) return;
    try { audio = new AC(); } catch (e) { audio = null; }
  }
  function note(idx, vol, octave) {
    if (!audio || muted || audio.state === "closed") return;
    var now = audio.currentTime;
    if (now - lastNoteAt > 0.1) { lastNoteAt = now; notesThisWindow = 0; }
    if (voices >= 20 || ++notesThisWindow > 9) return;       // stay musical, not a wall of noise
    var f = 261.63 * Math.pow(2, (SCALE[idx % SCALE.length] + 12 * (octave || 0)) / 12);
    var o = audio.createOscillator(), g = audio.createGain();
    o.type = "triangle"; o.frequency.value = f;
    g.gain.setValueAtTime(0.0001, now);
    g.gain.exponentialRampToValueAtTime(Math.max(0.02, Math.min(0.28, vol)), now + 0.008);
    g.gain.exponentialRampToValueAtTime(0.0001, now + 0.55);
    o.connect(g); g.connect(audio.destination); o.start(now); o.stop(now + 0.6);
    voices++; o.onended = function () { voices--; };
  }

  /* ---------- layout ---------- */
  function resize() {
    var box = canvas.parentElement, w = Math.min(box.clientWidth, 640);
    var h = Math.round(Math.min(Math.max(window.innerHeight * 0.66, 360), 760));
    DPR = Math.min(window.devicePixelRatio || 1, 2);
    W = w; H = h;
    canvas.style.width = w + "px"; canvas.style.height = h + "px";
    canvas.width = Math.round(w * DPR); canvas.height = Math.round(h * DPR);
    ctx.setTransform(DPR, 0, 0, DPR, 0, 0);
    ctx.fillStyle = "#07060c"; ctx.fillRect(0, 0, W, H);
    for (var i = 0; i < balls.length; i++) {                  // keep everything inside after a rotate / resize
      balls[i].x = Math.min(Math.max(balls[i].x, balls[i].r), W - balls[i].r);
      balls[i].y = Math.min(Math.max(balls[i].y, balls[i].r), H - balls[i].r);
    }
  }

  /* ---------- sandbox ---------- */
  function addBall(x, y, vx, vy) {
    if (balls.length >= MAX_BALLS) balls.shift();
    var i = Math.floor(Math.random() * COLORS.length);
    var r = 7 + Math.random() * 9;
    balls.push({ x: x, y: y, vx: vx === undefined ? (Math.random() - 0.5) * 420 : vx, vy: vy === undefined ? (Math.random() - 0.5) * 420 : vy,
                 r: r, color: COLORS[i], n: Math.floor(Math.random() * SCALE.length), oct: r > 13 ? -1 : 0 });
  }
  function burst(n, x, y) { for (var i = 0; i < n; i++) addBall(x, y); }

  function stepSandbox(dt) {
    var g = G_FACTOR * H * gravSign, i, j, b;
    for (i = 0; i < balls.length; i++) {
      b = balls[i];
      b.vy += g * dt;
      if (magnet && pointer.inside) {
        var dx = pointer.x - b.x, dy = pointer.y - b.y, d2 = dx * dx + dy * dy + 900, f = 9e5 / d2;
        b.vx += (dx / Math.sqrt(d2)) * f * dt; b.vy += (dy / Math.sqrt(d2)) * f * dt;
        b.vx *= 0.998; b.vy *= 0.998;
      }
      b.x += b.vx * dt; b.y += b.vy * dt;
      if (b.x < b.r) { b.x = b.r; if (-b.vx > 160) note(b.n, -b.vx / 2600, b.oct); b.vx = -b.vx * REST; }
      else if (b.x > W - b.r) { b.x = W - b.r; if (b.vx > 160) note(b.n, b.vx / 2600, b.oct); b.vx = -b.vx * REST; }
      if (b.y < b.r) { b.y = b.r; if (-b.vy > 160) note(b.n, -b.vy / 2600, b.oct); b.vy = -b.vy * REST; }
      else if (b.y > H - b.r) { b.y = H - b.r; if (b.vy > 160) note(b.n, b.vy / 2600, b.oct); b.vy = -b.vy * REST; }
    }
    // collisions on a uniform grid, so 140 balls stay cheap
    var cell = 36, grid = {}, key;
    for (i = 0; i < balls.length; i++) { key = Math.floor(balls[i].x / cell) + "," + Math.floor(balls[i].y / cell); (grid[key] = grid[key] || []).push(i); }
    for (i = 0; i < balls.length; i++) {
      var a = balls[i], cx = Math.floor(a.x / cell), cy = Math.floor(a.y / cell);
      for (var gx = cx - 1; gx <= cx + 1; gx++) for (var gy = cy - 1; gy <= cy + 1; gy++) {
        var list = grid[gx + "," + gy]; if (!list) continue;
        for (var k = 0; k < list.length; k++) {
          j = list[k]; if (j <= i) continue;
          b = balls[j];
          var nx = b.x - a.x, ny = b.y - a.y, dist2 = nx * nx + ny * ny, min = a.r + b.r;
          if (dist2 >= min * min || dist2 === 0) continue;
          var dist = Math.sqrt(dist2); nx /= dist; ny /= dist;
          var overlap = (min - dist) / 2; a.x -= nx * overlap; a.y -= ny * overlap; b.x += nx * overlap; b.y += ny * overlap;
          var ma = a.r * a.r, mb = b.r * b.r, rv = (b.vx - a.vx) * nx + (b.vy - a.vy) * ny;
          if (rv > 0) continue;
          var imp = -(1 + REST) * rv / (1 / ma + 1 / mb);
          a.vx -= imp * nx / ma; a.vy -= imp * ny / ma; b.vx += imp * nx / mb; b.vy += imp * ny / mb;
          if (-rv > 120) { note((a.r > b.r ? a : b).n, -rv / 1800, (a.r > b.r ? a : b).oct); hits++; }
        }
      }
    }
  }

  function drawSandbox() {
    ctx.globalCompositeOperation = "source-over";
    ctx.fillStyle = "rgba(7,6,12,0.30)"; ctx.fillRect(0, 0, W, H);        // the translucent fill is what leaves the trails
    ctx.globalCompositeOperation = "lighter";
    for (var i = 0; i < balls.length; i++) {
      var b = balls[i], s = b.r * 2.3;
      ctx.drawImage(sprite(b.color), b.x - s, b.y - s, s * 2, s * 2);
    }
    ctx.globalCompositeOperation = "source-over";
    for (i = 0; i < balls.length; i++) {
      b = balls[i]; ctx.beginPath(); ctx.arc(b.x, b.y, b.r * 0.55, 0, 6.2832); ctx.fillStyle = b.color; ctx.fill(); ctx.beginPath(); ctx.arc(b.x - b.r * 0.15, b.y - b.r * 0.15, b.r * 0.22, 0, 6.2832); ctx.fillStyle = "#ffffffcc"; ctx.fill();
    }
  }

  /* ---------- polyrhythm ---------- */
  function polyState(t) {
    var out = [], floor = H - 70, amp = H * 0.62, left = 36, step = (W - 72) / (POLY_N - 1);
    for (var i = 0; i < POLY_N; i++) {
      var count = 20 + i, phase = (t * count / POLY_PERIOD), frac = phase - Math.floor(phase);
      var y = floor - amp * (1 - Math.pow(2 * frac - 1, 2));              // a parabola: up, then down to the floor
      out.push({ i: i, x: left + i * step, y: y, bounce: Math.floor(phase), color: COLORS[i % COLORS.length] });
    }
    return out;
  }
  var lastBounce = [];
  function stepPoly(dt) {
    var prev = polyT; polyT += dt * speed;
    var st = polyState(polyT), i;
    for (i = 0; i < st.length; i++) {
      if (lastBounce[i] === undefined) lastBounce[i] = st[i].bounce;
      if (st[i].bounce !== lastBounce[i]) { lastBounce[i] = st[i].bounce; note(i, 0.2, 0); hits++; }
    }
    if (Math.floor(prev / POLY_PERIOD) !== Math.floor(polyT / POLY_PERIOD)) { flash = 1; for (i = 0; i < POLY_N; i += 2) note(i, 0.16, 1); }
    flash = Math.max(0, flash - dt * 1.6);
  }
  function drawPoly() {
    var st = polyState(polyT), floor = H - 70, i;
    ctx.globalCompositeOperation = "source-over";
    ctx.fillStyle = "rgba(7,6,12," + (0.36 - 0.2 * flash) + ")"; ctx.fillRect(0, 0, W, H);
    ctx.fillStyle = "#c9b8ff22"; ctx.fillRect(18, floor + 18, W - 36, 3);
    ctx.globalCompositeOperation = "lighter";
    for (i = 0; i < st.length; i++) {
      var p = st[i], s = 26;
      ctx.drawImage(sprite(p.color), p.x - s, p.y - s, s * 2, s * 2);
      if (p.y > floor - 14) { ctx.fillStyle = p.color + "88"; ctx.fillRect(p.x - 16, floor + 18, 32, 3); }
    }
    ctx.globalCompositeOperation = "source-over";
    for (i = 0; i < st.length; i++) { ctx.beginPath(); ctx.arc(st[i].x, st[i].y, 8, 0, 6.2832); ctx.fillStyle = st[i].color; ctx.fill(); ctx.beginPath(); ctx.arc(st[i].x - 2, st[i].y - 2, 3, 0, 6.2832); ctx.fillStyle = "#ffffffcc"; ctx.fill(); }
    var left = POLY_PERIOD - (polyT % POLY_PERIOD);
    ctx.fillStyle = "#ffd23f"; ctx.font = "700 20px ui-sans-serif, system-ui, sans-serif"; ctx.textAlign = "center";
    ctx.fillText("REALIGN IN " + left.toFixed(1) + "s", W / 2, 38);
    ctx.fillStyle = "#c9b8ffcc"; ctx.font = "600 14px ui-sans-serif, system-ui, sans-serif";
    ctx.fillText(POLY_N + " balls · " + POLY_N + " beats · one moment", W / 2, 60);
  }

  /* ---------- loop ---------- */
  var last = 0, acc = 0;
  function frame(ts) {
    requestAnimationFrame(frame);
    if (!last) last = ts;
    var dt = Math.min(0.05, (ts - last) / 1000); last = ts;
    if (!paused) {
      if (mode === "sandbox") { acc += dt * speed; while (acc >= 1 / 120) { stepSandbox(1 / 120); acc -= 1 / 120; } }
      else stepPoly(dt);
    }
    if (mode === "sandbox") drawSandbox(); else drawPoly();
    var hint = document.getElementById("bl-hint");
    if (hint && hits > 8) hint.style.opacity = "0";
  }

  /* ---------- controls ---------- */
  function setMode(m) {
    mode = m; ctx.fillStyle = "#07060c"; ctx.fillRect(0, 0, W, H);
    document.querySelectorAll("[data-mode]").forEach(function (b) { b.setAttribute("aria-pressed", b.getAttribute("data-mode") === m ? "true" : "false"); });
    document.querySelectorAll("[data-for]").forEach(function (g) { g.hidden = g.getAttribute("data-for") !== m; });
    if (m === "sandbox" && balls.length === 0) burst(36, W / 2, H * 0.3);
    if (m === "poly") { polyT = 0; lastBounce = []; }
  }
  function act(name) {
    ensureAudio(); if (audio && audio.state === "suspended") audio.resume();
    if (name === "add") burst(12, W / 2, H * 0.25);
    else if (name === "flip") { gravSign = -gravSign; }
    else if (name === "magnet") { magnet = !magnet; }
    else if (name === "shake") { balls.forEach(function (b) { b.vx += (Math.random() - 0.5) * 1400; b.vy += (Math.random() - 0.5) * 1400; }); }
    else if (name === "boom") { balls.forEach(function (b) { var dx = b.x - W / 2, dy = b.y - H / 2, d = Math.sqrt(dx * dx + dy * dy) + 30; b.vx += dx / d * 1300; b.vy += dy / d * 1300; }); }
    else if (name === "clear") { balls.length = 0; }
    else if (name === "slow") { speed = speed === 1 ? 0.35 : 1; }
    else if (name === "fast") { speed = speed === 2 ? 1 : 2; }
    else if (name === "pause") { paused = !paused; }
    else if (name === "sound") { muted = !muted; if (!muted) { ensureAudio(); } }
    else if (name === "share") { share(); }
    var map = { flip: gravSign < 0, magnet: magnet, slow: speed < 1, fast: speed > 1, pause: paused, sound: !muted };
    document.querySelectorAll('[data-act]').forEach(function (b) {
      var n = b.getAttribute("data-act"); if (n in map) b.setAttribute("aria-pressed", map[n] ? "true" : "false");
    });
  }
  function share() {
    var url = location.origin + location.pathname, data = { title: "Ball Lab, a free ball-physics toy", text: "Drop balls, flip gravity, make music.", url: url };
    var status = document.getElementById("bl-status");
    if (navigator.share) { navigator.share(data).catch(function () {}); return; }
    if (navigator.clipboard) navigator.clipboard.writeText(url).then(function () { if (status) status.textContent = "Link copied."; });
  }

  document.addEventListener("click", function (e) {
    var el = e.target.closest("[data-act],[data-mode]"); if (!el) return;
    if (el.hasAttribute("data-mode")) { setMode(el.getAttribute("data-mode")); ensureAudio(); }
    else act(el.getAttribute("data-act"));
  });
  function pos(e) { var r = canvas.getBoundingClientRect(); return { x: e.clientX - r.left, y: e.clientY - r.top }; }
  canvas.addEventListener("pointerdown", function (e) {
    var p = pos(e); pointer.x = p.x; pointer.y = p.y; pointer.down = pointer.inside = true;
    ensureAudio(); if (audio && audio.state === "suspended") audio.resume();
    if (mode === "sandbox") { burst(4, p.x, p.y); }
    try { canvas.setPointerCapture(e.pointerId); } catch (x) { /* older browsers */ }
  });
  canvas.addEventListener("pointermove", function (e) { var p = pos(e); pointer.x = p.x; pointer.y = p.y; pointer.inside = true; });
  canvas.addEventListener("pointerup", function () { pointer.down = false; });
  canvas.addEventListener("pointerleave", function () { pointer.inside = false; pointer.down = false; });
  window.addEventListener("resize", resize);

  resize(); setMode("sandbox"); requestAnimationFrame(frame);
  window.BallLab = { balls: function () { return balls.length; }, hits: function () { return hits; }, mode: function () { return mode; },
                     act: act, setMode: setMode, polyState: polyState, config: { POLY_N: POLY_N, POLY_PERIOD: POLY_PERIOD, MAX_BALLS: MAX_BALLS },
                     size: function () { return [W, H]; }, polyT: function () { return polyT; } };
})();
