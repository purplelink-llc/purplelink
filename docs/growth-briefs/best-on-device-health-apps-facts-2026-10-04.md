# Fact table: best health tracking apps that keep your data on your phone

Checked 2026-10-04 for `site/guides/best-on-device-health-apps/index.html`. Method: `competitive-landscape-research`.
Tiers: 1 = vendor's own site, vendor privacy policy, Apple/Google first-party page, or the App Store listing (store data
read through Apple's iTunes lookup JSON plus the rendered apps.apple.com page, which carries the privacy label and the
in-app purchase list); 2 = named independent source; 3 = aggregator or search summary (never stated flatly in the article).

Reading notes:

- WebFetch returns a model-written summary of a page. Rows marked "fetch summary" were read that way and the article words
  them conservatively. Pages WebFetch could not render were read with curl and a browser user agent ("curl").
- HTTP 403 to every automated fetch: whoop.com (membership and privacy pages), support.whoop.com (CSS error page),
  withings.com and support.withings.com, help.yazio.com, Garmin's privacy pages (JavaScript-only; text not served).
  Rows that depend on them are tier 3 or rest on the App Store label alone, and the article hedges them.
- Prices are App Store (US storefront) prices read 2026-10-04. Most subscription apps list the same product at several
  price points (regional or legacy tiers, intro offers). The article quotes a figure only when the product is named
  unambiguously, and otherwise says "several tiers are listed".
