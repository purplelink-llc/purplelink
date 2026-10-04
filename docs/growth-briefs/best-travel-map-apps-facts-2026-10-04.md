# Fact table: best travel map and country-tracking apps for iPhone

Checked 2026-10-04 for `site/guides/best-travel-map-apps-for-iphone/index.html`. Method: `competitive-landscape-research`.
Tiers: 1 = vendor's own site or App Store listing (store data read through Apple's iTunes lookup JSON plus the
rendered apps.apple.com page, which carries the privacy label and in-app purchase list); 2 = named independent source;
3 = aggregator or search summary (never stated flatly in the article).

Reading notes:

- WebFetch returns a model-written summary of a page. Rows marked "fetch summary" were read that way and the article words
  them conservatively. Apple, Google and vendor pages that WebFetch could not render were read with curl and a browser
  user agent (those rows say "curl").
- `support.polarsteps.com`, `my.flightradar24.com`, `flightradar24.com/blog` returned HTTP 403 (a Cloudflare challenge) to
  every automated fetch. `beenapp.com` refused the connection. Rows that depend on them are tier 3 and hedged.
- Prices are App Store (US storefront) prices read on 2026-10-04. Several apps list the same product at multiple price
  points (regional tiers or old tiers); the article quotes the listed figure only when the product is named
  unambiguously and otherwise says "several tiers are listed".
- "Data Used to Track You" and the other privacy-label headings are Apple's own wording for what the developer declared.

## GlobePin (Purplelink, own product)

| Fact | Value | Tier | Source | Checked | Conflicts |
|---|---|---|---|---|---|
| Release | First released 2026-09-03; current version 1.2, updated 2026-09-28 | 1 | App Store lookup id6762313540 | 2026-10-04 | `site/globepin/index.html` and its JSON-LD still say version 1.0 |
| Price | Free, with one in-app purchase: GlobePin Pro (Lifetime) $14.99 | 1 | apps.apple.com/us/app/globepin/id6762313540 | 2026-10-04 | site page says "free", "nothing", "no subscription", no mention of Pro. `site/privacy/index.html` says Pro is "a one-time purchase or monthly subscription"; the listing says one-time, not a subscription |
| Ads | Free version shows a small banner on some screens and a short ad before Year in Review, Map Collage and Travel Reel export; adds a "Made with GlobePin" mark to shared cards and reels; Pro removes all of it | 1 | listing description | 2026-10-04 | not on the site page |
| Platforms | iPhone and iPad, iOS and iPadOS 17.0+; the compatibility list also shows Mac (macOS 14+, Apple M1 or later) and Apple Vision (visionOS 1.0+) | 1 | listing compatibility section | 2026-10-04 | site says iPhone and iPad, iOS 17+ |
| Privacy label | Data Used to Track You: Identifiers, Usage Data. Data Not Linked to You: Diagnostics, Identifiers, Usage Data | 1 | listing App Privacy section | 2026-10-04 | listing text says "No accounts, no tracking"; the label discloses tracking data. Privacy page attributes the data to Google AdMob on the free tier |
| Data location | "Everything stays on your device and in your own private iCloud. No accounts" | 1 | listing description | 2026-10-04 | consistent with site |
| What is tracked | Pins on a 3D globe and world map; flights, road trips, cruises, train journeys; boarding pass scan; stats (countries, continents, nights abroad, furthest point, total miles); photo postcards; Travel Goals; journal and time capsules; trip planning; Discover Nearby; Travel Reels; Year in Review; share cards and map collages; widgets; Spotlight; CSV import and export; iCloud sync | 1 | listing description | 2026-10-04 | site page lists a shorter feature set (no Look Around, Reels, planning, widgets, CSV) |
| Automatic location tracking | Not described in the listing. Privacy page says location is used to set "home" and calculate distances, on-device | 1 | listing; `site/privacy/index.html` | 2026-10-04 | none |
| Social features | None described in the listing; site page says "no social network required" | 1 | listing; site page | 2026-10-04 | none |
| Ratings | 5.0 from 2 ratings | 1 | lookup JSON | 2026-10-04 | none |
| Open graph image | `site/assets/og/globepin.png` exists | 1 | repo | 2026-10-04 | none |

