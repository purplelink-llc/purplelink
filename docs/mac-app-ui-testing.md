# Mac app UI testing checklist

Every live UI test of a Purplelink Mac app (release check, bug repro, hand test) runs in the background through
agent-desktop. Ben uses the Mac while tests run, so a test must never take focus, move the cursor or send global keys.
Approved by Ben on 2026-11-10, including pid-targeted typing into a background app. Trial results (BatteryMeter
menu-bar, Vitae windowed, 5/5 each): side-session note `agent-desktop-trial-2026-11-10.md`.

## Tool
- agent-desktop 1.2.0 (vercel-labs), a CLI that reads and acts on the macOS accessibility tree. No network use found.
- Installed outside the repo at `~/.purplelink/agent-desktop/pkg` (npm package copied with scripts disabled; binary
  sha256 `dec75e0b...f738e9`). State dir `~/.purplelink/agent-desktop/home`, mode 700.
- Always call it through `scripts/ui-test/ad.sh`. The wrapper refuses `--headed` and every command that can take focus,
  move the real cursor or windows, send global keys, quit apps, or touch the clipboard or notifications.
- Needs Accessibility (and Screen Recording for screenshots). Inside the Claude app it inherits the app's grants; a
  launchd job or CI runner needs its own grant, which only Ben can give.

## Checklist (every app test)
1. **Throwaway copy.** Copy the build into the scratchpad, set a `.handtest` bundle id, turn Sparkle off
   (`SUEnableAutomaticChecks` false, delete `SUFeedURL`), remove app extensions that carry real ids (widgets),
   `codesign --force --deep -s -`. Never test the installed app.
2. **Isolated data.** An ad-hoc signed copy loses its sandbox, so it can read the real app's data folder. Use the
   app's test mode (Vitae: Debug build with `-VitaeUITesting -VitaeUITestFixtures`), or check in the source that the
   copy cannot open the real store before launching it. If neither is possible, do not run the copy.
3. **App Nap off for the copy only.** `defaults write <handtest id> NSAppSleepDisabled -bool YES`. Without it,
   background reads time out or return partial trees after about a minute.
4. **Launch in the background.** `open -g -n <copy>.app --args ...`; record the pid. Never `launch` or `focus-window`.
5. **Act headless.**
   - Read with `snapshot`. Use `-i` to find actions, and a full read with `--max-depth 25` (no `-i`) to check text.
   - Buttons and menu items: `click` (AX press).
   - Text: `focus` the field, then `type`. `type` delivers to the app's pid, not the global keyboard, so the app does
     not need to be frontmost. `set-value` does not reach SwiftUI bindings; don't use it for SwiftUI fields.
   - Snapshot right before each action. Refs go stale when the app rebuilds its UI. Retry once only when the error
     says `not_delivered`. A delivered toggle reports `retry: unsafe`, and retrying would flip it back.
   - After a view switch the window id can mismatch (title changed). Re-read once.
6. **Guards in the run script.**
   - Abort if `lsappinfo front` changes from its value at the start.
   - Abort if the copy's pid dies (`kill -0`).
   - Stop at the first crash. Never relaunch a crashing copy.
7. **Verify against real state.** Clicks often report `delivered_unverified`. Check stored state (`defaults read`, files
   in the test folder) or a fresh read, not the action's own result.
8. **Time it.** Record per-step ms over 5 runs. Typical figures: read 300 to 500 ms, click 80 to 250 ms, focus or type
   about 100 ms.
9. **Clean up.**
   - Quit the copy by pid.
   - Run `defaults delete <handtest id>` and remove `~/Library/Preferences/<handtest id>.plist`.
   - Remove any temp folders the copy made, by literal path.
   - `lsregister -u <copy>`.
   - Check that Saved Application State and `~/Library/Logs/DiagnosticReports` have nothing for the copy.

## Still needs physical input
Global hotkeys, drag, hover, double-click and anything else that needs the real mouse or keyboard. Those stay opt-in
and run only when Ben is away (idle gate, as in Panely's `scripts/live/run.sh`). They also need the screen-unlocked and
frontmost checks.

## Not yet tried
Sheets, menus inside windows, Release builds (most have no test mode, see step 2).
