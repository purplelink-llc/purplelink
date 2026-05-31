# Haea — launch kit (template, fill in at launch)

Haea is the privacy-positioning anchor of the studio. Use the launch to make the architectural privacy claim verifiable and quotable.

## Pre-launch (1 week before)

- [ ] Update `Organization.sameAs` + `SoftwareApplication.downloadUrl` on `/haea/`
- [ ] Update Haea OG card with the App Store badge variant
- [ ] Publish a technical privacy post to `/blog/why-haea-is-on-device/` (already exists) — refresh dateModified
- [ ] Submit to PrivacyGuides.org tool list (form on their site)
- [ ] Submit to Awesome-Privacy on GitHub (PR to the list)

## Show HN copy

**Title:**
> Show HN: Haea – iOS health analytics that doesn't send your data anywhere

**Body:**

> Hi HN — Ben from Purplelink LLC.
>
> Haea is the on-device iOS health app I built because everything else made a trade-off I didn't want: either Apple Health's baseline + no analytics, or rich analytics + my health data on someone's server. So I built the no-trade-off version.
>
> Reads from Apple Health (HealthKit). All analysis runs locally: Kalman-filtered weight smoothing, TDEE calculation, circadian rhythm modeling, Granger causality between sleep / nutrition / activity / mood, a one-line morning summary. Zero network calls related to your health data.
>
> Verifiable claims (not promised, verifiable): open the Network tab in iOS proxy tools, fire up Haea, observe nothing leaving the device. The only network calls are Apple's IAP and a single crash-report endpoint with no health data.
>
> No third-party SDKs. No analytics tier. No "we anonymize and aggregate" — there is no aggregation, no aggregator.
>
> Comparison vs Apple Health / Bearable / Welltory: https://purplelink.llc/guides/best-on-device-health-apps
> Architecture write-up: https://purplelink.llc/blog/why-haea-is-on-device/
> App Store: [URL]
>
> Free tier; premium is $1.99/mo or $14.99/year. Asking $14.99/year because it's enough to keep development sustainable without VC and without ads.
>
> Happy to answer questions on the architecture or the privacy posture.

## r/iOSProgramming + r/Swift

Lead with the architecture, not the marketing:

> [OC] Built a no-network-call iOS health app in SwiftUI — architecture write-up

Body: discuss the on-device ML pipeline (Kalman filter implementation, why you avoided Core ML for some pieces, etc.). Link to the privacy comparison guide as a secondary reference.

## r/PrivacyGuides + r/PrivacyToolsIO

Focus on the verifiability:

> Built a privacy-first iOS health app. Network tab is the spec.

Body: explain why "trust us" privacy claims are weaker than architectural claims. Show how to verify yourself by inspecting network traffic. Link to the comparison guide.

## LinkedIn

> Haea ships today.
>
> An iOS health analytics app that processes everything on your iPhone. Sleep, nutrition, biometrics, exercise — analyzed locally with on-device ML (Kalman filtering, TDEE, circadian modeling, Granger causality). Zero network calls related to your health data.
>
> Most health apps make a trade-off: either Apple's baseline analytics or your data on someone's server. Haea is the no-trade-off option.
>
> App Store: [URL]
> Why on-device: purplelink.llc/blog/why-haea-is-on-device
> Comparison: purplelink.llc/guides/best-on-device-health-apps
>
> Free tier; Premium $1.99/mo or $14.99/year.
>
> #PrivacyByDesign #iOS #HealthTech

## Bluesky

> Haea shipped.
>
> iOS health analytics that runs entirely on your phone. No network calls related to your health data. Verifiable, not promised.
>
> Free + Premium ($1.99/mo). App Store: [URL]
>
> Comparison vs Apple Health/Bearable/Welltory: purplelink.llc/guides/best-on-device-health-apps

## Newsletter pitches

Same shape as GlobePin's. Targets:

- iOS Dev Weekly
- MacStories
- Indie Hackers
- **6'5″ + Privacy** (privacy newsletter)
- **The Markup** (if there's a relevant ongoing investigation about health-app data)
- **MIT Tech Review's The Algorithm** (long shot, but the privacy-as-architecture angle is publishable)

## What to NOT do

- Don't claim "HIPAA-compliant" unless lawyers have signed off. "HIPAA-ready architecture" is the right line if true.
- Don't overstate the ML — Granger causality is genuinely there, "AI-powered" framing is the wrong register for this audience.
- Don't downplay Apple Health. Position Haea as a layer on top, not a replacement.
