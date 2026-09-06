"""add notes field to documents

Revision ID: d0fc12509b11
Revises: 07a79a5898d6
Create Date: 2026-09-06 14:54:16.086043

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd0fc12509b11'
down_revision: Union[str, Sequence[str], None] = '07a79a5898d6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('documents', sa.Column('notes', sa.Text(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('documents', 'notes')
