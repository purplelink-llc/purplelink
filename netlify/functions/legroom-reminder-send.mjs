// Daily at 14:10 UTC: send the Legroom trial reminders that are due. See legroom-reminder.mjs.
import { sendDueReminders } from "./legroom-reminder.mjs";

export default async function handler() {
  const result = await sendDueReminders();
  console.log("legroom-reminder-send", JSON.stringify(result));
  return new Response(JSON.stringify(result), { status: 200, headers: { "Content-Type": "application/json", "Cache-Control": "no-store" } });
}

export const config = { schedule: "10 14 * * *" };
