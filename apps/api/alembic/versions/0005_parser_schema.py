"""Parser schema — add document_format to filing_documents and extraction_runs.

Revision ID: 0005
Revises: 0004
Create Date: 2026-03-17

Changes:
    filing_documents.document_format varchar(32) NULL
        Populated by the Phase 5A classify step.  Stores the detected parser
        format: 'ixbrl', 'xbrl', 'html', 'pdf', or 'unsupported'.
        NULL means the document has not been classified yet.

    extraction_runs.document_format varchar(32) NULL
        Records the format that was detected at the time the extraction run
        was created.  Allows historical tracking if format detection logic
        changes between re-parses.

    New controlled vocabulary value for filing_documents.parse_status:
        'classified' — format detected; awaiting Phase 5B extraction.
        (No DB enum change needed — parse_status is varchar(32).)
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "filing_documents",
        sa.Column("document_format", sa.String(32), nullable=True),
    )
    op.add_column(
        "extraction_runs",
        sa.Column("document_format", sa.String(32), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("extraction_runs", "document_format")
    op.drop_column("filing_documents", "document_format")
