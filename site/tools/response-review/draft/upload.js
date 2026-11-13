// Response letter drafting ($24, product "response-draft"). Field names match
// POST /response-review/draft/submit in backend/app.py: "file" is the ORIGINAL
// manuscript (required); "revised_file" is optional.
window.setupPaidToolUpload({
  productCategory: "response-draft",
  submitPath: "/response-review/draft/submit",
  fields: [
    { type: "file",     name: "file",              elementId: "file-input",     required: true,  maxBytes: 20 * 1024 * 1024 },
    { type: "file",     name: "revised_file",      elementId: "revised-input",  required: false, maxBytes: 20 * 1024 * 1024 },
    { type: "textarea", name: "reviewer_comments", elementId: "reviewer-input", required: true },
    { type: "textarea", name: "author_notes",      elementId: "notes-input",    required: false },
    { type: "email",    name: "email",             elementId: "email-input",    required: false },
  ],
  extraValidate: function (v) {
    if ((v.reviewer_comments || "").length > 60000) return "Reviewer comments are too long (max 60k chars).";
    if ((v.author_notes || "").length > 60000) return "Your notes are too long (max 60k chars).";
    return null;
  },
});
