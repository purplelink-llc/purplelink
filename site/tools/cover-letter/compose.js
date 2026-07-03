// Cover Letter compose page — wires up the shared paid-tool helper.
window.setupPaidToolUpload({
  productCategory: "cover-letter",
  submitPath: "/cover-letter/submit",
  fields: [
    { type: "text",     name: "title",        elementId: "title-input",    required: false },
    { type: "textarea", name: "abstract",     elementId: "abstract-input", required: true },
    { type: "text",     name: "journal_name", elementId: "journal-input",  required: true },
    { type: "textarea", name: "custom_note",  elementId: "note-input",     required: false },
    { type: "email",    name: "email",        elementId: "email-input",    required: false },
  ],
  extraValidate: function (vals) {
    if ((vals.abstract || "").length > 5000) return "Abstract is too long (max 5,000 chars).";
    return null;
  },
});
