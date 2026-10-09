// Daily at 14:30 UTC: send the Tapefolio trial reminders that are due. See tapefolio-reminder.mjs.
import { sendDueReminders } from "./tapefolio-reminder.mjs";

export default async function handler() {
  const result = await sendDueReminders();
  console.log("tapefolio-reminder-send", JSON.stringify(result));
  return new Response(JSON.stringify(result), { status: 200, headers: { "Content-Type": "application/json", "Cache-Control": "no-store" } });
}

export const config = { schedule: "30 14 * * *" };