## Polarsteps

| Fact | Value | Tier | Source | Checked | Conflicts |
|---|---|---|---|---|---|
| Free vs paid | Free to download; Polarsteps Plus subscription listed at $9.99 monthly and $34.99 yearly (US App Store) | 1 | apps.apple.com id947925763 | 2026-10-04 | polarsteps.com/plus shows EUR 8.99 monthly and EUR 29.99 yearly, "prices may vary by region"; article quotes both and says prices vary |
| What Plus adds | 3D maps, extra map styles, Play mode, up to 10 Travel Buddies (vs 5 free), step stats such as elevation, 20% off Travel Books on the yearly plan; "you can still plan, track, share and relive your trips without paying" | 1 | polarsteps.com/plus (fetch summary) | 2026-10-04 | none |
| Tracking | "Automatic route tracking"; works offline; "typically less than 4% battery per day while tracking" | 1 | listing; polarsteps.com (fetch summary) | 2026-10-04 | existing guide says the same in other words |
| Add a past trip by hand | Yes, steps joined by straight lines | 3 | search excerpt of support.polarsteps.com (403 to fetch) | 2026-10-04 | not stated flatly; article says "reported as" |
| Account requirement | Not confirmed on a tier-1 page (support pages 403). Privacy label lists Contact Info as linked to you; `globepin-vs-polarsteps` says an account is required. Article says "not confirmed" | 3 | label; prior guide | 2026-10-04 | none |
| Sharing and privacy | Choose who sees a trip: everyone, followers only, or you only (listing); "Only you, Friends & Family, The entire world" (site) | 1 | listing; polarsteps.com | 2026-10-04 | none |
| Travel Books | Printed hardback book from a trip | 1 | listing; polarsteps.com | 2026-10-04 | none |
| Privacy label | All data linked to you: Contact Info, Contacts, Diagnostics, Financial Info, Identifiers, Location, Purchases, Search History, Usage Data, User Content. No "used to track you" section | 1 | listing App Privacy | 2026-10-04 | none |
| Size of user base | "22M+ travelers" | 1 | polarsteps.com | 2026-10-04 | `globepin-vs-polarsteps` says "~10M+ installs globally as of 2025": stale, different metric |
| Countries and distance stats | "Travel stats: ... total of countries visited, distances covered" | 1 | listing | 2026-10-04 | none |
| Flights | Transport mode can be set to plane; no flight log described | 1 | listing | 2026-10-04 | none |

## Visited (Arriving In High Heels)

| Fact | Value | Tier | Source | Checked | Conflicts |
|---|---|---|---|---|---|
| Price | Free; in-app purchases listed include Visited Pro $59.99, Unlock Cities $9.99, Unlock Regions $3.99, Remove Ads $3.99, Unlock Itineraries $7.99, plus monthly $9.99 and yearly $34.99 | 1 | apps.apple.com id846983349 | 2026-10-04 | visitedapp.com: free tier has country maps, travel lists, stats and friend comparison; premium adds city and regional maps, 175+ lists, itineraries, ad removal |
| What is tracked | Countries, states, regions and cities; 150+ lists (listing) or 175+ (site); travel goals; journal notes by country; poster printing | 1 | listing; visitedapp.com | 2026-10-04 | 150 vs 175: listing and site disagree, article says "over 150" |
| Account and sync | "Signing up ensures your data is securely saved on our servers and can be accessed through any of your devices" | 1 | visitedapp.com (fetch summary) | 2026-10-04 | `globepin-vs-polarsteps` says account "Optional": roughly consistent, sync needs one |
| Location tracking | "We do not track your location, unlike other travel apps"; no GPS tracking | 1 | visitedapp.com (fetch summary) | 2026-10-04 | none |
| Platforms | iPhone (iOS 17.6+), also Android | 1 | listing; visitedapp.com | 2026-10-04 | none |
| Flights | None described | 1 | listing; visitedapp.com | 2026-10-04 | none |
| Privacy label | Linked to you: Contact Info, Identifiers, Usage Data. Not linked: Diagnostics, Usage Data | 1 | listing | 2026-10-04 | none |
| Prior guide claim | "doesn't track specific places within a country, no map detail" | 1 | listing | 2026-10-04 | contradicted: listing says cities, states and regional maps for 20+ countries (several paid) |

