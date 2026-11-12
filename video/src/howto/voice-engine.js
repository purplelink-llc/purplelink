// The how-to narration engine. Since 2026-11-12 (Ben): every how-to is narrated with VibeVoice (the stored narrator
// voice, cloned with VibeVoice-1.5B) and nothing else; narrate.py never falls back to another voice. For one manual
// run, HOWTO_TTS_ENGINE=kokoro (or "kokoro" in ~/.config/purplelink/howto-voice-engine) narrates with Kokoro instead.
// Only the how-tos read this; every other video calls narrate.py without it.
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

export const SWITCH_FILE = path.join(os.homedir(), ".config", "purplelink", "howto-voice-engine");

export function howtoVoiceEngine(env = process.env, file = SWITCH_FILE) {
  let v = (env.HOWTO_TTS_ENGINE || "").trim().toLowerCase();
  if (!v) {
    try { v = fs.readFileSync(file, "utf8").trim().toLowerCase(); } catch { v = ""; }
  }
  return v === "kokoro" ? "default" : "vibevoice";
}

// env for narrate.py: unchanged unless the switch is on
export function narrateEnv(env = process.env, file = SWITCH_FILE) {
  if (howtoVoiceEngine(env, file) === "vibevoice") return { ...env, TTS_ENGINE: "vibevoice" };
  const off = { ...env };
  if ((off.TTS_ENGINE || "").trim().toLowerCase() === "vibevoice") delete off.TTS_ENGINE; // off means off
  return off;
}
