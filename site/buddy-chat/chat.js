/* Buddy chat panel (docs/designs/buddy-chat.md, sections 2-6). Loaded by loader.js on the first click.
   Model text is never parsed as HTML: it goes in with textContent, and only allow-listed purplelink.llc paths
   become links. */
(function () {
  "use strict";

  var API = "https://ben-ampel--purplelink-latextools-web.modal.run";
  var BASE = "/buddy-chat/";
  var MOCK = /[?&]buddy-mock=1\b/.test(location.search) || /^(localhost|127\.0\.0\.1)$/.test(location.hostname);
  var MAX_LEN = 600;
  var SOUND_KEY = "buddy-chat-sound";

  var panel, log, input, sendBtn, soundBtn, avatar, launcher;
  var turns = [];
  var busy = false;
  var formTs = "";
  var allowed = null;
  var convo = (crypto.randomUUID && crypto.randomUUID()) || String(Date.now()) + Math.random().toString(16).slice(2);

  function track(type, meta) { try { if (window.plTrack) window.plTrack(type, meta || ""); } catch (e) {} }

  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text != null) n.textContent = text;
    return n;
  }

  // ---- sounds (section 3) -------------------------------------------------------------------------------------
  var Sound = (function () {
    var ctx = null, buffers = { down: [], up: [], space: [], enter: [] }, loaded = false;
    var FILES = {
      down: ["down-1", "down-2", "down-3", "down-4", "down-5", "down-6"],
      up: ["up-1", "up-2", "up-3", "up-4", "up-5", "up-6"],
      space: ["space-1"],
      enter: ["enter-1"]
    };
    function on() {
      try { return localStorage.getItem(SOUND_KEY) !== "off"; } catch (e) { return true; }
    }
    function set(v) { try { localStorage.setItem(SOUND_KEY, v ? "on" : "off"); } catch (e) {} }
    function ext() {
      var a = document.createElement("audio");
      return a.canPlayType('audio/webm; codecs="opus"') ? ".webm" : ".m4a";
    }
    function load() {
      if (loaded || !window.AudioContext && !window.webkitAudioContext) return;
      loaded = true;
      ctx = new (window.AudioContext || window.webkitAudioContext)();
      var e = ext();
      Object.keys(FILES).forEach(function (role) {
        FILES[role].forEach(function (name) {
          fetch(BASE + "sounds/" + name + e)
            .then(function (r) { return r.ok ? r.arrayBuffer() : Promise.reject(); })
            .then(function (b) { return new Promise(function (ok, no) { ctx.decodeAudioData(b, ok, no); }); })
            .then(function (buf) { buffers[role].push(buf); })
            .catch(function () {});
        });
      });
    }
    function play(role) {
      if (!on() || !ctx) return;
      var list = buffers[role].length ? buffers[role] : buffers.down;
      if (!list.length) return;
      if (ctx.state === "suspended") ctx.resume();
      var src = ctx.createBufferSource();
      src.buffer = list[Math.floor(Math.random() * list.length)];
      src.playbackRate.value = 0.97 + Math.random() * 0.06;
      var g = ctx.createGain();
      g.gain.value = 0.35;
      src.connect(g).connect(ctx.destination);
      src.start();
    }
    return { on: on, set: set, load: load, play: play };
  })();

  // ---- links (section 4) --------------------------------------------------------------------------------------
  function loadAllowed() {
    fetch(BASE + "links.json").then(function (r) { return r.ok ? r.json() : []; })
      .then(function (list) {
        allowed = new Map();
        (Array.isArray(list) ? list : []).forEach(function (p) {
          if (typeof p === "string" && /^\/[a-z0-9\/._-]*$/i.test(p)) allowed.set(p, p);
        });
      })
      .catch(function () { allowed = new Map(); });
  }
  // The href is always the allow-list's own string (from links.json), never text from the model.
  function safeLink(raw) {
    var u;
    try { u = new URL(raw); } catch (e) { return null; }
    if (u.protocol !== "https:" || u.hostname !== "purplelink.llc" || u.search || u.username || u.password) return null;
    var listed = allowed && allowed.get(u.pathname.replace(/\/?$/, "/"));
    return listed ? { href: listed, label: "purplelink.llc" + listed } : null;
  }
  function renderText(node, text) {
    var re = /https:\/\/purplelink\.llc[^\s<>"')\]]*/g, last = 0, m;
    while ((m = re.exec(text))) {
      var raw = m[0].replace(/[.,;:!?]+$/, "");
      var link = safeLink(raw);
      node.appendChild(document.createTextNode(text.slice(last, m.index)));
      if (link) {
        var a = el("a", null, link.label);
        a.href = link.href;
        node.appendChild(a);
      } else {
        node.appendChild(document.createTextNode(raw));
      }
      last = m.index + raw.length;
      re.lastIndex = last;
    }
    node.appendChild(document.createTextNode(text.slice(last)));
  }

  // ---- face states ----------------------------------------------------------------------------------------------
  var blinkTimer = null;
  function blinkLoop() {
    clearTimeout(blinkTimer);
    blinkTimer = setTimeout(function () {
      avatar.classList.add("bc-blink");
      setTimeout(function () { avatar.classList.remove("bc-blink"); }, 200);
      blinkLoop();
    }, 3000 + Math.random() * 3000);
  }
  function mood(name) {
    avatar.classList.toggle("is-thinking", name === "thinking");
    avatar.classList.toggle("is-happy", name === "happy");
  }

  // ---- messages -------------------------------------------------------------------------------------------------
  function say(who, text) {
    var p = el("p", "bc-msg bc-msg--" + who);
    if (who === "buddy") renderText(p, text); else p.textContent = text;
    log.appendChild(p);
    log.scrollTop = log.scrollHeight;
    return p;
  }
  function chips() {
    var row = el("div", "bc-chips");
    [["free_check", "Free citation check"], ["app_fit", "Which app fits me?"], ["latex", "Help with a LaTeX error"]]
      .forEach(function (c) {
        var b = el("button", "bc-chip", c[1]);
        b.type = "button";
        b.addEventListener("click", function () {
          track("chat_offer", c[0]);
          if (c[0] === "free_check") freeCheckForm();
          else send(c[1]);
        });
        row.appendChild(b);
      });
    log.appendChild(row);
  }

  function post(path, body) {
    if (MOCK) return mockPost(path, body);
    return fetch(API + path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body)
    }).then(function (r) { return r.json().catch(function () { return {}; }); });
  }

  function send(text) {
    text = (text || "").trim().slice(0, MAX_LEN);
    if (!text || busy) return;
    busy = true;
    sendBtn.disabled = true;
    say("you", text);
    turns.push({ text: text });
    track("chat_message");
    var wait = say("wait", "Buddy is thinking");
    wait.className = "bc-msg bc-msg--buddy bc-msg--wait";
    mood("thinking");
    post("/buddy/chat", { conversation_id: convo, turns: turns.slice(-8) })
      .then(function (res) { return res && res.reply ? res.reply : "Something went wrong. You can write to Ben instead."; })
      .catch(function () { return "I could not reach the server. You can write to Ben instead."; })
      .then(function (reply) {
        wait.remove();
        say("buddy", reply);
        mood("idle");
        busy = false;
        sendBtn.disabled = false;
        input.focus();
      });
  }

  // ---- free Citation Gap check (section 6) -----------------------------------------------------------------------
  function freeCheckForm() {
    if (panel.querySelector(".bc-form")) { panel.querySelector(".bc-form input").focus(); return; }
    var f = el("form", "bc-form");
    f.noValidate = true;
    f.appendChild(el("p", null, "One free check per email. I'll email you a link to upload your PDF."));
    var lab = el("label", null, "Email");
    lab.htmlFor = "bc-email";
    var email = el("input", "bc-field");
    email.type = "email"; email.id = "bc-email"; email.autocomplete = "email"; email.required = true;
    var hp = el("input", "bc-hp");
    hp.name = "website"; hp.tabIndex = -1; hp.autocomplete = "off"; hp.setAttribute("aria-hidden", "true");
    var go = el("button", "bc-send", "Send me the link");
    go.type = "submit";
    f.appendChild(lab); f.appendChild(email); f.appendChild(hp);
    f.appendChild(el("p", null, "Your PDF is sent to Anthropic for analysis and is not kept by us."));
    f.appendChild(go);
    f.addEventListener("submit", function (e) {
      e.preventDefault();
      if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.value.trim())) { email.focus(); return; }
      go.disabled = true;
      track("free_check_requested");
      post("/buddy/free-check", { email: email.value.trim(), website: hp.value, form_ts: formTs })
        .then(function (res) {
          f.remove();
          say("buddy", (res && res.message) || "Check your inbox for the upload link. It works for 3 days.");
          if (res && res.ok) { mood("happy"); setTimeout(function () { mood("idle"); }, 2500); }
        })
        .catch(function () { go.disabled = false; say("buddy", "That did not go through. Please try again."); });
    });
    log.appendChild(f);
    log.scrollTop = log.scrollHeight;
    email.focus();
  }

  // ---- panel ----------------------------------------------------------------------------------------------------
  function build() {
    panel = el("section", "bc-panel");
    panel.setAttribute("role", "dialog");
    panel.setAttribute("aria-label", "Chat with Buddy");
    panel.hidden = true;

    var head = el("div", "bc-head-row");
    avatar = el("div", "bc-avatar");
    avatar.innerHTML = window.__buddyFace;
    var title = el("div", "bc-title");
    title.appendChild(el("p", "bc-name", "Buddy"));
    var note = el("p", "bc-note", "AI, can be wrong. ");
    var ben = el("a", null, "Write to Ben");
    ben.href = "/support/";
    note.appendChild(ben);
    title.appendChild(note);

    soundBtn = el("button", "bc-icon-btn");
    soundBtn.type = "button";
    soundBtn.setAttribute("aria-label", "Key sounds");
    soundBtn.setAttribute("aria-pressed", String(Sound.on()));
    soundBtn.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 9v6h4l5 4V5L8 9z"/>' +
      '<path class="bc-wave" d="M16.5 8.5a5 5 0 0 1 0 7"/><path class="bc-mute" d="M17 9l5 6M22 9l-5 6"/></svg>';
    soundBtn.addEventListener("click", function () {
      var v = !Sound.on();
      Sound.set(v);
      soundBtn.setAttribute("aria-pressed", String(v));
    });
    var close = el("button", "bc-icon-btn");
    close.type = "button";
    close.setAttribute("aria-label", "Close chat");
    close.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 6l12 12M18 6L6 18"/></svg>';
    close.addEventListener("click", hide);

    head.appendChild(avatar); head.appendChild(title); head.appendChild(soundBtn); head.appendChild(close);

    log = el("div", "bc-log");
    log.setAttribute("aria-live", "polite");

    var compose = el("form", "bc-compose");
    var row = el("div", "bc-compose-row");
    input = el("textarea", "bc-field");
    input.rows = 1;
    input.maxLength = MAX_LEN;
    input.placeholder = "Ask a question";
    input.setAttribute("aria-label", "Message");
    sendBtn = el("button", "bc-send", "Send");
    sendBtn.type = "submit";
    row.appendChild(input); row.appendChild(sendBtn);
    var credit = el("p", "bc-credit", "Key sounds from ");
    var kf = el("a", null, "Keyfeel");
    kf.href = "/keyfeel/?utm_source=site&utm_medium=chat&utm_content=buddy-chat-sound";
    credit.appendChild(kf);
    credit.appendChild(document.createTextNode(", our Mac app."));
    compose.appendChild(row); compose.appendChild(credit);

    compose.addEventListener("submit", function (e) { e.preventDefault(); var t = input.value; input.value = ""; send(t); });
    input.addEventListener("keydown", function (e) {
      Sound.load();
      if (!e.repeat) Sound.play(e.key === " " ? "space" : e.key === "Enter" ? "enter" : "down");
      if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); compose.requestSubmit(); }
    });
    input.addEventListener("keyup", function (e) { if (e.key !== " " && e.key !== "Enter") Sound.play("up"); });

    panel.appendChild(head); panel.appendChild(log); panel.appendChild(compose);
    panel.addEventListener("keydown", function (e) { if (e.key === "Escape") hide(); });
    document.body.appendChild(panel);

    say("buddy", "Ask me about our Mac apps or paper tools. I can also run a free Citation Gap check on a paper draft.");
    chips();
    loadAllowed();
    fetchStatus();
  }

  function fetchStatus() {
    if (MOCK) { formTs = "mock"; return; }
    post("/buddy/status", {}).then(function (s) {
      formTs = s.form_ts || "";
      if (s.enabled === false) {
        input.disabled = true; sendBtn.disabled = true;
        say("buddy", "The chat is off for today. You can write to Ben instead.");
      }
    }).catch(function () {});
  }

  function show() {
    panel.hidden = false;
    launcher.setAttribute("aria-expanded", "true");
    blinkLoop();
    input.focus();
    track("chat_open", location.pathname);
  }
  function hide() {
    panel.hidden = true;
    clearTimeout(blinkTimer);
    launcher.setAttribute("aria-expanded", "false");
    launcher.focus();
  }

  // ---- canned replies for the local mock (no server) -----------------------------------------------------------
  function mockPost(path) {
    return new Promise(function (ok) {
      setTimeout(function () {
        if (path === "/buddy/free-check") ok({ ok: true, message: "Check your inbox for the upload link. It works for 3 days." });
        else ok({ reply: "ModernTex is a native Mac LaTeX editor: $19.99 once, with a 7-day trial. " +
          "If you write in Overleaf today, it opens the same projects and compiles offline. See https://purplelink.llc/moderntex/" });
      }, 900);
    });
  }

  window.BuddyChat = {
    toggle: function (btn) {
      launcher = btn;
      if (!panel) build();
      if (panel.hidden) show(); else hide();
    }
  };
})();
