"""Convert documents to Markdown using Microsoft markitdown.

Offline only: plugins are disabled and no LLM client is configured, so only
the built-in file converters run. Callers must pass a local file path, never a
URL, which keeps markitdown's network/URI converters (YouTube, http fetch)
unreachable.
"""
from markitdown import MarkItDown

_converter = MarkItDown(enable_plugins=False)


def convert_to_markdown(path: str) -> str:
    """Convert a local file to Markdown text. Raises on failure."""
    result = _converter.convert(path)
    # markitdown exposes `.markdown` in recent versions and keeps
    # `.text_content` for backward compatibility; prefer whichever exists.
    return getattr(result, "markdown", None) or result.text_content
