window.setupPaidToolUpload({
  productCategory: "response-review",
  submitPath: "/response-review/submit",
  fields: [
    { type: "file",     name: "file",                elementId: "file-input",       required: true, maxBytes: 20 * 1024 * 1024 },
    { type: "textarea", name: "reviewer_comments",   elementId: "reviewer-input",   required: true },
    { type: "textarea", name: "author_response",     elementId: "response-input",   required: true },
    { type: "email",    name: "email",               elementId: "email-input",      required: false },
  ],
  extraValidate: function (v) {
    if ((v.reviewer_comments || "").length > 60000) return "Reviewer comments are too long (max 60k chars).";
    if ((v.author_response  || "").length > 60000) return "Response is too long (max 60k chars).";
    return null;
  },
});
