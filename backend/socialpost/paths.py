"""Private locations. Environment overrides exist so tests never touch the real queue, config or keychain."""
from __future__ import annotations

import os
from pathlib import Path


def home() -> Path:
    return Path(os.environ.get("PL_SOCIAL_HOME") or Path.home() / ".purplelink" / "social")


def queue_dir() -> Path:
    return home() / "queue"


def pause_file() -> Path:
    return home() / "PAUSE"


def lock_file() -> Path:
    return home() / "run-due.lock"


def config_file() -> Path:
    return Path(os.environ.get("PL_SOCIAL_CONFIG") or Path.home() / ".config" / "purplelink" / "social.json")


def log_file() -> Path:
    return Path(os.environ.get("PL_SOCIAL_LOG") or Path.home() / "Library" / "Logs" / "purplelink-social.log")


def outreach_log() -> Path:
    return Path(os.environ.get("PL_OUTREACH_LOG") or
                Path("/Volumes/Extreme SSD/Purplelink LLC/Outreach/OUTREACH-LOG.md"))


def change_logger() -> Path:
    return Path(os.environ.get("PL_LOG_CHANGE") or Path.home() / ".purplelink" / "insights" / "changelog" / "log_change.py")


def bluesky_profile() -> Path:
    return Path(os.environ.get("PL_BLUESKY_PROFILE") or Path.home() / ".purplelink" / "bluesky-profile")


def linkedin_profile() -> Path:
    return Path(os.environ.get("PL_LINKEDIN_PROFILE") or Path.home() / ".purplelink" / "linkedin-profile")
