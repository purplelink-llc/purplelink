#!/bin/bash
# Double-click this (or run it) to wire up mail-based stats collection.
# It stops at exactly one prompt: your Google APP PASSWORD.
cd "$(dirname "$0")/.."

ACCOUNT="ben.ampel@gmail.com"
SERVICE="gmail-imap"
PY=/Library/Frameworks/Python.framework/Versions/3.12/bin/python3

echo
echo "======================================================================"
echo " Gmail → photo-licensing analytics setup"
echo "======================================================================"
echo
echo "This stores a Google APP PASSWORD in your macOS Keychain."
echo "It is read at runtime by scripts/mail-collect.py and is never printed,"
echo "logged, or visible to Claude."
echo
echo "  Account : $ACCOUNT"
echo "  Service : $SERVICE"
echo

if security find-generic-password -a "$ACCOUNT" -s "$SERVICE" >/dev/null 2>&1; then
  echo "A Keychain entry already exists. Nothing to add."
  echo "(To replace it: security delete-generic-password -a \"$ACCOUNT\" -s $SERVICE)"
else
  echo "----------------------------------------------------------------------"
  echo " STEP 1 of 2 — get an app password (NOT your Google password)"
  echo "----------------------------------------------------------------------"
  echo "  1. Opening https://myaccount.google.com/apppasswords"
  echo "  2. Create one named e.g. 'purplelink stats'"
  echo "  3. Copy the 16-character password Google shows you"
  echo
  read -r -p "Press Return once you have it copied... " _
  open "https://myaccount.google.com/apppasswords" 2>/dev/null
  echo
  echo "----------------------------------------------------------------------"
  echo " STEP 2 of 2 — paste it at the prompt below"
  echo "----------------------------------------------------------------------"
  echo "The prompt shows nothing as you type or paste. That is expected."
  echo
  security add-generic-password -a "$ACCOUNT" -s "$SERVICE" -w || {
    echo; echo "Keychain entry was not created. Re-run this script to retry."; exit 1; }
  echo
  echo "Stored in Keychain."
fi

echo
echo "======================================================================"
echo " Verifying the connection (read-only, only platform senders)"
echo "======================================================================"
echo
"$PY" scripts/mail-collect.py --discover --days 30

echo
echo "======================================================================"
echo " Done. Tell Claude what appeared above and it will write the parsers."
echo "======================================================================"
echo
read -r -p "Press Return to close... " _