- "Data Used to Track You", "Data Linked to You", "Data Not Linked to You" and "Data Not Collected" are Apple's own
  headings for what the developer declared. They are self-reported (Apple's developer page says so) and I did not audit them.
- All ratings and release dates come from the iTunes lookup JSON on 2026-10-04.

## Brief and old-guide claims corrected

| Claim in old guide or brief | Finding | Source |
|---|---|---|
| Haea "expected launch 2026", "zero network calls", "possible crash-report payload (anonymized)" | Not released; no App Store listing exists (iTunes search for "Haea", "Purplelink" and developer search return only GlobePin from Purplelink LLC). The network-behavior claims cannot be verified for an unreleased app, so they were removed | iTunes search API, 2026-10-04 |
| Product page "no cloud sync" vs blog "Cross-device sync for Haea uses iCloud via HealthKit" | Our own pages differ. The guide quotes the product page and notes that the blog describes sync through Apple's iCloud, not a Purplelink server | `site/haea/index.html`; `site/blog/why-haea-is-on-device/index.html` |
| Bearable "Premium ~$5/mo", data on Bearable's servers "by default" | Vendor pricing page: $6.99 monthly, $34.99 yearly. Privacy policy: data is stored on the device and, with an account, on Bearable servers (Firestore, Frankfurt) for backup and cross-device use. Label lists Health & Fitness as linked to you and Contact Info and Identifiers as used to track you | bearable.app/pricing, bearable.app/privacy-policy, App Store id1482581097 |
| Welltory "Premium ~$10/mo" | Listing shows 1-year Premium at $99.99 and $119.99, lifetime $299.99 and several other products | App Store id1074367771 |
| "Many users will get 80% of the value" from Apple Health alone | No source. Removed | n/a |
| Fitbit | The Fitbit app became the Google Health app on 2026-05-19; App Store name is "Google Health (Fitbit)" | blog.google; App Store id462638897 |
| Brief names "Carbon Diet Coach" | App Store name is "Carbon - Macro Coach & Tracker" (Reform, LLC). A different app, "Carbon Nutrition Tracker" (Carbon Nutrition Inc., id6766758668, 0 ratings), also exists | iTunes search |

## Apple Health, Fitness, Journal

| Fact | Value | Tier | Source | Checked | Conflicts |
|---|---|---|---|---|---|
| Price | Free; built in (listing id1242545199, version 2.5.6, updated 2026-09-14) | 1 | App Store lookup | 2026-10-04 | none |
| Privacy label (Health) | Data Not Linked to You: Health & Fitness, Location, Search History, Identifiers, Usage Data, Sensitive Info, Diagnostics, Other Data | 1 | apps.apple.com/us/app/id1242545199 | 2026-10-04 | a long list of categories under "not linked"; listed as declared |
| iCloud | "Your health data stays up to date across all your devices automatically using iCloud, where it is encrypted while in transit and on Apple servers" | 1 | App Store description | 2026-10-04 | none |
| End-to-end | "If you are using iOS 12 or later and turn on two-factor authentication, Apple will not be able to read your health and activity data synced to iCloud" | 1 | apple.com/legal/privacy/data/en/health-app/ (fetch summary) | 2026-10-04 | none |
| Locked device | Health data encrypted and inaccessible by default when a passcode, Touch ID or Face ID is set (Medical ID excepted) | 1 | same | 2026-10-04 | none |
| Third-party access | "Users are asked to grant access when apps request access to health data", separate read and write access per data type; "If granted permission to read data, apps can read data written by all sources." Apps must conform to restrictions on how data is used | 1 | support.apple.com/guide/security/protecting-access-to-users-health-data-sec88be9900f/web (fetch summary) | 2026-10-04 | the page does not say whether an app may transmit data off the device; the article states this as its own reading, labeled as such |
| Health sync switch | Apple documents Health sync under Settings, your name, iCloud (search snippet of support.apple.com guide; page itself returned only the table of contents to the fetcher) | 3 | web search snippet | 2026-10-04 | hedged in article ("a Health sync switch in iCloud settings") |
| Apple Fitness label | Data Linked to You: Health & Fitness, Purchases, Financial Info, Identifiers, Usage Data. Data Not Linked to You: Health & Fitness, Diagnostics. Listing mentions Fitness+ as a paid subscription | 1 | App Store id1208224953 | 2026-10-04 | Fitness+ price not read; none given |
| Journal | Free; iOS 17.2+; label Data Not Linked to You: Identifiers, Usage Data; entries synced between devices through iCloud; suggestions "created using on-device intelligence" | 1 | App Store id6447391597 | 2026-10-04 | none |
| 2026 changes | Apple announced a redesigned Health app (Insights tab, Longevity tab with a "Health Age" metric, movement evaluations, lab panels at $119 through Quest, perimenopause support) for "later 2026", US English first; watchOS 27 on 2026-09-14; Apple Watch Series 12 and Ultra 4 with a Readiness score. Press release mentions no subscription. The movement-evaluation feature "runs entirely on device"; the release does not detail privacy for the rest | 1 | apple.com/newsroom/2026/09/apple-advances-health-and-fitness-capabilities-using-apple-intelligence/ (fetch summary) | 2026-10-04 | gadget sites call it "Health+"; Apple's release does not use that name. Article does not use it |

## Gentler Streak

| Fact | Value | Tier | Source | Checked | Conflicts |
|---|---|---|---|---|---|
| Price | Free; Premium monthly $8.99, yearly $39.99, lifetime plans at several prices ($59.99 to $179.99 listed), family plans | 1 | App Store id1576857102 | 2026-10-04 | vendor page gave no price |
| Platforms | iPhone iOS 16+, iPad, Apple Watch watchOS 9+ | 1 | listing | 2026-10-04 | none |
| Privacy label | Data Not Linked to You: Purchases, Location, Identifiers, Usage Data, Diagnostics, Other Data | 1 | listing | 2026-10-04 | listing text says health data "stays on-device via Apple HealthKit, with no external processing"; label lists identifiers and usage data |
| On-device | Vendor: "All analysis happens on your iPhone. ... No user accounts. No servers." Policy: "Your Health Data will be accessed locally through Apple Health and will not be stored or cached by the app. Your Health Data is processed locally and will not be sent to any server." | 1 | gentlerstories.com/gentlerstreak/, .../privacypolicy (fetch summary) | 2026-10-04 | policy also lists Sentry (crash), Mixpanel (interaction analytics) and Adjust (promotional analysis) SDKs, "We will not use your Health Data for marketing or advertising purposes"; photo timestamps saved "in your private iCloud" |
| Ratings | 4.71 from 8,821 | 1 | lookup | 2026-10-04 | none |

## Athlytic

| Fact | Value | Tier | Source | Checked | Conflicts |
|---|---|---|---|---|---|
| Price | Free to download; Pro $4.99 monthly or $29.99 yearly; one-week free trial (site says 7-day) | 1 | App Store id1543571755; athlyticapp.com | 2026-10-04 | none; site says "No lifetime unlocks" |
| Privacy label | Data Not Collected | 1 | listing | 2026-10-04 | none |
| On-device | "Everything is read and processed on your device through Apple Health." "No accounts, no tracking." Listing: "The developer does not collect any data from this app." | 1 | athlyticapp.com; listing | 2026-10-04 | vendor's `/privacy-policy` URL (linked from the listing) returned 404; `/privacy/` returns 200 with a short page |
| Watch needed | "An Apple Watch is needed for most features, since HRV and resting heart rate come from the watch." Some third-party wearables that write HRV to Apple Health also work | 1 | listing | 2026-10-04 | none |
| Platforms | iPhone iOS 17+, iPad, Apple Vision, Apple Watch watchOS 10.6+ | 1 | listing | 2026-10-04 | none |
| Ratings | 4.79 from 11,069 | 1 | lookup | 2026-10-04 | none |

## AutoSleep

| Fact | Value | Tier | Source | Checked | Conflicts |
|---|---|---|---|---|---|
| Price | $8.99, no in-app purchases, no subscription | 1 | App Store id1164801111 | 2026-10-04 | none |
| Privacy label | Data Not Collected | 1 | listing | 2026-10-04 | none |
| On-device | "AutoSleep has no user analytics tracking. No advertising plugins. No 3rd party code. No data upload to any server." / "This data is not transmitted anywhere by the AutoSleep app. It remains on your iPhone for your personal use." | 1 | listing; autosleepapp.tantsissa.com/privacy (fetch summary) | 2026-10-04 | policy does not mention iCloud or accounts; article says "no account is described" |
| Platforms | iPhone iOS 15+, Apple Watch watchOS 9+; "Requires Apple Watch running WatchOS 4 or higher" | 1 | listing | 2026-10-04 | none |
| Ratings | 4.71 from 61,741 | 1 | lookup | 2026-10-04 | none |

## Bevel

| Fact | Value | Tier | Source | Checked | Conflicts |
|---|---|---|---|---|---|
| Price | Free; Bevel Pro monthly $14.99, annual $99.99; credit packs $4.99 to $49.99 | 1 | App Store id6456176249 | 2026-10-04 | bevel.health shows no prices |
| Privacy label | Data Used to Track You: Identifiers. Data Linked to You: Location, Contact Info, Identifiers, Usage Data. Data Not Linked to You: Health & Fitness, Diagnostics | 1 | listing | 2026-10-04 | search summary said "coarse location"; the label itself just says Location |
| Storage | Policy: Apple Health data "is stored on your device unless you enable Bevel Intelligence"; with Bevel Intelligence on, "certain Apple Health data may be transmitted to and stored on our servers"; health data from other integrations (Oura, Garmin, Google Health) "is stored on our servers for the duration of your account"; LLM providers named (Google, Anthropic, OpenAI, Baseten) | 1 | bevel.health/privacy-policy (curl text and fetch summary) | 2026-10-04 | none |
| Account | Policy describes data given "when you register or update your account" | 1 | same | 2026-10-04 | no explicit "required" sentence; article says "its policy describes registering an account" |
| Ads | "We never use Health Information for advertising or marketing purposes"; "We do not share your Health Information with advertising networks, data brokers, or social media platforms" | 1 | same | 2026-10-04 | label still lists Identifiers as used to track |
| Platforms | iPhone iOS 18+, Apple Watch watchOS 10+; works with Apple Watch, Oura, Garmin, Amazfit, Google Health | 1 | listing; bevel.health | 2026-10-04 | none |
| Ratings | 4.85 from 16,769 | 1 | lookup | 2026-10-04 | none |

## Daylio and Streaks

| Fact | Value | Tier | Source | Checked | Conflicts |
|---|---|---|---|---|---|
| Daylio price | Free; Premium listed at several prices ($4.99, $17.99, $23.99, $35.99, $59.99) | 1 | App Store id1194023242 | 2026-10-04 | tiers not reconciled; article says "several tiers" |
| Daylio label | Data Not Linked to You: Purchases, Usage Data, Diagnostics | 1 | listing | 2026-10-04 | none |
| Daylio storage | Policy: "Your data are stored only locally on your device and all calculations are done on your device as well"; "The Application does not provide an option to create an account"; backups optional to iCloud Drive (iOS); Google Analytics for Firebase and Crashlytics collect anonymized usage data | 1 | daylio.net/faq/privacy-policy/ (fetch summary); listing | 2026-10-04 | none |
| Streaks price | $5.99, no in-app purchases listed | 1 | App Store id963034692 | 2026-10-04 | none |
| Streaks label | Data Not Linked to You: Diagnostics | 1 | listing | 2026-10-04 | none |
| Streaks storage | "Everything is stored securely on your device"; task history may sync via iCloud; "Streaks does not transmit any data read from the Health app across the Internet to either our own or any third-party server"; aggregated anonymous data goes to a crash reporting service | 1 | streaks.app/privacy.html (fetch summary) | 2026-10-04 | policy does not mention accounts |
| Streaks role | A habit tracker that can complete tasks from Health data (water, caffeine); iPhone iOS 17.6+, iPad, Mac, Vision, Watch | 1 | listing | 2026-10-04 | not a mood tracker; the article calls it a habit tracker |

## Oura

| Fact | Value | Tier | Source | Checked | Conflicts |
|---|---|---|---|---|---|
| Price | Membership $5.99 a month or $69.99 a year (US), first month free for new members; ring sold separately, ring price not read | 1 | ouraring.com/membership (fetch summary) | 2026-10-04 | App Store IAP list empty |
| Privacy label | Data Linked to You: Health & Fitness, Location, Contact Info, Identifiers, Diagnostics. Data Not Linked to You: Usage Data | 1 | App Store id1043837948 | 2026-10-04 | none |
| Account and storage | Policy: account created; mentions "cloud service providers"; "Oura does not sell or rent your personal information"; "We do not sell or share your personal data for cross-context behavioral advertising"; uses cookies on its website for ad audiences; integrations with Apple HealthKit, Google Health Connect and LLM providers with consent | 1 | ouraring.com/privacy-policy (fetch summary) | 2026-10-04 | policy summary did not state where data is stored; article says cloud via "cloud service providers" and the label |
| Platforms | iPhone iOS 16+, Vision, Watch | 1 | listing | 2026-10-04 | none |

## WHOOP

| Fact | Value | Tier | Source | Checked | Conflicts |
|---|---|---|---|---|---|
| Needs | "The WHOOP app requires a WHOOP wearable"; free 1-month trial of wearable and app | 1 | App Store id933944389 (listing text) | 2026-10-04 | none |
| Privacy label | Data Linked to You: Health & Fitness, Location, Contact Info, User Content, Identifiers, Usage Data, Sensitive Info, Diagnostics, Other Data. Data Not Linked to You: Diagnostics. Listing's purposes include Developer's Advertising or Marketing and Analytics | 1 | listing | 2026-10-04 | policy page returned 403; article says the policy was not read |
| Price | Reported as One $199, Peak $239, Life $359 a year (price trackers and a 2026 Engadget piece in the search results) | 3 | web search | 2026-10-04 | whoop.com and support.whoop.com unreachable (403 and CSS error). Article says "reported as" and gives no flat price |
| Platforms | iPhone iOS 17+, iPad | 1 | listing | 2026-10-04 | none |

## MacroFactor

| Fact | Value | Tier | Source | Checked | Conflicts |
|---|---|---|---|---|---|
| Price | Free to download; subscription only. Listing: monthly $11.99; annual $59.99 and $71.99 both listed; semiannual $47.99; bundle $89.99 | 1 | App Store id1553503471 | 2026-10-04 | vendor home page showed no price |
| Privacy label | Data Linked to You: Health & Fitness, Purchases, Contact Info, User Content, Identifiers, Usage Data, Diagnostics | 1 | listing | 2026-10-04 | none |
| Storage and account | Policy: user data stored with Google LLC (Firebase Cloud Firestore) in the USA; an account is required; Firebase analytics and Crashlytics; RevenueCat for subscriptions; "We do not sell your Personal Data to third parties"; "we do not share your data for cross-behavioral advertising purposes" | 1 | macrofactor.com/privacy/ (fetch summary) | 2026-10-04 | listing links privacy.macrofactorapp.com |
| Platforms | iPhone iOS 15+, iPad, Mac macOS 12+, Vision, Watch. MacroFactor Workouts is a separate app (id6737156524) | 1 | listing | 2026-10-04 | none |
| Ratings | 4.84 from 22,842 | 1 | lookup | 2026-10-04 | none |

## Cronometer

| Fact | Value | Tier | Source | Checked | Conflicts |
|---|---|---|---|---|---|
| Price | Free Basic plan; Gold $10.99 monthly, $59.99 yearly | 1 | cronometer.com/gold/ (fetch summary); App Store id1145935738 | 2026-10-04 | none |
| Privacy label | Data Used to Track You: Contact Info, Identifiers, Usage Data. Data Linked to You: Health & Fitness, Contact Info, User Content, Identifiers, Usage Data, Sensitive Info. Data Not Linked to You: Search History, Identifiers, Usage Data, Diagnostics | 1 | listing | 2026-10-04 | none |
| Storage and ads | Policy: data kept "in the cloud and on secure, HIPAA compliant servers in the United States"; account needed for most services; for free users discloses limited information to advertising service providers; "We do not provide personal health information, or PHI, to Advertisers"; does not respond to Do Not Track | 1 | cronometer.com/privacy/ (fetch summary) | 2026-10-04 | none |
| Platforms | iPhone iOS 15.5+, iPad, Mac macOS 13+, Vision, Watch | 1 | listing | 2026-10-04 | none |

## MyFitnessPal

| Fact | Value | Tier | Source | Checked | Conflicts |
|---|---|---|---|---|---|
| Price | Free; Premium $19.99 monthly, $79.99 yearly (US); listing shows other tiers ($9.99, $49.99) | 1 | myfitnesspal.com/premium (fetch summary); App Store id341232718 | 2026-10-04 | listing's legacy tiers differ |
| Privacy label | Data Used to Track You: Identifiers, Usage Data. Data Linked to You: Health & Fitness, Contact Info, User Content, Identifiers, Usage Data, Diagnostics. Data Not Linked to You: Diagnostics | 1 | listing | 2026-10-04 | none |
| Ads and account | Policy: discloses personal information to "marketing and advertising partners, including social media platforms, third-party advertising networks"; says cookies for targeted advertising "may constitute 'sales' or 'sharing'" under privacy laws; opt-out via Privacy Center | 1 | myfitnesspal.com/privacy-policy (fetch summary) | 2026-10-04 | account requirement inferred (policy talks of users/accounts; app needs sign-in); article says "an account" because the label lists Contact Info linked |
| Platforms | iPhone iOS 18+, iPad, Watch | 1 | listing | 2026-10-04 | none |

## Welltory

| Fact | Value | Tier | Source | Checked | Conflicts |
|---|---|---|---|---|---|
| Price | Free to download; listing shows 1-year Premium at $99.99 and $119.99, lifetime $299.99, other add-ons | 1 | App Store id1074367771 | 2026-10-04 | old guide said about $10/mo |
| Privacy label | Data Used to Track You: Location, Contact Info. Data Not Linked to You: Health & Fitness, Location, Contact Info, User Content, Identifiers, Usage Data, Sensitive Info, Diagnostics | 1 | listing | 2026-10-04 | none |
| Storage, account, ads | Policy: backend in US cloud data centers; account needed (email and password at registration); for US residents it discloses hashed email, online identifiers, device information and internet activity to advertising partners including Meta, Google and TikTok, and says "We do not create, upload, share, or use advertising audiences based on health data, wellness metrics, symptoms, diagnoses, stress, sleep, HRV" | 1 | welltory.com/privacy/ (fetch summary) | 2026-10-04 | old guide said "sent to Welltory's servers for analysis": consistent |
| Platforms | iPhone iOS 16+, Vision, Watch | 1 | listing | 2026-10-04 | none |

## Exist

| Fact | Value | Tier | Source | Checked | Conflicts |
|---|---|---|---|---|---|
| Price | Vendor: $6.99 a month, $62.90 a year, 30-day trial. Listing text: "7.99 USD"; IAP list: $8.49 monthly | 1 | exist.io (fetch summary); App Store id986201088 | 2026-10-04 | three different monthly figures. Article quotes $6.99 on the vendor page and says the App Store shows more |
| Needs | "THIS APP REQUIRES A PAID ACCOUNT"; 30-day trial | 1 | listing | 2026-10-04 | none |
| Privacy label | Data Linked to You: Health & Fitness, Location, User Content, Usage Data | 1 | listing | 2026-10-04 | none |
| Storage | Policy: account needed; hosting "outside the United States"; removed Google Analytics in September 2024; uses Sentry and Campaign Monitor; "We make money selling Exist subscriptions, not your data" | 1 | exist.io/privacy, exist.io (fetch summary) | 2026-10-04 | none |
| Ratings | 4.02 from 47 | 1 | lookup | 2026-10-04 | none |

## Shorter entries

| App | Fact | Tier | Source | Conflicts |
|---|---|---|---|---|
| Strava | Free tier; subscription $79.99 a year, 30-day trial (vendor page); label: Data Used to Track You: Purchases, Identifiers; linked Health & Fitness, Location, Contact Info, Contacts, User Content, Search History, etc.; policy: account, data stored in the US, "If we collect health information from these integrations (such as heart rate), we will not sell or use it for advertising"; may disclose to advertising networks to promote its services | 1 | strava.com/subscribe, strava.com/legal/privacy (fetch summaries); App Store id426826309 | listing also shows $11.99 monthly and Runna bundles |
| Lose It! | Free; Premium at many prices ($9.99 to $79.99, lifetime $49.99 and $59.99 listed); label: Used to Track You: Contact Info, Identifiers, Usage Data; linked incl. Health & Fitness, Sensitive Info; policy (fitnowinc.com/privacy/loseit/, curl): servers in the US, may share data with advertisers, "we may sell or share the personal data you provide to us (excluding data that originates from Google Fit and Health Connect)" for interest-based ads, opt-out available | 1 | App Store id297368629; fitnowinc.com | www.loseit.com/privacy refused WebFetch; redirects to fitnowinc.com |
| Carbon | App Store name "Carbon - Macro Coach & Tracker" (Reform, LLC); monthly $11.99, six-month $59.99, yearly $99.99; label: linked Purchases, Contact Info, User Content, Identifiers, Sensitive Info, Diagnostics; policy: "in order to use our application you must create an account and start a subscription"; "We never sell your Personal Data for money"; data primarily in the US (AWS); discloses some categories to advertising partners "so that we can reach you across the web" | 1 | App Store id1437820611; joincarbon.com/privacy-policy/ (fetch summary) | none |
| Yazio | App Store name "AI Calorie Tracker by Yazio" (YAZIO GmbH); free with Pro at many prices; label: Used to Track You: Identifiers; linked Health & Fitness, Purchases, Contact Info, User Content, Identifiers; policy (yazio.com/en/privacy, curl): account sign-up (email, Apple or Google), Google Ads remarketing and conversion tracking, Facebook social plug-in | 1 | App Store id946099227; yazio.com/en/privacy | help.yazio.com 403 (the URL the listing links) |
| Withings | Free app; needs Withings devices; Withings+ listed $9.99 monthly, $99.99 annual; label: linked Health & Fitness, Location, Contact Info, User Content, Identifiers, Usage Data, Diagnostics | 1 (label, price) | App Store id542701020 | withings.com policy and support pages 403; account and cloud storage reported (third-party search results) so article hedges |
| Garmin Connect | Free; label: Data Linked to You: Health & Fitness, Contact Info, Contacts, User Content, Identifiers; Not Linked: Location, Usage Data, Diagnostics; Connect+ $6.99 monthly or $69.99 yearly, "All existing features and data in Garmin Connect will remain free" | 1 (label; Connect+ from Garmin press release) | App Store id583446403; garmin.com/en-US/newsroom (fetch summary) | Garmin privacy pages are JavaScript-only (text not served); account requirement not read, article says label lists contact info and identifiers as linked |
| Google Health (Fitbit) | Fitbit app became Google Health on 2026-05-19; requires a Google Account; Google says it "committed to not using Fitbit user health and wellness data for Google Ads"; label: broad Data Linked to You list incl. Health & Fitness, Purchases, Location, Contacts; Premium listed at $9.99 monthly and $79.99 annual on App Store | 1 | blog.google/.../google-health-app/ (fetch summary); App Store id462638897 | search results report Premium repriced to $99 a year; Google's post gives no price. Article quotes the listing figures and says reports differ |
| Zepp | Free; label: linked Identifiers; not linked Health & Fitness, Location, User Content, Usage Data, Diagnostics; policy: account required; data stored in the US, Germany or mainland China depending on region; "We do not sell any personal information" | 1 | App Store id1127269366; policy (fetch summary) | none |
| Sleep Cycle | Free; Premium at many prices; label: Used to Track You: Identifiers; linked Health & Fitness, Purchases, Location, Contact Info, Identifiers, Usage Data, Diagnostics; policy: "personal data related to your health will only be stored locally on your device" by default, cloud backup optional on Google Cloud; an account is needed (name, email, password) | 1 | App Store id320606217; sleepcycle.com/privacy-policy/ (fetch summary) | label lists health data as linked while policy says local by default: article reports both |
| RISE | Free to download, but "A Paid Subscription (or free trial) is required to access the content of the app"; Sleep Improvement Membership listed from $9.99 to $69.99; label: Used to Track You: Identifiers; linked Health & Fitness, Financial Info, Contact Info, Identifiers, Usage Data, Diagnostics; policy: US cloud storage, account (email and password), may share de-identified data with sleep health partners, ad cookies | 1 | App Store id1453884781; risescience.com/privacy (fetch summary) | none |
| Strong | Free; Strong PRO $4.99 monthly, $29.99 yearly (listing text), "Strong Accounts are Free Forever" and optional; Strong Cloud sync; label: all Data Linked to You: Health & Fitness, Purchases, Contact Info, Identifiers, Diagnostics, Other Data | 1 | App Store id464254577; strong.app (fetch summary) | iubenda policy page says "no longer active", so no policy statements |
| Hevy | Free; Hevy Pro listed $2.99 or $3.99 monthly, $23.99 yearly, $74.99 lifetime; label: Linked Purchases, Contact Info, Contacts, Usage Data; Not linked Identifiers, Sensitive Info, Diagnostics; policy (iubenda): account registration (email, name, password), Amplitude and Google Analytics, Adjust for advertising | 1 | App Store id1458862350; iubenda.com/privacy-policy/75379905 (fetch summary) | none |
| Gyroscope | Free to start; "Gyroscope requires an account to sync and view your data"; Gyroscope One at several prices ($9 to $299); label: linked Health & Fitness, Purchases, Location, Contact Info, User Content, Identifiers, Sensitive Info; policy: US servers, AWS, "We never sell your data, and AI providers never train on it"; 50 ratings | 1 | App Store id1104085053; gyrosco.pe/privacy/ (fetch summary) | none |
| Ultrahuman | App free; needs the ring; label: linked Location, Contact Info, User Content, Identifiers, Usage Data; policy: account required, storage on AWS, Snowflake and MongoDB Atlas, "We will never sell your data to third-parties", shares with advertising partners "to market our own Products and Services" | 1 | App Store id1491286709; ultrahuman.com/privacyPolicy (fetch summary) | none |
| Bearable | Free tier; Premium $6.99 monthly, $34.99 yearly; data on device and, with an account, on Bearable's servers (EU); label: Used to Track You: Contact Info, Identifiers; linked Health & Fitness, Location, Contact Info, User Content, Identifiers, Usage Data; policy lists Firebase, Segment, Moosend, Zendesk, Google Analytics, Mixpanel, RevenueCat and Facebook SDK | 1 | bearable.app/pricing, bearable.app/privacy-policy (fetch summaries); App Store id1482581097 | none |
| Notion | "All Customer Data is stored in the cloud"; account required | 1 | notion.com/help/privacy (fetch summary) | no price quoted; article does not give one |
| Spreadsheet | No source needed beyond the general statement that a spreadsheet file you keep yourself has no vendor account; Numbers' storage options were not read | n/a | n/a | article keeps it generic |

## Apple's privacy-label definitions

| Fact | Value | Tier | Source | Checked |
|---|---|---|---|---|
| Collect | "Collect" refers to transmitting data off the device in a way that allows the developer and/or third-party partners to access it for a period longer than what is necessary to service the transmitted request in real time. Data processed only on device is not collected | 1 | developer.apple.com/app-store/app-privacy-details/ (fetch summary) | 2026-10-04 |
| Tracking | Linking data from the app about a user or device with third-party data for targeted advertising or advertising measurement, or sharing it with a data broker | 1 | same | 2026-10-04 |
| Linked | Connected to identity via an account, device identifiers or other details | 1 | same | 2026-10-04 |
| Not linked | Direct identifiers stripped before collection, no re-linking | 1 | same | 2026-10-04 |
| Self-reported | "You're responsible for keeping your responses accurate and up to date" | 1 | same | 2026-10-04 |

## Haea (Purplelink, own product, not released)

| Fact | Value | Tier | Source | Checked | Conflicts |
|---|---|---|---|---|---|
| Status | "In development · 2026"; "Coming to the App Store"; waitlist form; JSON-LD offers use availability PreOrder | 1 | `site/haea/index.html` | 2026-10-04 | FAQ says "expected to launch in 2026" |
| App Store | No listing. iTunes search "Haea" returns unrelated apps (HAEA App by Hereditary Angioedema Association, Hawa); developer/term search "Purplelink" returns GlobePin only | 1 | itunes.apple.com/search | 2026-10-04 | none |
| Planned free | Complete logging (food, weight, water, exercise, mood), HealthKit import, 7-day and 30-day trend charts, activity timeline, optional 8am daily briefing | 1 | product page | 2026-10-04 | page's FAQ says "core health logging and charts" |
| Planned Premium | $1.99 a month or $14.99 a year: Energy Balance and TDEE, Circadian Rhythm Intelligence, Running Analytics (FIT export, route maps, power curves, training zones), "Advanced ML models" (dose-response, Granger causality, adaptation tracking, Kalman-filtered recovery state), "Biological metrics" (biological age estimate, VO2 max, DFA-alpha1 HRV, circadian age) | 1 | product page | 2026-10-04 | page FAQ lists only Kalman, Granger and biological age under Premium |
| Privacy design | "No cloud sync. No third-party SDKs. No ads. All analytics run on-device using GRDB.sqlite local storage" | 1 | product page | 2026-10-04 | blog "Why we built Haea on-device" says cross-device sync "uses iCloud via HealthKit - Apple's own infrastructure, not ours". Not the same statement as "no cloud sync". Article quotes the page and notes the blog |
| Platform | iOS 17+ | 1 | product page JSON-LD | 2026-10-04 | none |
| Validation | Biological age, causal and ML claims are the developer's description. No validation study is cited on the page | 1 | product page | 2026-10-04 | none |
| Open graph image | `site/assets/og/haea.png` exists (1200 by 630 per the og tags); old guide and product page already use it | 1 | repo | 2026-10-04 | none |

## Label purposes (read from the App Store privacy detail data, 2026-10-04)

The privacy detail page lists each declared purpose with its data categories. Which categories sit under "Developer's
Advertising or Marketing" or "Third-Party Advertising", as declared:

| App | Declared advertising-related purposes | Tier | Notes |
|---|---|---|---|
| WHOOP | Developer's Advertising or Marketing: Health & Fitness, Location, Contact Info, Usage Data | 1 | article says Health & Fitness appears with that purpose |
| Strava | Third-Party Advertising: Identifiers, Usage Data. Developer's Advertising or Marketing: Health & Fitness, Purchases, Location, Contact Info, Identifiers, Usage Data | 1 | same |
| Cronometer | Developer's Advertising or Marketing: Health & Fitness, Contact Info, Identifiers, Sensitive Info. Third-Party Advertising: Identifiers, Usage Data | 1 | same |
| MyFitnessPal, Lose It!, Yazio | Identifiers, Usage Data, Contact Info or Purchases only (no Health & Fitness) | 1 | |
| Gentler Streak | Developer's Advertising or Marketing: Location (only one label type, Not Linked) | 1 | article mentions it |
| Bevel, Sleep Cycle, Welltory, Bearable, Ultrahuman, Gyroscope, RISE, Google Health, Fitness | identifiers, contact info, usage data, purchases or location only | 1 | |
| Apple Health, Journal, Athlytic, AutoSleep, Oura, Carbon, Withings, Streaks, Daylio, Exist, Zepp, Garmin, Strong, Hevy | none declared | 1 | |

Caveat: for apps with several label headings, the detail page repeats the purposes under each heading, so the table
cannot say which heading (linked or tracking) a purpose belongs to; the article only says the category appears "with that
purpose" in the label.

## Added after the main pass

| App | Fact | Tier | Source | Checked |
|---|---|---|---|---|
| MacroFactor | Listing: "Download to start your 7-day trial of this premium, ad-free macro tracker app" | 1 | App Store id1553503471 description | 2026-10-04 |
| Athlytic | Listing describes Recovery, Exertion (scored 0 to 10), Target Exertion, "Athlytic Age" (the vendor's own fitness number), sleep metrics and a 24/7 monitor | 1 | App Store id1543571755 description | 2026-10-04 |
| Gentler Streak | Listing describes readiness summary, 14-night sleep trends, daily steps and movement, cycle-phase suggestions | 1 | App Store id1576857102 description | 2026-10-04 |
| Bevel | Listing describes Recovery, Sleep, Strain, Nutrition and Stress scores, 6 million+ food database, glucose tracking, strength trainer with 700+ exercises | 1 | App Store id6456176249 description | 2026-10-04 |
