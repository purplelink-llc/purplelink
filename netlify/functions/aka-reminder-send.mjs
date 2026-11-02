// Daily at 14:50 UTC: send the AKA trial reminders that are due. See aka-reminder.mjs.
import { sendDueReminders } from "./aka-reminder.mjs";

export default async function handler() {
  const result = await sendDueReminders();
  console.log("aka-reminder-send", JSON.stringify(result));
  return new Response(JSON.stringify(result), { status: 200, headers: { "Content-Type": "application/json", "Cache-Control": "no-store" } });
}

export const config = { schedule: "50 14 * * *" };
