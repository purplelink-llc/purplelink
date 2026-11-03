// Daily at 14:30 UTC: send the Lenscrib trial reminders that are due. See lenscrib-reminder.mjs.
import { sendDueReminders } from "./lenscrib-reminder.mjs";

export default async function handler() {
  const result = await sendDueReminders();
  console.log("lenscrib-reminder-send", JSON.stringify(result));
  return new Response(JSON.stringify(result), { status: 200, headers: { "Content-Type": "application/json", "Cache-Control": "no-store" } });
}

export const config = { schedule: "30 14 * * *" };
