window.setupPaidToolUpload({
  productCategory: "anonymity-check",
  submitPath: "/anonymity-check/submit",
  fields: [
    { type: "file", name: "file", elementId: "file-input", required: true, maxBytes: 20 * 1024 * 1024 },
    { type: "email", name: "email", elementId: "email-input", required: false },
  ],
});
