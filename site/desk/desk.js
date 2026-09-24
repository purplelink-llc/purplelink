// Research desk: optional Amazon Associates tagging for a[data-amazon] links.
const AMAZON_TAG = "";  // Amazon Associates tracking id, e.g. "yourtag-20". Empty = links go out untagged.

(function () {
  if (!AMAZON_TAG) return;
  document.querySelectorAll("a[data-amazon]").forEach(function (link) {
    try {
      const url = new URL(link.getAttribute("href"), window.location.href);
      url.searchParams.set("tag", AMAZON_TAG);
      link.setAttribute("href", url.toString());
    } catch (e) {
      // Leave a malformed href untouched.
    }
  });
})();
