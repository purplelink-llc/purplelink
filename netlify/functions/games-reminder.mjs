/**
 * Netlify scheduled function: the optional "your streak ends tonight" email for /games/.
 *
 * Runs at 00:00 UTC (8 pm US Eastern). It only writes to accounts that turned the reminder on, only when a
 * streak of two or more days is alive (played yesterday, not yet today), and at most once per puzzle day.
 * Every email carries a one-click unsubscribe link (the same switch as on /games/account/).
 * Env: RESEND_API_KEY.
 */

import { dayIndexUTC, streakAtRisk } from "../lib/games-logic.mjs";

const SITE_ORIGIN = "https://purplelink.llc";
const RESEND_API_URL = "https://api.resend.com/emails";
const FROM_ADDRESS = "Purplelink LLC <orders@purplelink.llc>";
const REPLY_TO = "ben@purplelink.llc";
const MAX_PER_RUN = 500;
const NAMES = { linkle: "Linkle", quadlink: "Quadlink", "daily-five": "Daily Five", "daily-photo": "Daily Photo", crossword: "the crossword" };
const PATHS = { linkle: "linkle", quadlink: "quadlink", "daily-five": "daily-five", "daily-photo": "daily-photo", crossword: "crossword" };

export function reminderMail(email, acct, token, risks) {
  const top = risks[0];
  const off = `${SITE_ORIGIN}/games/account/?off=${acct}.${token}`;
  const link = `${SITE_ORIGIN}/games/${PATHS[top.game]}/`;
  const also = risks.length > 1 ? ` You also have streaks in ${risks.slice(1).map((r) => NAMES[r.game]).join(" and ")}.` : "";
  const subject = `Your ${top.streak}-day ${NAMES[top.game]} streak ends at midnight`;
  const text =
    `You have played ${NAMES[top.game]} ${top.streak} days in a row and have not played it today yet.${also}\n\n` +
    `A puzzle takes a few minutes: ${link}\n\n` +
    `You get this because you turned on streak reminders at ${SITE_ORIGIN}/games/account/. Turn it off with one click:\n${off}\n\n` +
    `Purplelink LLC, Atlanta, Georgia`;
  const html =
    `<p>You have played ${NAMES[top.game]} ${top.streak} days in a row and have not played it today yet.${also}</p>` +
    `<p><a href="${link}">Play today's puzzle</a>. It takes a few minutes.</p>` +
    `<p>You get this because you turned on streak reminders on your <a href="${SITE_ORIGIN}/games/account/">games account</a>. <a href="${off}">Turn it off with one click</a>.</p>` +
    `<p>Purplelink LLC, Atlanta, Georgia</p>`;
  return {
    from: FROM_ADDRESS, reply_to: REPLY_TO, to: [email], subject, text, html,
    headers: { "List-Unsubscribe": `<${off}>`, "List-Unsubscribe-Post": "List-Unsubscribe=One-Click" },
  };
}

export function createReminder({ getStore, env, fetchFn = (...a) => fetch(...a), now = () => Date.now() }) {
  return async function run() {
    const apiKey = env("RESEND_API_KEY");
    if (!apiKey) return { sent: 0, skipped: "no_api_key" };
    const store = getStore("games-accounts");
    const idx = dayIndexUTC(new Date(now() - 6 * 3600 * 1000));   // 8 pm Eastern is still the same puzzle day
    let sent = 0, checked = 0;
    const { blobs } = await store.list({ prefix: "acct:" });
    for (const { key } of blobs) {
      if (sent >= MAX_PER_RUN) break;
      const acct = await store.get(key, { type: "json" });
      checked++;
      if (!acct || !acct.remind || !acct.remindToken || !acct.email || acct.lastRemind === idx) continue;
      const risks = streakAtRisk(acct.data, idx);
      if (!risks.length) continue;
      const mail = reminderMail(acct.email, key.slice("acct:".length), acct.remindToken, risks);
      try {
        const resp = await fetchFn(RESEND_API_URL, { method: "POST", headers: { "Content-Type": "application/json", Authorization: `Bearer ${apiKey}` }, body: JSON.stringify(mail) });
        if (!resp.ok) continue;
      } catch (_) { continue; }
      acct.lastRemind = idx;
      await store.setJSON(key, acct);
      sent++;
    }
    return { sent, checked, idx };
  };
}

export default async function () {
  const { getStore } = await import("@netlify/blobs");
  const result = await createReminder({ getStore, env: (k) => Netlify.env.get(k) })();
  return new Response(JSON.stringify(result), { headers: { "Content-Type": "application/json" } });
}

export const config = { schedule: "0 0 * * *" };
