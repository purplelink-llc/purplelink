"""Step-by-step setup text for each platform. Ben runs these in his own terminal; no agent creates accounts,
developer apps or tokens, and nothing here is ever typed into a form by a script."""

THREADS = """\
Threads (official API). One-time setup, about 15 minutes.

1. The company Threads profile. It must be Purplelink LLC's own profile, not a personal one. Threads profiles are
   normally created by signing in with an Instagram account; use the company's.
2. https://developers.facebook.com/apps  ->  Create app  ->  use case "Access the Threads API".
   (This gives a separate Threads app ID and secret; use those, not the Facebook ones.)
3. App dashboard -> Use cases -> Threads API -> Permissions: add  threads_basic  and  threads_content_publish.
4. App dashboard -> App roles -> Roles -> Add People -> Threads Tester. Enter the company profile's username.
   Then in the Threads app, signed in as the company profile: Settings -> Account -> Website permissions ->
   Invites, and accept. (Testers can use their own profile's permissions without App Review.)
5. App dashboard -> Use cases -> Threads API -> User Token Generator -> generate a token for the company profile.
   Paste it below. If it is a short-lived token (valid 1 hour), also paste the Threads app secret and this tool
   exchanges it for a 60-day token. If it is already long-lived, press Enter at the app secret prompt.
6. Tokens last 60 days. run-due refreshes them when they are 30 days old, and `social.py refresh threads` does it by hand.
Images for Threads are served from https://purplelink.llc/social-media/ (a read-only Netlify Blobs function).
"""

MASTODON = """\
Mastodon (official API). One-time setup, about 10 minutes.

Recommended server: mastodon.social. It is open to registration without approval and its server rules have no
advertising or bot rule. fosstodon.org and mas.to are invitation-only and ban promotion; techhub.social needs approval,
bans direct advertising and requires silent-mode bots. Keep posts informational (releases, guides).

1. Create the account on the server, named for the company (for example @purplelink). Use a company email address.
2. Preferences -> Profile -> tick "This is an automated account" (the bot flag) and fill in the bio with the website.
3. Preferences -> Development -> New application. Name: Purplelink social poster. Scopes: read:accounts,
   write:statuses, write:media (and nothing else). Save, open the application, copy "Your access token".
4. Paste the server URL and the token below.
"""

X = """\
X (Twitter) API v2. DISABLED by default. Posting is pay-per-use: no monthly fee, but you buy credits first.
Read 2026-10-18 from docs.x.com/x-api/getting-started/pricing: a post is $0.015, a post whose text contains a link is
$0.20 (about $6 a month at one link post a day), setting image alt text adds $0.005, identity reads cost fractions
of a cent. There is no tier gate on images. Because every Purplelink post carries a link, plan on about $0.20 each.

1. Sign in to X as the company account (not a personal one). Open https://console.x.com, create a project and an app,
   and buy a small amount of credits. Set a spend cap.
2. App settings -> User authentication settings: enable OAuth 2.0, type "Web App, Automated App or Bot" (confidential) or
   "Native App" (public), callback URL  http://127.0.0.1:8765/callback , website https://purplelink.llc .
3. Copy the OAuth 2.0 Client ID (and the Client Secret if the app is confidential).
4. Paste them below. This tool opens the authorize link, catches the callback on 127.0.0.1:8765, and stores the
   access and refresh tokens (scopes tweet.read tweet.write users.read media.write offline.access) in the keychain.
   Authorize while signed in as the COMPANY account; the identity check refuses anything else.
5. When you accept the cost, set  "x": {"enabled": true, "paid_posting_ok": true}  in ~/.config/purplelink/social.json.
"""

BLUESKY = """\
Bluesky @purplelink.llc uses a saved browser session, no API credential. A browser window opens; log in as the company
account, then press Enter in this terminal. The session is kept in ~/.purplelink/bluesky-profile.
"""

INSTAGRAM = """\
Instagram (official API with Instagram Login, graph.instagram.com). One-time setup, about 15 minutes.
The account is @purplelink.llc (a Business account). Never RubbleFront's: both sit in the same Meta account, so check
which profile Instagram is signed in as at every step. This tool refuses a token for any account named rubblefront.

1. https://developers.facebook.com/apps  ->  Create app  ->  use case "Manage messaging & content on Instagram".
   Make it a new app; leave the Threads app as it is. The app can stay in Development mode: an account that has a
   role on the app can publish without App Review.
2. App dashboard -> Use cases -> Instagram API -> "API setup with Instagram login".
   Permissions: instagram_business_basic and instagram_business_content_publish (the others are not used).
3. "Generate access tokens" -> Add account -> sign in to Instagram as purplelink.llc. If it asks you to accept a
   tester invite: Instagram app, signed in as purplelink.llc -> Settings -> Website permissions -> Apps and websites
   -> Tester invites -> Accept. Then press Generate token next to purplelink.llc and copy it (valid 60 days).
4. Paste the token below and press Enter at the app secret prompt (the dashboard token is already long-lived).
   This tool shows which account it belongs to and pins it only if you type yes. run-due renews it at 30 days.
5. Link in bio (only the Instagram app can set it): Edit profile -> Links -> Add external link ->
   https://purplelink.llc/instagram/?utm_source=instagram&utm_medium=social&utm_campaign=bio
6. Then run: social.py instagram preview   (the dry run: renders the next Reel and image post, posts nothing)
Images are served from https://purplelink.llc/social-media/ (JPEG). Reels are put on the public video bucket named by
media.video.env_file in ~/.config/purplelink/social.json for the minutes Meta needs to fetch them, then deleted.
"""

GUIDES = {"instagram": INSTAGRAM, "threads": THREADS, "mastodon": MASTODON, "x": X, "bluesky": BLUESKY}
