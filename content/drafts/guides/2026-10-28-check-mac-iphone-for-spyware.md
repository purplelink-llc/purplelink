# How to check a Mac or iPhone for spyware

By Benjamin Ampel · October 28, 2026

A clean scan never proves a device is safe. Start with the built-in checks, know what each tool can and cannot see, and call a helpline first if you think you are being targeted.

**Read this first.** A scan that finds nothing does not show that a phone or Mac is safe. Every tool below looks for traces that someone has already published or that a person can see, and those traces can be missing or can expire. If you think you are being targeted right now, for example because you are a journalist, researcher or activist and Apple has warned you, or someone with access to your devices is watching you, contact a helpline before you change anything: [Access Now's Digital Security Helpline](https://www.accessnow.org/help/) or [Amnesty International's Security Lab](https://securitylab.amnesty.org/get-help/). Details are in the last section. Purplelink sells no spyware scanner, and nothing here is a product pitch. Facts and menu paths below were checked against the pages linked, read on October 28, 2026. I did not run any of the tools for this guide.


## The short answer


Do the built-in steps first, because they cost nothing and change what an attacker can do: update the software, read the list of profiles and background items, and run Safety Check on the iPhone. Turn on Lockdown Mode only if your risk is real, because it breaks things. Use Amnesty's Mobile Verification Toolkit only if you are comfortable with the command line, or hand the phone to someone who is. Treat a clean result as "nothing known was found," not as "safe."


## Signs that mean something, and signs that do not


**Worth acting on:**


- A threat notification from Apple. Apple describes these as high-confidence alerts that you have been individually targeted by a mercenary spyware attack, and says it has sent them in more than 150 countries since 2021 ([Apple](https://support.apple.com/en-us/102174)). They arrive as an alert on the Lock Screen, as an email to the addresses on your Apple Account and as a banner after you sign in at account.apple.com.
- A configuration profile or device-management entry you did not install and your employer or school did not install (see below).
- An unfamiliar item in the Mac's login or background list.
- Another person who knows things only your phone or accounts could have told them. That can mean a shared account, a shared location setting or a watched device, and the first two are far more common than spyware.


**Not enough on their own:** a hot phone, fast battery drain, a slow Mac, odd pop-ups or random reboots. Ordinary causes explain all of them, including a new update, a bad app or an aging battery. I have no reliable figure for how often they point to spyware, so I will not give one. If one of them shows up together with a sign from the first list, take the combination seriously.


Two cautions. Apple does not say what triggers a threat notification, so not receiving one tells you little. And Apple says its real notifications never ask you to click a link, open a file, install an app or profile, or enter credentials. A message that does is a scam, not a notification. To check a real one, sign in at account.apple.com and look for the banner there.


## If the person watching you may be someone you live with


If you think a partner or ex has put something on your phone, think about safety before you remove anything. Apple's own Safety Check page says to consider the effect on your safety and privacy before making changes or deleting information ([Apple](https://support.apple.com/guide/personal-safety/how-safety-check-works-ips2aad835e1/web)). Changes to a watched device may be noticed, so talk to a domestic violence advocate first. The Coalition Against Stalkerware advises using a different device, one the person has never had physical access to, when you look for help, because searches on a watched device can be seen. It lists hotlines by country, including the US National Domestic Violence Hotline at +1 800 799 7233 ([stopstalkerware.org](https://stopstalkerware.org/resources/)). If you are in danger, contact local emergency services.


## Step 1: update the software


Apple says keeping software up to date is one of the most important things you can do for the security of its products ([Apple](https://support.apple.com/en-us/118575)). On the iPhone, open Settings, General, Software Update. On the Mac, open System Settings, General, Software Update ([Apple](https://support.apple.com/en-us/102551) gives the same path for macOS). Turn on Automatic Updates in the same place. Updating fixes known holes. It does not remove something that is already there.


## Step 2: read the profiles and management entries


Apple says configuration profiles and management tools may allow access to data or location information on the device ([Apple](https://support.apple.com/guide/personal-safety/review-and-delete-configuration-profiles-ips327569a75/web)).


- **iPhone:** Settings, General, VPN & Device Management. If nothing is listed, no profiles are installed.
- **Mac (macOS 13 or later):** System Settings, General, Device Management. On macOS 12 or earlier it is System Preferences, Profiles; if there is no Profiles pane, no profiles are installed.


A work or school profile is normal. A profile you do not recognize is not, and a VPN or "security" app you did not choose is worth a second look. To remove one on the iPhone, select it, tap Delete Profile and restart; deleting it also deletes the settings, apps and data tied to that profile. If the device belongs to an employer or school, ask the administrator first, because removing a profile can cut off access you need. Do not delete it first if you are worried about who installed it and may need it as evidence; see the section on safety above.


## Step 3: login items and background items on the Mac


Open System Settings, General, Login Items & Extensions. Apple describes this screen as the place to choose which apps, documents, folders and server connections open automatically when you log in, and to allow apps to run in the background ([Apple](https://support.apple.com/guide/mac-help/mh15189/mac)). Read every name. Look up any you do not know by searching the exact name. Turn off or remove what you did not install and do not need.


This list is what macOS shows you on that screen. It is a place to look, not a full scan, so an empty-looking list does not prove the Mac is clean.


## Step 4: Safety Check on the iPhone


Settings, Privacy & Security, Safety Check, on iOS 16 or later with an Apple Account that uses two-factor authentication ([Apple](https://support.apple.com/guide/personal-safety/how-safety-check-works-ips2aad835e1/web)). It lets you review and stop sharing your information with individual people and apps, including location, review the devices signed in to your Apple Account, and reset app privacy permissions. Emergency Reset stops sharing with everyone and everything at once; Manage Sharing & Access goes person by person.


Safety Check is not a scanner. Apple's page does not say it detects spyware. It cannot review or change accounts and passwords that are not Apple's, or social media sharing, and Screen Time restrictions or a management profile can remove some options. For someone worried about a partner or ex, it is often the more useful step, because shared locations and signed-in devices are common.


## Step 5: Lockdown Mode, if your risk is real


Apple designed Lockdown Mode for the very few people who, because of who they are or what they do, may be targeted by sophisticated attacks, and says most people never are. It limits features to shrink what an attack could use ([Apple](https://support.apple.com/en-us/105120)).


- **iPhone:** Settings, Privacy & Security, Lockdown Mode, Turn On Lockdown Mode, then Turn On & Restart.
- **Mac:** System Settings, Privacy & Security, Lockdown Mode, Turn On, then Turn On & Restart.


Apple lists the costs: most message attachment types and link previews are blocked, some websites load slowly or break, incoming FaceTime calls are blocked unless you have called that person in the last 30 days, wired connections to accessories and computers need the device unlocked, and configuration profiles and new device-management enrollment cannot be installed while it is on. Phone calls and plain-text messages still work. It turns a risk down. It does not scan for or remove anything.


## Tools that look for traces


### Mobile Verification Toolkit (MVT)


MVT is the established option. Amnesty International's Security Lab released it in July 2021, alongside the Pegasus Project, and Amnesty and other contributors still maintain it ([MVT documentation](https://docs.mvt.re/en/latest/)). It works on Android and iOS. It does not check a Mac.


Two limits matter. First, Amnesty's own help page calls it a forensic research tool and says it is not intended for end-user self-assessment, and that using it takes forensic basics and command-line skills ([Amnesty Security Lab](https://securitylab.amnesty.org/get-help/)). Second, it matches your data against published indicators of compromise, such as the ones Amnesty releases for Pegasus and Predator, so it can only find what has already been identified ([MVT indicators](https://docs.mvt.re/en/latest/iocs/)).


For an iPhone, the usual path is an encrypted backup made in Finder, because MVT's documentation says encryption allows more accurate detection ([backup guide](https://docs.mvt.re/en/latest/ios/backup/itunes/)). It also says a backup holds only a subset of the files on the device, and that an encrypted backup adds records such as Safari history that an unencrypted one lacks ([methodology](https://docs.mvt.re/en/latest/ios/methodology/)). In outline, from the documentation ([install](https://docs.mvt.re/en/latest/install/), [check a backup](https://docs.mvt.re/en/latest/ios/backup/check/)):

- Install the prerequisites (Python 3.10 or newer, Xcode and Homebrew), then `pipx install mvt`.
- Run `mvt download-iocs` to fetch the public indicator files.
- Decrypt the backup with `mvt-ios decrypt-backup`, then run `mvt-ios check-backup --output` with a folder for the results and the path to the backup.


Matches are saved in files with "detected" in the name. A match means look closer, not "you are infected," and a person who can read the output should do that. If you are not comfortable here, the helplines below will do this for you if you qualify.


### Zero-Breach-Toolkit, a newer option and not the main path


[Zero-Breach-Toolkit](https://github.com/interplains/Zero-Breach-Toolkit) is a free checker for known commercial spyware on Windows, macOS, Linux, Android and iPhone backups. Here is what I could confirm on October 28, 2026:


- The repository was created on October 25, 2026, three days earlier, so it has no track record.
- GitHub lists two contributors; one account made 44 commits and the other one.
- The README says the project is anonymous. The code is Apache-2.0.
- It had about 2,000 stars. Stars show interest, not review.
- The README says it is read-only, makes no network requests while scanning, and only downloads when you ask it to update indicators or collect from Android. It also says this is not an operating-system network sandbox.
- I found no independent review of it. Those safety properties are the author's statements, not something I or anyone I could find has tested.


The README is candid about limits: it checks published indicators only, a clean result is not proof of safety, a match means "look closer," many traces expire within weeks, and it does not replace an expert examination. It also tells people who think they are being targeted right now to get expert help first. I agree with all of that, and I would not make a three-day-old project from an anonymous author the first thing you run on a device you are worried about. If you still want to try it, read the code first or ask someone who can, run it on a copy of the data and not on your only machine, and keep its report out of synced folders as the README advises. I have not run it, so I cannot say whether it works.


## If you may be targeted right now


Contact a helpline before you wipe, reset or update the device, because doing so can destroy the evidence they would look for.


- **Access Now Digital Security Helpline.** It describes itself as free, as working for civil society, journalists, activists and human rights defenders, as staffed around the clock in 10 languages, and as replying to every request within two hours. It first checks that supporting you falls within its mandate, so an individual outside those groups may not qualify ([Access Now](https://www.accessnow.org/help/)).
- **Amnesty International Security Lab.** It supports journalists, activists and civil society organizations at risk from targeted digital attacks and says it investigates phones and laptops for signs of malicious activity. It will not share your forensic information with third parties without your permission, with narrow exceptions it lists, and it may need access to your devices, so read its privacy policy first. It does not promise to confirm targeting or find every attack ([Amnesty Security Lab](https://securitylab.amnesty.org/get-help/)).
- **Apple.** If you received a threat notification, Apple points to the Access Now helpline and suggests turning on Lockdown Mode.


If your worry is a partner or ex and not a state-level attacker, a domestic violence hotline is the better first call, using a device the person cannot access.


## What I did not verify


I did not run MVT or Zero-Breach-Toolkit and did not test any menu path on a device; the paths come from Apple's pages as read on October 28, 2026, and labels shift between macOS and iOS versions. I do not know how likely any given sign is to mean spyware, so I gave no numbers. I could not open the Coalition Against Stalkerware's page on signs and removal, so I rely on Apple's safety wording and the hotline page I could open.


## Frequently asked


### If a scan finds nothing, is my phone safe?


No. These tools match known, published traces. Spyware that is new, was never published or has left no trace in the places a tool can read will not show up. Treat a clean result as one piece of evidence and keep the built-in steps in place.


### Can I scan my Mac with MVT?


No. MVT is for Android and iOS devices. For a Mac, the practical steps are the built-in ones above and, if you are at risk, a helpline. Zero-Breach-Toolkit says it covers macOS, but see the limits above.


### Should I turn on Lockdown Mode just in case?


Only if your work or situation makes a targeted attack plausible. Apple says most people are never targeted that way, and the mode blocks attachments, link previews and some websites, so it is a real cost for little gain in an ordinary case.


### I got an Apple threat notification. What do I do?


Check it is real by signing in at account.apple.com, take it seriously, turn on Lockdown Mode and contact the Access Now helpline, which Apple points to. Do not wipe the device first.


## Sources


- Apple: [threat notifications](https://support.apple.com/en-us/102174), [Lockdown Mode](https://support.apple.com/en-us/105120), [Safety Check](https://support.apple.com/guide/personal-safety/how-safety-check-works-ips2aad835e1/web), [configuration profiles](https://support.apple.com/guide/personal-safety/review-and-delete-configuration-profiles-ips327569a75/web), [Login Items & Extensions](https://support.apple.com/guide/mac-help/mh15189/mac), [updating an iPhone](https://support.apple.com/en-us/118575), [updating a Mac](https://support.apple.com/en-us/102551).
- Amnesty: [Security Lab, get help](https://securitylab.amnesty.org/get-help/) and the [MVT documentation](https://docs.mvt.re/en/latest/).
- [Access Now Digital Security Helpline](https://www.accessnow.org/help/) and [Coalition Against Stalkerware resources](https://stopstalkerware.org/resources/).
- [Zero-Breach-Toolkit README](https://github.com/interplains/Zero-Breach-Toolkit) and its public GitHub repository data, read October 28, 2026.



## Related guides


- [What AI tools leave on your Mac, and what is safe to delete](https://purplelink.llc/guides/what-ai-tools-leave-on-your-mac/): another look at what runs and what is stored on a Mac.
- [Before you paste client notes into ChatGPT or Claude](https://purplelink.llc/guides/before-you-paste-client-notes-into-chatgpt/): privacy settings worth checking on a Mac.
- [All guides](https://purplelink.llc/guides/).

https://purplelink.llc/guides/check-mac-iphone-for-spyware/
