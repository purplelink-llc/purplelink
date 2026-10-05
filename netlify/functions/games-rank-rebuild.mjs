// Weekly, Monday 09:00 UTC: recompute the games histograms and daily boards from the accounts. See rebuildRanks in games-api.mjs.
import { createHandler } from "./games-api.mjs";

export default async function () {
  const { getStore } = await import("@netlify/blobs");
  const result = await createHandler({ getStore, env: (k) => Netlify.env.get(k) }).rebuild();
  console.log("games-rank-rebuild", JSON.stringify(result));
  return new Response(JSON.stringify(result), { status: 200, headers: { "Content-Type": "application/json", "Cache-Control": "no-store" } });
}

export const config = { schedule: "0 9 * * 1" };
