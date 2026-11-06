/* Mac keyboard tester. Reads KeyboardEvent.code only. Nothing typed is stored, logged or sent anywhere. */
(function () {
  "use strict";

  /* [code, label, width in quarter-units]. The grid is 60 columns, 15 key-units wide. */
  var ROWS = [
    [["Escape", "esc", 6], ["F1", "F1", 4], ["F2", "F2", 4], ["F3", "F3", 4], ["F4", "F4", 4], ["F5", "F5", 4], ["F6", "F6", 4],
     ["F7", "F7", 4], ["F8", "F8", 4], ["F9", "F9", 4], ["F10", "F10", 4], ["F11", "F11", 4], ["F12", "F12", 4]],
    [["Backquote", "`", 4], ["Digit1", "1", 4], ["Digit2", "2", 4], ["Digit3", "3", 4], ["Digit4", "4", 4], ["Digit5", "5", 4],
     ["Digit6", "6", 4], ["Digit7", "7", 4], ["Digit8", "8", 4], ["Digit9", "9", 4], ["Digit0", "0", 4], ["Minus", "-", 4],
     ["Equal", "=", 4], ["Backspace", "delete", 8]],
    [["Tab", "tab", 6], ["KeyQ", "Q", 4], ["KeyW", "W", 4], ["KeyE", "E", 4], ["KeyR", "R", 4], ["KeyT", "T", 4], ["KeyY", "Y", 4],
     ["KeyU", "U", 4], ["KeyI", "I", 4], ["KeyO", "O", 4], ["KeyP", "P", 4], ["BracketLeft", "[", 4], ["BracketRight", "]", 4],
     ["Backslash", "\\", 6]],
    [["CapsLock", "caps lock", 7], ["KeyA", "A", 4], ["KeyS", "S", 4], ["KeyD", "D", 4], ["KeyF", "F", 4], ["KeyG", "G", 4],
     ["KeyH", "H", 4], ["KeyJ", "J", 4], ["KeyK", "K", 4], ["KeyL", "L", 4], ["Semicolon", ";", 4], ["Quote", "'", 4],
     ["Enter", "return", 9]],
    [["ShiftLeft", "shift", 9], ["KeyZ", "Z", 4], ["KeyX", "X", 4], ["KeyC", "C", 4], ["KeyV", "V", 4], ["KeyB", "B", 4],
     ["KeyN", "N", 4], ["KeyM", "M", 4], ["Comma", ",", 4], ["Period", ".", 4], ["Slash", "/", 4], ["ShiftRight", "shift", 11]],
    [["Fn", "fn", 4, "unseen"], ["ControlLeft", "control", 4], ["AltLeft", "option", 4], ["MetaLeft", "command", 5],
     ["Space", "", 22], ["MetaRight", "command", 5], ["AltRight", "option", 4], ["ArrowLeft", "◀", 4], ["ArrowUpDown", "", 4], ["ArrowRight", "▶", 4]]
  ];

  var NAMES = {
    Escape: "Escape", Backspace: "Delete", Tab: "Tab", CapsLock: "Caps Lock", Enter: "Return", ShiftLeft: "Left Shift",
    ShiftRight: "Right Shift", ControlLeft: "Left Control", AltLeft: "Left Option", AltRight: "Right Option",
    MetaLeft: "Left Command", MetaRight: "Right Command", Space: "Space", ArrowLeft: "Left arrow", ArrowRight: "Right arrow",
    ArrowUp: "Up arrow", ArrowDown: "Down arrow", Backquote: "` (backtick)", Minus: "- (minus)", Equal: "= (equals)",
    BracketLeft: "[", BracketRight: "]", Backslash: "\\ (backslash)", Semicolon: "; (semicolon)", Quote: "' (quote)",
    Comma: ", (comma)", Period: ". (period)", Slash: "/ (slash)", Fn: "fn (Globe)"
  };
  function nameOf(code) {
    if (NAMES[code]) return NAMES[code];
    var m = /^Key([A-Z])$/.exec(code) || /^Digit([0-9])$/.exec(code);
    return m ? m[1] : code;
  }

  var board = document.getElementById("kt-board");
  if (!board) return;
  var elTested = document.getElementById("kt-tested");
  var elHeld = document.getElementById("kt-held");
  var elMax = document.getElementById("kt-max");
  var elLast = document.getElementById("kt-last");
  var elMissing = document.getElementById("kt-missing");
  var elMissingCount = document.getElementById("kt-missing-count");
  var elOther = document.getElementById("kt-other");
  var elCapture = document.getElementById("kt-capture");
  var btnReset = document.getElementById("kt-reset");
  var swSound = document.getElementById("kt-sound");
  var soundRadios = document.querySelectorAll('input[name="kt-set"]');
  var soundStatus = document.getElementById("kt-sound-status");

  var keyEls = {}, order = [], tested = {}, held = {}, maxHeld = 0, other = [], soundOn = false;

  function make(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text) e.textContent = text;
    return e;
  }

  function build() {
    ROWS.forEach(function (row) {
      var rowEl = make("div", "kt-row");
      row.forEach(function (k) {
        var code = k[0], cls = "kt-key kt-w" + k[2];
        if (code === "ArrowUpDown") {
          var stack = make("div", "kt-stack kt-w4");
          [["ArrowUp", "▲"], ["ArrowDown", "▼"]].forEach(function (a) {
            var half = make("div", "kt-key kt-half", a[1]);
            keyEls[a[0]] = half; order.push(a[0]);
            stack.appendChild(half);
          });
          rowEl.appendChild(stack);
          return;
        }
        var el = make("div", cls, k[1]);
        if (code === "Fn") { el.classList.add("kt-unseen"); }
        else { order.push(code); keyEls[code] = el; }
        if (/^(F\d+|Escape)$/.test(code)) el.classList.add("kt-small");
        rowEl.appendChild(el);
      });
      board.appendChild(rowEl);
    });
  }

  function render() {
    var n = 0, missing = [];
    order.forEach(function (c) {
      var el = keyEls[c];
      el.classList.toggle("kt-tested", !!tested[c]);
      el.classList.toggle("kt-held", !!held[c]);
      if (tested[c]) n++; else missing.push(nameOf(c));
    });
    var heldN = Object.keys(held).length;
    elTested.textContent = n + " of " + order.length;
    elHeld.textContent = String(heldN);
    elMax.textContent = String(maxHeld);
    elMissingCount.textContent = String(missing.length);
    elMissing.textContent = missing.length ? missing.join(", ") : "None. The browser saw every key on this layout.";
    elOther.textContent = other.length ? other.join(", ") : "None yet.";
  }

  function reset() {
    tested = {}; held = {}; maxHeld = 0; other = [];
    elLast.textContent = "Press a key.";
    render();
  }

  function isModifier(code) {
    return /^(Shift|Control|Alt|Meta)(Left|Right)$/.test(code);
  }

  function mark(code, down) {
    if (code === "ArrowUp" || code === "ArrowDown" || keyEls[code]) {
      if (down) { tested[code] = true; held[code] = true; }
      else delete held[code];
    } else if (down) {
      var label = nameOf(code);
      if (other.indexOf(label) < 0) other.push(label);
    }
    var cnt = Object.keys(held).length;
    if (cnt > maxHeld) maxHeld = cnt;
  }

  function boardHasFocus(target) {
    return target === board;
  }

  function onKeyDown(e) {
    var code = e.code;
    if (!code) return;
    /* Keep Tab free so keyboard users can always move on. Tab still lights up. Command and Control
       shortcuts are left to the browser. */
    if (boardHasFocus(e.target) && code !== "Tab" && !e.metaKey && !e.ctrlKey) e.preventDefault();
    if (!e.repeat) {
      mark(code, true);
      elLast.textContent = nameOf(code) + " (" + code + ")";
      if (soundOn && window.KeySounds) window.KeySounds.play(currentSet(), "down", code);
    }
    render();
  }

  function onKeyUp(e) {
    var code = e.code;
    if (!code) return;
    mark(code, false);
    /* macOS sends no keyup for a key pressed while Command is held, so release them with Command. */
    if (code === "MetaLeft" || code === "MetaRight") {
      Object.keys(held).forEach(function (c) { if (!isModifier(c)) delete held[c]; });
    }
    if (soundOn && window.KeySounds) window.KeySounds.play(currentSet(), "up", code);
    render();
  }

  function currentSet() {
    for (var i = 0; i < soundRadios.length; i++) if (soundRadios[i].checked) return soundRadios[i].value;
    return "tactile";
  }

  function setSoundStatus(t) { soundStatus.textContent = t; }

  function loadCurrent() {
    var set = currentSet();
    setSoundStatus("Loading " + window.KeySounds.sets[set].label + "...");
    window.KeySounds.load(set).then(function (ok) {
      if (!soundOn || set !== currentSet()) return;
      setSoundStatus(ok ? window.KeySounds.sets[set].label + " is on. " + window.KeySounds.sets[set].note : "The sounds could not be loaded. Check your connection and try again.");
    });
  }

  function toggleSound() {
    if (!window.KeySounds || !window.KeySounds.unlock()) {
      setSoundStatus("This browser cannot play Web Audio, so sound is unavailable.");
      return;
    }
    soundOn = !soundOn;
    swSound.setAttribute("aria-checked", soundOn ? "true" : "false");
    swSound.textContent = soundOn ? "Sound on" : "Sound off";
    if (soundOn) loadCurrent(); else setSoundStatus("Sound is off.");
  }

  function focusBoard() { board.focus({ preventScroll: true }); }

  build();
  reset();

  document.addEventListener("keydown", onKeyDown);
  document.addEventListener("keyup", onKeyUp);
  window.addEventListener("blur", function () { held = {}; render(); });
  board.addEventListener("focus", function () { elCapture.textContent = "The keyboard is capturing keys. Press Tab to move on."; });
  board.addEventListener("blur", function () { elCapture.textContent = "Click the keyboard above so the page does not scroll or act on the keys you press."; });
  board.addEventListener("pointerdown", function () { focusBoard(); });

  swSound.addEventListener("click", function (e) {
    toggleSound();
    if (e.detail > 0) focusBoard();
  });
  soundRadios.forEach(function (r) {
    r.addEventListener("change", function () {
      if (soundOn) loadCurrent();
      else setSoundStatus(window.KeySounds.sets[currentSet()].label + " selected. Turn sound on to hear it.");
    });
    r.addEventListener("click", function (e) { if (e.detail > 0) focusBoard(); });
  });
  btnReset.addEventListener("click", function (e) {
    reset();
    if (e.detail > 0) focusBoard();
  });
})();
