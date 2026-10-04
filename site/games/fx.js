/* Sound and feedback for /games/. Everything is synthesised in the browser with the Web Audio API
   (no audio files). Sound is on at a low volume and one tap on the speaker button turns it off;
   the choice is remembered on this device. Motion helpers do nothing when the visitor prefers
   reduced motion. Load before the game scripts. */
(function () {
  "use strict";
  var KEY = "pl-games-sound";
  var ctx = null, master = null, on = true, listeners = [];

  try { on = localStorage.getItem(KEY) !== "off"; } catch (e) { on = true; }

  function reduced() { try { return window.matchMedia("(prefers-reduced-motion: reduce)").matches; } catch (e) { return true; } }

  function audio() {
    if (!on) return null;
    try {
      if (!ctx) {
        var C = window.AudioContext || window.webkitAudioContext;
        if (!C) return null;
        ctx = new C();
        master = ctx.createGain();
        master.gain.value = 0.55;
        var comp = ctx.createDynamicsCompressor();
        master.connect(comp); comp.connect(ctx.destination);
      }
      if (ctx.state === "suspended") ctx.resume();
      return ctx;
    } catch (e) { return null; }
  }

  // One enveloped oscillator note. `at` is seconds from now.
  function tone(freq, at, dur, type, vol, glide) {
    var c = audio(); if (!c) return;
    var t = c.currentTime + at, o = c.createOscillator(), g = c.createGain();
    o.type = type || "sine";
    o.frequency.setValueAtTime(freq, t);
    if (glide) o.frequency.exponentialRampToValueAtTime(Math.max(30, freq + glide), t + dur);
    g.gain.setValueAtTime(0.0001, t);
    g.gain.exponentialRampToValueAtTime(vol || 0.1, t + 0.008);
    g.gain.exponentialRampToValueAtTime(0.0001, t + dur);
    o.connect(g); g.connect(master);
    o.start(t); o.stop(t + dur + 0.03);
  }

  // A short filtered noise burst: the "wood" of a chess move or a sudoku digit.
  function thud(at, dur, freq, vol) {
    var c = audio(); if (!c) return;
    var t = c.currentTime + at, n = Math.max(1, Math.floor(c.sampleRate * dur)), buf = c.createBuffer(1, n, c.sampleRate), d = buf.getChannelData(0);
    for (var i = 0; i < n; i++) d[i] = (Math.random() * 2 - 1) * Math.pow(1 - i / n, 3);
    var s = c.createBufferSource(), f = c.createBiquadFilter(), g = c.createGain();
    s.buffer = buf; f.type = "bandpass"; f.frequency.value = freq; f.Q.value = 1.2;
    g.gain.value = vol || 0.3;
    s.connect(f); f.connect(g); g.connect(master);
    s.start(t);
  }

  function arp(notes, gap, type, vol, len) {
    notes.forEach(function (f, i) { tone(f, i * gap, len || 0.28, type || "triangle", vol || 0.09); });
  }

  var SOUNDS = {
    tap: function () { tone(660, 0, 0.05, "sine", 0.06); },
    key: function () { tone(480, 0, 0.035, "triangle", 0.045); },
    back: function () { tone(330, 0, 0.04, "triangle", 0.04); },
    flip: function (i) { tone(320 + (i || 0) * 46, 0, 0.1, "triangle", 0.07); },
    good: function () { tone(659, 0, 0.14, "sine", 0.1); tone(880, 0.09, 0.2, "sine", 0.1); },
    bad: function () { tone(210, 0, 0.22, "triangle", 0.09, -70); },
    place: function () { thud(0, 0.05, 900, 0.32); tone(210, 0, 0.06, "sine", 0.07); },
    capture: function () { thud(0, 0.09, 1800, 0.4); tone(150, 0, 0.12, "triangle", 0.1, -30); },
    check: function () { tone(988, 0, 0.1, "square", 0.025); tone(1319, 0.08, 0.16, "square", 0.025); },
    unit: function () { arp([523, 659, 784], 0.05, "sine", 0.06, 0.2); },
    reveal: function () { tone(440, 0, 0.12, "sine", 0.05); },
    win: function () { arp([523, 659, 784, 1047], 0.075, "triangle", 0.09, 0.34); tone(1319, 0.34, 0.7, "sine", 0.07); tone(1047, 0.34, 0.7, "sine", 0.05); },
    big: function () { arp([392, 523, 659, 784, 1047, 1319], 0.065, "triangle", 0.09, 0.34); tone(1568, 0.45, 0.9, "sine", 0.07); tone(1047, 0.45, 0.9, "sine", 0.05); },
    lose: function () { arp([392, 349, 294], 0.16, "triangle", 0.07, 0.4); },
    quest: function () { tone(880, 0, 0.9, "sine", 0.09); tone(1760, 0, 0.6, "sine", 0.04); tone(1320, 0.12, 0.8, "sine", 0.05); },
    level: function () { arp([392, 494, 587, 698, 784, 988, 1175], 0.07, "triangle", 0.085, 0.32); tone(1568, 0.55, 1.1, "sine", 0.07); },
    ach: function () { [1319, 1568, 1976, 2349].forEach(function (f, i) { tone(f, i * 0.06, 0.3, "sine", 0.045); }); },
    toggle: function () { tone(520, 0, 0.06, "sine", 0.07); tone(780, 0.06, 0.08, "sine", 0.07); }
  };

  function play(name, arg) {
    if (!on || !SOUNDS[name]) return;
    try { SOUNDS[name](arg); } catch (e) { /* sound is optional */ }
  }

  function vibrate(p) { try { if (on && navigator.vibrate) navigator.vibrate(p); } catch (e) { /* ignore */ } }

  function setSound(v) {
    on = !!v;
    try { localStorage.setItem(KEY, on ? "on" : "off"); } catch (e) { /* ignore */ }
    if (on) play("toggle");
    listeners.forEach(function (fn) { fn(on); });
  }

  // Restart a CSS animation class on an element.
  function kick(el, cls, ms) {
    if (!el || reduced()) return;
    el.classList.remove(cls);
    void el.offsetWidth;
    el.classList.add(cls);
    if (ms) window.setTimeout(function () { el.classList.remove(cls); }, ms);
  }

  // Run a class across a list of elements, one after another.
  function wave(els, cls, gap, ms) {
    if (reduced()) return;
    Array.prototype.forEach.call(els, function (el, i) {
      window.setTimeout(function () { kick(el, cls, ms || 600); }, i * (gap || 40));
    });
  }

  // Count a number up from its current value.
  function count(el, to, ms) {
    if (!el) return;
    var from = parseInt(el.textContent, 10) || 0;
    if (reduced() || from === to) { el.textContent = String(to); return; }
    var t0 = null, dur = ms || 700;
    function step(t) {
      if (t0 === null) t0 = t;
      var k = Math.min(1, (t - t0) / dur), e = 1 - Math.pow(1 - k, 4);
      el.textContent = String(Math.round(from + (to - from) * e));
      if (k < 1) window.requestAnimationFrame(step);
    }
    window.requestAnimationFrame(step);
  }

  // A small label that rises out of an element and fades: "+15 XP".
  function float(el, text) {
    if (!el || reduced()) return;
    var r = el.getBoundingClientRect(), f = document.createElement("span");
    f.className = "fx-float"; f.textContent = text; f.setAttribute("aria-hidden", "true");
    f.style.left = (r.left + r.width / 2) + "px"; f.style.top = (r.top + window.scrollY) + "px";
    document.body.appendChild(f);
    window.setTimeout(function () { if (f.parentNode) f.parentNode.removeChild(f); }, 1300);
  }

  // Wire any speaker buttons on the page (button[data-fx-sound]).
  function paintToggle(btn) {
    btn.setAttribute("aria-pressed", on ? "true" : "false");
    btn.setAttribute("aria-label", on ? "Sound on. Turn sound off" : "Sound off. Turn sound on");
    var use = btn.querySelector("use");
    if (use) use.setAttribute("href", "/games/glyphs.svg#" + (on ? "sound-on" : "sound-off"));
    var lab = btn.querySelector(".fx-label");
    if (lab) lab.textContent = on ? "Sound on" : "Sound off";
  }
  function mount() {
    Array.prototype.forEach.call(document.querySelectorAll("[data-fx-sound]"), function (btn) {
      if (btn.getAttribute("data-fx-wired")) return;
      btn.setAttribute("data-fx-wired", "1");
      paintToggle(btn);
      btn.addEventListener("click", function () { setSound(!on); });
      listeners.push(function () { paintToggle(btn); });
    });
  }

  // A soft tick on buttons and links that make no sound of their own.
  document.addEventListener("click", function (e) {
    var t = e.target && e.target.closest ? e.target.closest(".btn, .game-card, .dock-link, .next-card") : null;
    if (t && !t.hasAttribute("data-fx-wired") && !t.hasAttribute("data-quiet")) play("tap");
  }, true);

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", mount); else mount();

  window.PLFX = { play: play, vibrate: vibrate, setSound: setSound, isOn: function () { return on; }, reduced: reduced, kick: kick, wave: wave, count: count, float: float, mount: mount };
})();
