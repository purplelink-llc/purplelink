/* Keyfeel sample player. Shared by /tools/mac-keyboard-tester/ and the "Hear it" button on /keyfeel/.
   The recordings are Keyfeel's own CC0 1.0 sets, self-hosted under /tools/mac-keyboard-tester/sounds/.
   Nothing here plays until play() is called from a click or key press, and the AudioContext is only
   created by unlock(), which callers run inside a user gesture. */
(function () {
  "use strict";
  var BASE = "/tools/mac-keyboard-tester/sounds/";
  function seq(dir, prefix, n) {
    var out = [];
    for (var i = 1; i <= n; i++) out.push(dir + "/" + prefix + "-" + (i < 10 ? "0" : "") + i + ".wav");
    return out;
  }
  var SETS = {
    tactile: {
      label: "Tactile",
      note: "A tactile mechanical keyboard, one recording per key press.",
      down: seq("tactile", "press", 8), up: seq("tactile", "release", 8),
      space: ["tactile/space-press-01.wav"], spaceUp: ["tactile/space-release-01.wav"], enter: ["tactile/enter-press-01.wav"]
    },
    dome: {
      label: "Dome",
      note: "A Cherry KC 1000 rubber-dome keyboard. Softer and quieter than a mechanical board.",
      down: seq("dome", "press", 8), up: seq("dome", "release", 8),
      space: ["dome/space-press-01.wav"], spaceUp: ["dome/space-release-01.wav"], enter: ["dome/enter-press-01.wav"]
    },
    wood: {
      label: "Soft wood",
      note: "Gentle taps on a wooden table. Key presses only.",
      down: seq("wood", "take", 4), up: [], space: [], spaceUp: [], enter: []
    }
  };

  var ctx = null, gain = null, buffers = {}, loading = {}, last = {};

  function unlock() {
    if (!ctx) {
      var AC = window.AudioContext || window.webkitAudioContext;
      if (!AC) return false;
      ctx = new AC();
      gain = ctx.createGain();
      gain.gain.value = 0.8;
      gain.connect(ctx.destination);
    }
    if (ctx.state === "suspended" && ctx.resume) ctx.resume();
    return true;
  }

  function decode(data) {
    return new Promise(function (resolve, reject) {
      var p = ctx.decodeAudioData(data, resolve, reject);
      if (p && p.then) p.then(resolve, reject);
    });
  }

  function loadFile(path) {
    if (buffers[path]) return Promise.resolve(buffers[path]);
    if (loading[path]) return loading[path];
    loading[path] = fetch(BASE + path).then(function (r) {
      if (!r.ok) throw new Error("HTTP " + r.status);
      return r.arrayBuffer();
    }).then(decode).then(function (b) { buffers[path] = b; return b; });
    return loading[path];
  }

  function files(set) {
    var s = SETS[set], all = [];
    ["down", "up", "space", "spaceUp", "enter"].forEach(function (k) { all = all.concat(s[k]); });
    return all;
  }

  /* Fetch and decode a whole set. Resolves true when every file is ready, false if the context or a file is missing. */
  function load(set) {
    if (!SETS[set] || !unlock()) return Promise.resolve(false);
    return Promise.all(files(set).map(loadFile)).then(function () { return true; }, function () { return false; });
  }

  function pick(list, key) {
    if (!list.length) return null;
    var i = Math.floor(Math.random() * list.length);
    if (list.length > 1 && last[key] === i) i = (i + 1) % list.length;
    last[key] = i;
    return list[i];
  }

  /* kind: "down" | "up". code is a KeyboardEvent.code, used only to choose the Space or Enter recording. */
  function play(set, kind, code) {
    var s = SETS[set];
    if (!s || !ctx) return;
    var list;
    if (code === "Space") list = kind === "up" ? s.spaceUp : s.space;
    else if ((code === "Enter" || code === "NumpadEnter") && kind === "down" && s.enter.length) list = s.enter;
    else list = kind === "up" ? s.up : s.down;
    if (!list || !list.length) return;
    var path = pick(list, set + kind + (code === "Space" ? "s" : ""));
    var buf = buffers[path];
    if (!buf) return;
    var src = ctx.createBufferSource();
    src.buffer = buf;
    src.playbackRate.value = 0.97 + Math.random() * 0.06;
    src.connect(gain);
    src.start();
  }

  window.KeySounds = { sets: SETS, unlock: unlock, load: load, play: play };
})();
