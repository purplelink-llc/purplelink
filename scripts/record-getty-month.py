#!/usr/bin/env python3
"""Kept so older notes and the monthly reminder still work: same as record-photo-month.py getty <month> <amount>."""
import runpy, sys
from pathlib import Path

sys.argv = [sys.argv[0], "getty"] + sys.argv[1:]
runpy.run_path(str(Path(__file__).with_name("record-photo-month.py")), run_name="__main__")
