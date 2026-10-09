// Every product page's free-trial download link has to be one analytics.js counts, or the trial-to-sale funnel
// silently undercounts (Keyfeel's link changed to ?download=1 in 1.1.0 while the counter still looked for ?trial=1).
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync, existsSync } from "node:fs";

const analytics = readFileSync(new URL("../../site/analytics.js", import.meta.url), "utf8");

for (const product of ["moderntex", "outbound-veil", "legroom", "keyfeel", "tapefolio"]) {
  const pagePath = new URL(`../../site/${product}/index.html`, import.meta.url);
  if (!existsSync(pagePath)) continue;
  test(`analytics.js counts the ${product} trial download link`, () => {
    const page = readFileSync(pagePath, "utf8");
    const queries = [...new Set([...page.matchAll(new RegExp(`${product}-download\\?(\\w+)=1`, "g"))].map((m) => m[1]))];
    assert.ok(queries.length > 0, `no ${product}-download link on the page`);
    for (const q of queries) {
      const simple = analytics.includes(`${product}-download?${q}=1`);
      const pattern = new RegExp(`${product}-download\\\\\\?\\(([^)]*)\\)=1`).exec(analytics);
      const viaPattern = pattern ? pattern[1].split("|").includes(q) : false;
      assert.ok(simple || viaPattern, `${product}'s page links ?${q}=1 but analytics.js does not count it`);
    }
  });
}
