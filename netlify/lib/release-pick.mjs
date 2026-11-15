// Which DMG in an app's Blobs store counts as "the newest release" for the buyer and trial doors.
//
// Apps can publish a beta (`scripts/publish-release.sh <version> --beta` in the app repo): its appcast item carries
// <sparkle:channel>beta</sparkle:channel>, so Sparkle offers it only to installs that opted in. The DMG still sits in
// the same store, and the plain "highest version in the store" pick would hand it to every buyer and trial download.
// So versions whose appcast item has a channel are left out. The version is read from each enclosure's file name and
// excluded across every name pattern (paid and trial DMGs of a beta version both stay out).
// If the appcast is missing, unreadable or lists no DMG, nothing is excluded: the pick is exactly the old one.

/** The version numbers in a DMG file name ("Keyfeel-Trial-1.2.0.dmg" -> [1, 2, 0]), or null. */
export function dmgVersion(name) {
  const m = /(\d+(?:\.\d+)*)\.dmg$/.exec(name || "");
  return m ? m[1].split(".").map(Number) : null;
}

/** Compare two version arrays; missing parts count as 0 ("1.0" == "1.0.0"). */
export function compareVersions(a, b) {
  for (let i = 0; i < Math.max(a.length, b.length); i++) {
    const d = (a[i] || 0) - (b[i] || 0);
    if (d) return d;
  }
  return 0;
}

/** Versions whose appcast item carries a <sparkle:channel>, plus how many DMG items the feed lists. */
export function channelVersions(xml) {
  const betas = [];
  let items = 0;
  for (const m of String(xml || "").matchAll(/<item\b[\s\S]*?<\/item>/g)) {
    const item = m[0];
    const url = /<enclosure\b[^>]*\burl="([^"]+)"/.exec(item);
    if (!url) continue;
    const file = decodeURIComponent(url[1].split(/[/=]/).pop());
    const v = dmgVersion(file);
    if (!v) continue;
    items++;
    if (/<sparkle:channel>\s*[^<\s][^<]*<\/sparkle:channel>/.test(item)) betas.push(v);
  }
  return { betas, items };
}

/** The newest name (by version) that is not a channel (beta) version in `xml`. */
export function pickLatestDmg(names, xml) {
  const { betas } = channelVersions(xml);
  const candidates = names
    .map((name) => ({ name, v: dmgVersion(name) }))
    .filter((c) => c.v && !betas.some((b) => compareVersions(b, c.v) === 0));
  candidates.sort((a, b) => compareVersions(b.v, a.v));
  return candidates[0]?.name || null;
}

/** The newest released (non-beta) DMG in `store` whose key matches `pattern`. */
export async function latestReleasedDmg(store, pattern) {
  const { blobs } = await store.list();
  const names = blobs.map((b) => b.key).filter((k) => pattern.test(k));
  let xml = null;
  try {
    xml = await store.get("appcast.xml", { type: "text" });
  } catch {
    xml = null;
  }
  return pickLatestDmg(names, xml);
}
