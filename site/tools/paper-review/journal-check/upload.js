// Journal check upload page: fill the journal list, then hand off to the shared paid-tool upload helper.
(function () {
  var select = document.getElementById("journal-input");
  function fill() {
    if (!select) return;
    fetch(API_BASE + "/paper-review/journals?domain=general")
      .then(function (resp) {
        if (!resp.ok) throw new Error("HTTP " + resp.status);
        return resp.json();
      })
      .then(function (data) {
        var opts = (data && data.journals) || [];
        select.innerHTML = "";
        var first = document.createElement("option");
        first.value = "";
        first.textContent = "Choose a journal";
        select.appendChild(first);
        opts.forEach(function (j) {
          var o = document.createElement("option");
          o.value = j.key;
          o.textContent = j.name;
          select.appendChild(o);
        });
        var wanted = new URLSearchParams(window.location.search).get("journal");
        if (wanted && opts.some(function (j) { return j.key === wanted; })) select.value = wanted;
        select.disabled = false;
      })
      .catch(function () {
        select.innerHTML = "";
        var o = document.createElement("option");
        o.value = "";
        o.textContent = "Could not load the journal list. Reload the page.";
        select.appendChild(o);
      });
  }
  fill();
  window.setupPaidToolUpload({
    productCategory: "journal-check",
    submitPath: "/journal-check/submit",
    fields: [
      { type: "select", name: "journal_key", elementId: "journal-input", required: false },
      { type: "file", name: "file", elementId: "file-input", required: true, maxBytes: 20 * 1024 * 1024 },
      { type: "email", name: "email", elementId: "email-input", required: false },
    ],
    extraValidate: function (values) {
      return values.journal_key ? null : "Choose a journal first.";
    },
  });
})();
