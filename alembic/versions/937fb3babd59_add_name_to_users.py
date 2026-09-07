"""add name to users

Revision ID: 937fb3babd59
Revises: d0fc12509b11
Create Date: 2026-09-07 16:19:53.102434

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '937fb3babd59'
down_revision: Union[str, Sequence[str], None] = 'd0fc12509b11'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('users', sa.Column('name', sa.String(length=255), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('users', 'name')
