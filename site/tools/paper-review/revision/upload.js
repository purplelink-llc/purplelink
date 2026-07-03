window.setupPaidToolUpload({
  productCategory: "revision-review",
  submitPath: "/revision-review/submit",
  fields: [
    { type: "file",     name: "file",                 elementId: "file-input",            required: true, maxBytes: 20 * 1024 * 1024 },
    { type: "textarea", name: "original_review_md",   elementId: "original-review-input", required: true },
    { type: "email",    name: "email",                elementId: "email-input",           required: false },
  ],
  extraValidate: function (v) {
    if ((v.original_review_md || "").length > 120000) return "Original review is too long (max 120k chars).";
    return null;
  },
});
