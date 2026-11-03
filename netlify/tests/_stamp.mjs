// ?v= asset stamps exist only in a build checkout: CI stamps the tree like the Netlify build before the tests run, and
// the committed pages are bare (docs/designs/generated-files-at-build.md, phase 2). STAMP is a RegExp source fragment
// that requires the stamp under CI=true and allows a bare reference in a local checkout.
export const STAMP = process.env.CI === "true" ? "\\?v=[0-9a-f]{10}" : "(?:\\?v=[0-9a-f]{10})?";
