"""Add password_hash column to users table.

Revision ID: 0008
Revises: 0007
Create Date: 2026-03-19

Adds nullable password_hash TEXT column to support email+password
authentication (auth_provider = 'password'). OAuth-authenticated users
(auth_provider in {'google', 'github', ...}) leave this column NULL.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("password_hash", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "password_hash")