## been (VINCI APPS LTD)

| Fact | Value | Tier | Source | Checked | Conflicts |
|---|---|---|---|---|---|
| Price | Free; in-app purchases listed: Premium Features $2.29, been premium yearly $19.99, been premium weekly $4.99 | 1 | apps.apple.com id680148327 | 2026-10-04 | beenapp.com refused the connection |
| What is tracked | Countries and US states, optionally when visited; list with a ratio per continent, world map, 3D globe; compare with friends who have the app | 1 | listing | 2026-10-04 | none |
| Premium adds | Regions in 25+ countries, cities and airports, more 3D globe filters, a chronologic map, local profiles, share timeline as video | 1 | listing | 2026-10-04 | none |
| Privacy label | Used to track: Usage Data. Linked: Identifiers. Not linked: Diagnostics, Usage Data | 1 | listing | 2026-10-04 | none |
| Name collision | Search for "been" returns several apps by other developers (Pham Van Huy, Prostachki Ltd, Stanislav Kozlovskii and others); the long-running one is by VINCI APPS LTD, first released 2013-07-30 | 1 | iTunes search | 2026-10-04 | none |

## Pin Traveler (Pin Traveler LLC)

| Fact | Value | Tier | Source | Checked | Conflicts |
|---|---|---|---|---|---|
| Price | Free with unlimited pins and trips; Premium adds unlimited photo uploads, custom pins and colors, unlimited saved places. Weekly, monthly, yearly and lifetime tiers are listed at many price points ($2.49 to $44.99) | 1 | apps.apple.com id1335839375 | 2026-10-04 | pintravelerapp.com quotes "$2.49 premium monthly" in a testimonial; App Store lists several tiers. Article gives no single price |
| Features | Pin any city, country or US state; color-filled map; stats such as farthest pin; trips with dates, spots, photos; sync across devices; friends, follows and shared trips; web map link; "go private anytime" | 1 | listing | 2026-10-04 | none |
| Account | Required to create an online map ("sign up in a single click") | 1 | pintravelerapp.com (fetch summary) | 2026-10-04 | none |
| Platforms | iPhone (iOS 17.6+), Android; web | 1 | listing; pintravelerapp.com | 2026-10-04 | none |
| Privacy label | Used to track: Usage Data. Linked: Contact Info, Diagnostics, Identifiers, Purchases, Usage Data, User Content. Not linked: Diagnostics, Location, Usage Data | 1 | listing | 2026-10-04 | none |
| Sibling | Travel Pins: Track Where Been, same developer, v1.5.3, free with Remove Ads $4.99; "pin anywhere on earth" | 1 | apps.apple.com id1464618728 | 2026-10-04 | none |

## Flighty (Flighty LLC)

| Fact | Value | Tier | Source | Checked | Conflicts |
|---|---|---|---|---|---|
| Price | Free; Pro is free on your first flight; pricing page shows Pro at $59.99 billed annually; App Store lists monthly $9.99, annual $59.99, lifetime $299, family tiers | 1 | flightyapp.com/pricing (curl); apps.apple.com id1358823008 | 2026-10-04 | pricing page also shows "$4.99 per month" in a weekly toggle; article says "from $59.99 a year" |
| Free tier | No ads, unlimited flights, live data, personal flight log and map, personal all-time and annual stats, iCloud backup and sync; "historical flight input and import limited to past 365 days" | 1 | listing | 2026-10-04 | none |
| Pro | Delay alerts and predictions, live activities, unlimited past flight lookup, unlimited bulk import | 1 | listing | 2026-10-04 | none |
| Passport | "auto-create your personal flight map"; total mileage, where you went, compare stats with friends | 1 | listing; flightyapp.com/passport (curl) | 2026-10-04 | none |
| Import | From myFlightradar24, App In The Air, OpenFlights.org, FlightMemory, Logmyflight, JetLovers (listing); calendar, TripIt, email (site) | 1 | listing; flightyapp.com | 2026-10-04 | none |
| Platforms | iPhone (iOS 18.0+), iPad, Mac, Apple Watch; Android not mentioned | 1 | listing; flightyapp.com | 2026-10-04 | none |
| Account | "No account required" | 1 | listing | 2026-10-04 | flightyapp.com summary was silent; listing is explicit |
| Privacy label | Linked to you: Contact Info, Identifiers, Usage Data | 1 | listing | 2026-10-04 | none |
| Scope | Flights only; no places or countries beyond airports and flight stats | 1 | listing | 2026-10-04 | none |

