/* "Hear it" on /keyfeel/: three Tactile keystrokes, played only after a click. */
(function () {
  "use strict";
  var btn = document.getElementById("kf-hear");
  if (!btn || !window.KeySounds) { if (btn) btn.hidden = true; return; }
  var KS = window.KeySounds, busy = false;
  var note = document.getElementById("kf-hear-status");
  var idle = note.innerHTML;

  btn.addEventListener("click", function () {
    if (busy) return;
    if (!KS.unlock()) { note.textContent = "This browser cannot play Web Audio, so there is no sound sample."; return; }
    busy = true;
    btn.setAttribute("aria-disabled", "true");
    note.textContent = "Loading the sound...";
    KS.load("tactile").then(function (ok) {
      if (!ok) {
        note.textContent = "The sound could not be loaded. Check your connection and try again.";
        busy = false; btn.removeAttribute("aria-disabled");
        return;
      }
      note.textContent = "Playing three keystrokes.";
      var codes = ["KeyK", "KeyF", "Space"], i = 0;
      (function next() {
        if (i >= codes.length) {
          note.innerHTML = idle;
          busy = false; btn.removeAttribute("aria-disabled");
          return;
        }
        var c = codes[i++];
        KS.play("tactile", "down", c);
        setTimeout(function () { KS.play("tactile", "up", c); }, 70);
        setTimeout(next, 260);
      })();
    });
  });
})();
