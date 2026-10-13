# BatteryMeter promo: storyboard

Target: about 41 seconds including the Purplelink bumpers (version 1.1.0 cut; the 1.0 cut was about 35 s). 16:9 for the site and YouTube, 9:16 for Shorts, Reels and TikTok. A silent 8 second hero loop and a poster for the BatteryMeter page. Facts come only from the brief for this cut (verified against the app) and the BatteryMeter README. No statistics, ratings, testimonials or user counts.

Footage: not a screen recording. Every picture is a 2x render of the app's own menu bar item and menu. Two kinds, and the video never blurs them:
- `live-charging.png` is a live reading from the real app on a Mac. The narration says so, and the lower third says "Live reading".
- `sample-draining.png`, `sample-low.png` and `sample-consumers.png` are drawn by the app's snapshot mode with sample values. Each carries "Sample values, not a live reading" inside the image. The narration says "sample", and the lower third says "Sample values" for the whole scene.
`sample-consumers.png` (1600x1108, shown at 0.7) uses invented "Sample App A/B/C" names and has a drawn Quit / Force Quit flyout. `sample-full.png` exists in the app repo but is not used or copied.

Voice: en-GB-SoniaNeural at +4%, as the Panely promo, through edge-tts (`narrate.py`, which points edge-tts at Microsoft's new host since the old one answers 403 from 2026-10-10; `EDGE_TTS_HOST=legacy` reverts). The narration in `storyboards/batterymeter-promo.json` is the short cut; the longer lines below (with red at 10 and nothing leaves your Mac) run about 3 s longer with Sonia and were not restored, so the page transcript matches the JSON. Short declarative sentences, no semicolons, no em-dashes, plain numbers.

## 0. Title card (about 3.5 s)
- **Sees:** app icon, "BatteryMeter", "A free Mac battery meter that shows more."
- **Narration:** "BatteryMeter is a free Mac battery meter that shows more."
- **Connects to next:** the window rises in with the live menu bar item.

## 1. Live reading (about 5.5 s)
- **Sees:** the live image. The camera pushes in on the menu bar item (green battery icon, 61%, up arrow, +8.0 W). A ring on the item.
- **Understands:** the reading is real; the item shows percent, an arrow and watts.
- **On-screen copy:** "Live reading / Percent, arrow, battery watts."
- **Narration:** "This is a real reading from the app. It shows the percent, an arrow, and battery power in watts."

## 2. Draining sample (about 4.5 s)
- **Sees:** the draining sample (64%, down arrow, minus 11.0 W) with the line "Sample values, not a live reading" at the foot of the picture. A ring on the item.
- **On-screen copy:** "Sample values / Down arrow, minus watts."
- **Narration:** "Here is a sample. The arrow points down and the watts go negative while it drains."

## 3. Low sample (about 4.5 s)
- **Sees:** the low sample (16%, orange icon, down arrow, minus 7.2 W), same label in the image. Ring on the icon.
- **On-screen copy:** "Sample values / Orange at 20 percent or below."
- **Narration:** "Another sample. The icon turns orange at 20 percent or below on battery, and red at 10."

## 4. Menu details (about 5 s)
- **Sees:** the live image again, full menu. Rings step down the rows: time to full, battery power with volts and amps, system use, adapter, cycle count.
- **On-screen copy:** "Live reading / Time, volts and amps, adapter, cycles."
- **Narration:** "The menu adds time to full, volts and amps, system use, adapter watts, and cycle count."

## 5. Using the most power (about 8 s)
- **Sees:** `sample-consumers.png`: the menu's "Using the most power" section with five sample rows and an energy score each, and the Quit / Force Quit flyout for the first row. The camera pushes in on the first row; a ring on its energy number, then a ring on the flyout. Lower third "Sample values / Top apps by energy impact. Not a live reading." The image's own label "Sample values, not a live reading" stays visible.
- **Understands:** the menu lists the top five apps by energy impact and offers Quit and Force Quit (Force Quit asks first).
- **Narration:** "It also lists the apps using the most power. Quit one, or force quit it after a prompt." The score is relative, not watts, so the narration never says watts for it.

## 6. Put it where Apple's icon was (about 7 s)
- **Sees:** a drawn card (not a screenshot): heading "Put it where Apple's icon was", step 1 "Hide Apple's icon: System Settings, Control Center, Battery.", step 2 "Hold Command and drag BatteryMeter's item into its place." Each step appears as it is spoken.
- **Narration:** "To use it instead of Apple's icon, hide Apple's in System Settings. Then hold Command and drag BatteryMeter's item into its place."

## 7. End card (about 4.5 s)
- **Sees:** icon, "BatteryMeter", pill "Free for Mac", "purplelink.llc/batterymeter", note "No email. No account. macOS 13 or later, Apple silicon.", then the Purplelink bumper.
- **Narration:** "Free for Apple silicon Macs. Nothing leaves your Mac, and there is no account."

## Claims and where they come from
Free, macOS 13 or later, Apple silicon only, no network connection, no email or account: brief. Menu bar contents, colours and thresholds: brief and the images. Menu rows: shown in `live-charging.png`. Setup steps: brief.

## Hero loop
Silent, 8 s: the live image, a slow push in on the menu bar item with a ring, back out. It is the live reading, and the hero is not labelled because it carries no text. The page that hosts it should say it is a real reading.