## YourFlights (Tobias Hann)

| Fact | Value | Tier | Source | Checked | Conflicts |
|---|---|---|---|---|---|
| Price | Free; in-app purchases listed include Premium (Monthly) $3.99, Premium (Annual) $24.99 and capped flight packs up to Platinum ULTD $29.99 | 1 | apps.apple.com id1212158909 | 2026-10-04 | none |
| Features | Log flights by number, route or boarding pass scan; 3D globe; stats on distance, time, countries, airports, airlines, aircraft; ratings, notes, photos; badges; follow friends, activity feed, likes and comments | 1 | listing | 2026-10-04 | none |
| Privacy label | Linked to you: Contact Info, Identifiers, Other, User Content. Not linked: Diagnostics, Identifiers, Purchases, Usage Data | 1 | listing | 2026-10-04 | none |
| Ratings | 4.4 from 48 ratings | 1 | lookup JSON | 2026-10-04 | none |

## Wanderlog

| Fact | Value | Tier | Source | Checked | Conflicts |
|---|---|---|---|---|---|
| Price | Free with optional Pro subscription; listed tiers include $5.99 and $16.99 monthly and annual plans from $31.99 to $59.99 | 1 | apps.apple.com id1476732439 | 2026-10-04 | wanderlog.com summary: "annual subscription (no monthly option)" came from user feedback, not stated by the vendor; not used |
| What it is | Itineraries, maps of places to visit, reservations import by email or Gmail, budget and expense split, offline access, group collaboration | 1 | listing | 2026-10-04 | none |
| Platforms | iPhone, Android, web | 1 | listing; wanderlog.com (fetch summary) | 2026-10-04 | none |
| Account | Required | 1 | wanderlog.com (fetch summary) | 2026-10-04 | none |
| Visited-places map | Not described | 1 | listing | 2026-10-04 | none |
| Privacy label | Linked: Contact Info, Diagnostics, Identifiers, Usage Data, User Content. Not linked: Contacts, Location | 1 | listing | 2026-10-04 | none |

## Stippl (Stippl B.V.)

| Fact | Value | Tier | Source | Checked | Conflicts |
|---|---|---|---|---|---|
| Price | Free; Stippl Pro listed at $3.99, $24.99 and $34.99 | 1 | apps.apple.com id6443617088 | 2026-10-04 | stippl.io: free tier, Pro features not detailed |
| Scratch map | "Pin every country you've visited", stats, world map; country maps for USA, Germany, Japan, Canada, Australia, UK are marked Pro | 1 | listing | 2026-10-04 | stippl.io summary did not mention it |
| Also | Route and day planner, budget, journal, reels, photobooks, eSIM, AI planner (Pro) | 1 | listing | 2026-10-04 | none |
| Account | Required to save personal itineraries | 1 | stippl.io (fetch summary) | 2026-10-04 | none |
| Privacy label | Used to track: Contact Info. Linked: Contact Info, Identifiers, Purchases, Usage Data, User Content. Not linked: Diagnostics, Location | 1 | listing | 2026-10-04 | none |

## Journi (Journi GmbH)

