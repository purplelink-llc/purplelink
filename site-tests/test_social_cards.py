import importlib.util
import re
import struct
import sys
import types
import unittest
from common import ROOT, SITE, ORIGIN, meta

MAX_BYTES = 250 * 1024


def jpeg_size(path):
    data = path.read_bytes()
    if data[:2] != b"\xff\xd8":
        raise ValueError("not a JPEG")
    i = 2
    while i < len(data) - 9:
        if data[i] != 0xFF:
            i += 1
            continue
        marker = data[i + 1]
        if marker in (0xFF, 0x01) or 0xD0 <= marker <= 0xD9:
            i += 2 if marker != 0xFF else 1
            continue
        (length,) = struct.unpack(">H", data[i + 2:i + 4])
        if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
            h, w = struct.unpack(">HH", data[i + 5:i + 9])
            return w, h
        i += 2 + length
    raise ValueError("no SOF marker")


def card_pages():
    out = list((SITE / "format").glob("references-for-*/index.html"))
    out += list((SITE / "guides").glob("*/index.html"))
    out += [p for p in (SITE / "blog").glob("*/index.html") if p.parent.name != "digest"]
    return sorted(out)


class SocialCards(unittest.TestCase):
    def test_cards_are_valid(self):
        checked = 0
        problems = []
        for p in card_pages():
            img = meta(p.read_text(encoding="utf-8", errors="ignore"), "og:image") or ""
            if "assets/og/cards/" not in img:
                continue
            checked += 1
            f = SITE / img.replace(ORIGIN, "").lstrip("/")
            rel = p.relative_to(SITE)
            if not f.is_file():
                problems.append(f"{rel}: missing {img}")
                continue
            try:
                size = jpeg_size(f)
            except ValueError as e:
                problems.append(f"{rel}: {e}")
                continue
            if size != (1200, 630):
                problems.append(f"{rel}: {size} not 1200x630")
            if f.stat().st_size >= MAX_BYTES:
                problems.append(f"{rel}: {f.stat().st_size} bytes")
        self.assertGreater(checked, 20)
        self.assertEqual(problems, [])

    def test_plan_has_no_jobs(self):
        # gen_og_cards imports PIL at module level; plan() itself does not use it, so stub it when absent.
        try:
            from PIL import Image  # noqa: F401
        except ImportError:
            pil = types.ModuleType("PIL")
            pil.Image = types.ModuleType("PIL.Image")
            sys.modules["PIL"], sys.modules["PIL.Image"] = pil, pil.Image
        spec = importlib.util.spec_from_file_location("gen_og_cards", ROOT / "scripts" / "gen_og_cards.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        jobs = mod.plan()
        self.assertEqual([f"{j['section']}/{j['slug']}" for j in jobs], [], "pages still on the generic card")
