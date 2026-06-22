# backend/tests/test_digest_harvester.py
import sys
from pathlib import Path
BACKEND = Path(__file__).resolve().parent.parent
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from digest.sources import SOURCES, SourceDef, SourceType


def test_sources_is_nonempty():
    assert len(SOURCES) >= 10


def test_every_source_has_required_fields():
    for s in SOURCES:
        assert isinstance(s, SourceDef)
        assert s.name
        assert isinstance(s.type, SourceType)
        assert s.url
        assert s.category in {
            "papers", "ai_tech", "cybersecurity",
            "finance", "entrepreneurship", "general_tech",
        }


def test_no_duplicate_urls():
    urls = [s.url for s in SOURCES]
    assert len(urls) == len(set(urls)), "Duplicate URLs found in SOURCES"


def test_no_duplicate_names():
    names = [s.name for s in SOURCES]
    assert len(names) == len(set(names)), "Duplicate names found in SOURCES"