| Fact | Value | Tier | Source | Checked | Conflicts |
|---|---|---|---|---|---|
| App | "Journi Blog - Travel tracker", App Store category Photo & Video; timelines with photos, notes, maps, stamps; photo books; privacy levels Just for you, Secret, Only on request, Public; offline; Dropbox and Google Drive backup | 1 | apps.apple.com id884030844 | 2026-10-04 | journiapp.com homepage now leads with photo books and does not describe the app as a tracker |
| Price | Free; Premium Membership at several tiers; the listing text quotes EUR 9.99 monthly, EUR 43.99 six months, EUR 53.99 yearly; photo books from EUR 22.99 | 1 | listing | 2026-10-04 | App Store IAP list shows USD tiers $4.99 to $53.99; article says "several tiers" |
| Premium adds | Cloud save, weather and flight info on the timeline, all stickers | 1 | listing | 2026-10-04 | none |
| Privacy label | Linked: Contact Info, Identifiers, Purchases, Usage Data, User Content. Not linked: Diagnostics | 1 | listing | 2026-10-04 | none |
| Name collision | Other apps named "Journi" from different developers (Raijin Ai, Seweryn Lasko, others) | 1 | iTunes search | 2026-10-04 | none |

## Apple Maps Visited Places and Apple Photos map

| Fact | Value | Tier | Source | Checked | Conflicts |
|---|---|---|---|---|---|
| Visited Places | In Maps: Places, then Visited Places; "end-to-end encrypted, can't be read by Apple, and appear on all your synced devices"; you turn it on first; keep for a period you choose or Forever; Clear History; not available in all countries or regions | 1 | support.apple.com iPhone User Guide "View Visited Places in Maps on iPhone" (curl) | 2026-10-04 | none |
| Needs | Search by name, category, address, notes; filter by date, category, city. Needs Location Services access (the guide points to "Allow Maps to use your location") | 1 | same | 2026-10-04 | none |
| Photos map | Photos, Library, Show Map; "Only pictures and videos that have embedded location information (GPS data) are included" | 1 | support.apple.com "Browse photos and videos by location on iPhone" (curl) | 2026-10-04 | none |

## Google Maps Timeline

| Fact | Value | Tier | Source | Checked | Conflicts |
|---|---|---|---|---|---|
| Default | "Timeline is off by default for your Google Account"; turning it on on iPhone requires Location Services set to Always | 1 | support.google.com/maps/answer/6258979 (fetch summary, iOS variant) | 2026-10-04 | none |
| Export | Saved as location-history.json through the Files app on iPhone or iPad | 1 | same | 2026-10-04 | none |
| Backup and retention | Backup stores an encrypted copy on Google's servers; auto-delete after 3, 18 or 36 months | 1 | same | 2026-10-04 | none |
| Moved to device | Timeline now stored on the device rather than the cloud; Takeout export no longer useful | 3 | search summaries (mileagewise.com and others) | 2026-10-04 | Google's page confirms on-device export and optional encrypted backup; "moved to device" wording not read from Google directly, so article says "Google's help page describes export from the phone and an optional encrypted backup" |

## Scratch-off maps

| Fact | Value | Tier | Source | Checked | Conflicts |
|---|---|---|---|---|---|
| Brand | Scratch Map, "conceived by Luckies in 2009", sold through suck.uk.com; luckiesoflondon.co.uk redirects there | 1 | suck.uk.com (fetch summary) | 2026-10-04 | none |
| Prices | Reported as about $12 for A3 poster versions to about $25 for large; retailer prices differ | 3 | retailer listings in search results | 2026-10-04 | not stated in article beyond "a few tens of dollars" |
| Visited app poster | Visited offers a professionally printed scratch-style map poster | 1 | Visited listing | 2026-10-04 | none |

## OpenFlights, myFlightradar24 (FlightDiary), App in the Air

| Fact | Value | Tier | Source | Checked | Conflicts |
|---|---|---|---|---|---|
| OpenFlights | Free web service for flight logging, maps, stats and sharing; account required; import and export; open source; "requires JavaScript"; news line dated September 2026 | 1 | openflights.org (WebFetch and curl) | 2026-10-04 | none |
| FlightDiary | flightdiary.net returns 301 to my.flightradar24.com | 1 | WebFetch redirect notice | 2026-10-04 | none |
| myFlightradar24 contents | Flight diary with CSV import; free or paid not confirmed | 3 | search excerpts; my.flightradar24.com returned 403 | 2026-10-04 | article says the page would not load for me and gives no price |
| myFlightradar24 import | Flighty names it as an import source | 1 | Flighty listing | 2026-10-04 | none |
| App in the Air | Closed: removed from stores 2024-09-19, support ended 2024-10-19; pointed users to TripIt Pro and Flighty | 2 | heise.de report; consistent with Flighty and myFlights import notes; not found in App Store search | 2026-10-04 | search aggregators agree on the dates |

