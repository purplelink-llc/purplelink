#!/usr/bin/env python3
"""Unified social posting for the Purplelink LLC company accounts. See docs/social-posting.md.

  python3 backend/scripts/social.py new|validate|preview|approve|cancel|post|run-due|status|whoami|setup|refresh|pause|resume

Queue, config and secrets are private and live outside the repo. Exit codes: 0 ok, 1 nothing, 2 session expired,
3 failed, 4 refused (the signed-in account is not the expected company account).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from socialpost.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
