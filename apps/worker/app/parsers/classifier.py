"""
Document format classifier.

Classifies a filing document into a parser-relevant format category based on
the stored content_type metadata.  A content_peek hook is provided for Phase 5B
content sniffing (iXBRL namespace detection); it is currently a no-op.

Supported formats and their meanings:
    ixbrl       — Inline XBRL served as application/xhtml+xml.  Highest
                  confidence extraction path; tagged facts with contexts.
    xbrl        — Standalone XBRL served as application/xml.  Structured
                  but requires a different extraction path to iXBRL.
    html        — Semi-structured HTML tables.  Fallback extraction path;
                  lower confidence, requires DOM parsing and label matching.
    pdf         — PDF document.  Not extractable in Phase MVP (scanned or
                  image-based content); classified as unsupported until an
                  OCR path is implemented.
    unsupported — Any other content type, or no content type available.
                  Terminal; the document will not be re-attempted for
                  structured extraction.

Detection rules (docs/05-parser-design.md §Format detection):
    - application/xhtml+xml → ixbrl
    - application/xml       → xbrl
    - text/html             → html
    - application/pdf       → pdf (classified as unsupported for extraction)
    - anything else         → unsupported

Phase 5B will extend this module with content_peek inspection to confirm
iXBRL by checking for ix: namespace markers inside the document bytes.
"""

from __future__ import annotations

from typing import Literal

# Increment when classifier logic changes in a way that would change the
# output for any document.  Downstream extraction_runs rows record this
# version so re-parse history is traceable to the classifier that ran.
PARSER_VERSION = "1.1.0"

# All valid DocumentFormat values.
DocumentFormat = Literal["ixbrl", "xbrl", "html", "pdf", "unsupported"]

# Mapping from (normalised) content-type base to DocumentFormat.
# PDF is mapped to 'pdf' here; the caller decides whether to treat it as
# 'unsupported' at the task level — the format label is still preserved.
_CONTENT_TYPE_FORMAT: dict[str, DocumentFormat] = {
    "application/xhtml+xml": "ixbrl",
    "application/xml": "xbrl",
    "text/html": "html",
    "application/pdf": "pdf",
}


def classify_document(
    content_type: str | None,
    content_peek: bytes | None = None,  # noqa: ARG001  — Phase 5B hook
) -> DocumentFormat:
    """
    Classify a filing document into a parser-relevant format category.

    Phase 5A: classification is based on content_type metadata only.
    Phase 5B: content_peek will be used to confirm iXBRL by inspecting
              document bytes for ix: namespace markers.

    Args:
        content_type: The MIME type from filing_documents.content_type.
                      Content-type parameters (e.g. charset=utf-8) are
                      stripped before lookup.
        content_peek: First N bytes of the raw document.  Unused in Phase 5A;
                      reserved for Phase 5B format confirmation.

    Returns:
        One of: 'ixbrl', 'xbrl', 'html', 'pdf', 'unsupported'.
    """
    if content_type is None:
        return "unsupported"

    # Strip content-type parameters: "text/html; charset=utf-8" → "text/html"
    base_ct = content_type.split(";")[0].strip().lower()
    fmt = _CONTENT_TYPE_FORMAT.get(base_ct)
    if fmt is not None:
        return fmt

    # Phase 5B hook: inspect content_peek for iXBRL or XBRL namespace markers.
    # Example (not yet active):
    #   if content_peek and b"xmlns:ix=" in content_peek:
    #       return "ixbrl"

    return "unsupported"
