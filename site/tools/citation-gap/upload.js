window.setupPaidToolUpload({
  productCategory: "citation-gap",
  submitPath: "/citation-gap/submit",
  fields: [
    { type: "file", name: "file", elementId: "file-input", required: true, maxBytes: 20 * 1024 * 1024 },
    { type: "email", name: "email", elementId: "email-input", required: false },
  ],
});
