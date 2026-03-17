"""
Classifier unit tests.

Tests cover:
  - classify_document: content_type → DocumentFormat mapping
  - content-type parameter stripping
  - None content_type handling
  - unrecognised content types
  - content_peek passthrough (Phase 5B hook, currently no-op)
  - PARSER_VERSION constant
"""

from __future__ import annotations

import pytest

from app.parsers.classifier import PARSER_VERSION, classify_document


# ---------------------------------------------------------------------------
# Supported format mappings
# ---------------------------------------------------------------------------


def test_classify_xhtml_returns_ixbrl() -> None:
    assert classify_document("application/xhtml+xml") == "ixbrl"


def test_classify_xml_returns_xbrl() -> None:
    assert classify_document("application/xml") == "xbrl"


def test_classify_html_returns_html() -> None:
    assert classify_document("text/html") == "html"


def test_classify_pdf_returns_pdf() -> None:
    assert classify_document("application/pdf") == "pdf"


# ---------------------------------------------------------------------------
# Unsupported / edge cases
# ---------------------------------------------------------------------------


def test_classify_none_content_type_returns_unsupported() -> None:
    assert classify_document(None) == "unsupported"


def test_classify_unknown_content_type_returns_unsupported() -> None:
    assert classify_document("application/octet-stream") == "unsupported"


def test_classify_empty_string_returns_unsupported() -> None:
    assert classify_document("") == "unsupported"


def test_classify_plain_text_returns_unsupported() -> None:
    assert classify_document("text/plain") == "unsupported"


# ---------------------------------------------------------------------------
# Content-type parameter stripping
# ---------------------------------------------------------------------------


def test_classify_strips_charset_param() -> None:
    assert classify_document("text/html; charset=utf-8") == "html"


def test_classify_strips_boundary_param() -> None:
    assert classify_document("application/xhtml+xml; charset=UTF-8") == "ixbrl"


def test_classify_strips_whitespace_around_base_type() -> None:
    assert classify_document("  application/xml  ") == "xbrl"


# ---------------------------------------------------------------------------
# Case insensitivity
# ---------------------------------------------------------------------------


def test_classify_uppercase_content_type_returns_correct_format() -> None:
    assert classify_document("TEXT/HTML") == "html"


def test_classify_mixed_case_xhtml() -> None:
    assert classify_document("Application/XHTML+XML") == "ixbrl"


# ---------------------------------------------------------------------------
# content_peek hook — Phase 5B passthrough
# ---------------------------------------------------------------------------


def test_classify_with_content_peek_does_not_change_result_for_known_type() -> None:
    """content_peek is accepted but is a no-op in Phase 5A."""
    peek = b"<html><body>...</body></html>"
    assert classify_document("text/html", content_peek=peek) == "html"


def test_classify_unsupported_with_content_peek_stays_unsupported() -> None:
    """content_peek does not promote unsupported formats in Phase 5A."""
    # Even if the bytes look like iXBRL, Phase 5A ignores the content.
    peek = b'<html xmlns:ix="http://www.xbrl.org/2013/inlineXBRL">...</html>'
    assert classify_document("application/octet-stream", content_peek=peek) == "unsupported"


# ---------------------------------------------------------------------------
# PARSER_VERSION constant
# ---------------------------------------------------------------------------


def test_parser_version_is_semver_string() -> None:
    parts = PARSER_VERSION.split(".")
    assert len(parts) == 3
    assert all(p.isdigit() for p in parts)