## Smaller apps (listing-only rows)

| App | Facts used | Tier | Source id | Checked |
|---|---|---|---|---|
| TripIt | Itinerary organizer; forward bookings to plans@tripit.com; TripIt Pro $48.99 a year (App Store), $49 a year (site); listing does not describe a lifetime map or stats; privacy label links Contact Info, Identifiers, Location, Usage Data, User Content | 1 | id311035142; tripit.com/web/pro | 2026-10-04 |
| FindPenguins | Automatic route tracking "battery-friendly and offline", 3D flyover videos, travel book, no in-app purchases listed, free per site; account required; iOS and Android | 1 | id721334305; findpenguins.com | 2026-10-04 |
| Skratch (Zero Dawn Ltd) | Scratch map of countries, cities, states, regions; bucket list; eSIM; in-app purchases Power Ups Bundle $11.99, Cities & Regions $9.99, Map Themes $4.99; label lists tracking (Identifiers, Usage Data) | 1 | id1457438876 | 2026-10-04 |
| Places Been | Tag cities, UNESCO sites, national parks, 8,000+ airports and cruise ports; offline city database; many paid add-ons ($1.99 to $19.99 Traveler Edition); label: tracking Identifiers | 1 | id1480355919 | 2026-10-04 |
| Mark O'Travel | Countries and regions, Travelers' Century Club list, World Heritage, iCloud and Dropbox sync, Traveler Pro $9.99 and $0.99 map packs; label: Diagnostics only, not linked | 1 | id866778149 | 2026-10-04 |
| myFlights - Flight Diary (Timo Rieskamp) | Flight log, .pkpass and PDF import, stats, CO2, data stored locally, optional account backup, imports from Flightradar24 and App in the Air; Pro $1.99 monthly, $17.99 yearly, $39.99 lifetime | 1 | id6468884991 | 2026-10-04 |
| Tripsy | Itinerary planner, iOS 18+, Pro tiers; label: nothing linked or used to track | 1 | id1429967544 | 2026-10-04 |
| Stampie | Passport-style country tracker, 1,000+ stamps, Pro $6.99 monthly, $34.99 yearly, $79.99; v1 released 2025-09-26 | 1 | id6752670353 | 2026-10-04 |
| Swarm | Foursquare check-in app and location history; label links Location | 1 | id870161082 | 2026-10-04 |

## Not used, and why

- Countries Been (Daniel Knoblauch, id1165849344): live, 29 ratings at 3.7; not described in the article.
- Several look-alike "Countries Visited Map", "been", "Journi" apps by solo developers with under 10 ratings: not described.
- Notion and spreadsheets: no tier-1 claim needed; the article describes the DIY approach without product claims.
- Google Sheets geo chart help page returned 404; no claim about it is made.

## Discrepancies in Purplelink's own claims (found while checking)

1. `site/globepin/index.html` (visible text and JSON-LD) says version 1.0, free, "Nothing", no subscription, no ads. The App Store listing says version 1.2 (updated 2026-09-28), free with GlobePin Pro (Lifetime) $14.99, ads in the free version, and a much larger feature set (Look Around, Travel Reels, Year in Review, journal, trip planner, Discover Nearby, widgets, CSV import and export, Spotlight).
2. `site/privacy/index.html` says GlobePin Pro is "a one-time purchase or monthly subscription". The listing says one-time and "not a subscription".
3. The listing text says "No accounts, no tracking" but its App Privacy label lists Identifiers and Usage Data under "Data Used to Track You". The privacy page attributes the data to Google AdMob on the free tier.
4. `site/guides/globepin-vs-polarsteps/index.html` says GlobePin "is free" with no mention of ads or Pro; Polarsteps "~10M+ installs globally as of 2025" (vendor now says 22M+ travelers); Visited "doesn't track specific places within a country, no map detail" (listing shows cities, states and regional maps, several paid); Visited "Account: Optional" (sync needs signing up).
5. The new article is written from the App Store listing, not the site page.
