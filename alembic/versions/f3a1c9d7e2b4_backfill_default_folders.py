"""backfill default folders for pre-existing users

Revision ID: f3a1c9d7e2b4
Revises: 7bfad1211a79
Create Date: 2026-09-05 15:52:00.000000

Data migration: any user created before the folders feature existed has zero
folder rows. This gives every such user the same 5 default folders that
registration now creates automatically for new users. Idempotent -- only
users with zero folders are touched, so re-running (or running against a DB
that already seeded some users) is a no-op for anyone already seeded.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f3a1c9d7e2b4'
down_revision: Union[str, Sequence[str], None] = '7bfad1211a79'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

DEFAULT_FOLDER_NAMES = ["Lab Results", "Imaging", "Prescriptions", "Surgery", "General"]

# Lightweight, migration-local table definitions -- deliberately not
# importing webapp.models here, so this migration keeps working unchanged
# even if the ORM models evolve later.
users_table = sa.table("users", sa.column("id", sa.Integer))
folders_table = sa.table(
	"folders",
	sa.column("id", sa.Integer),
	sa.column("user_id", sa.Integer),
	sa.column("name", sa.String),
	sa.column("parent_folder_id", sa.Integer),
	sa.column("color", sa.String),
	sa.column("cover_image_path", sa.String),
)


def upgrade() -> None:
	bind = op.get_bind()

	all_user_ids = {row[0] for row in bind.execute(sa.select(users_table.c.id))}
	users_with_folders = {row[0] for row in bind.execute(sa.select(folders_table.c.user_id).distinct())}
	users_missing_folders = all_user_ids - users_with_folders

	if not users_missing_folders:
		return

	rows_to_insert = [
		{
			"user_id": user_id,
			"name": name,
			"parent_folder_id": None,
			"color": None,
			"cover_image_path": None,
		}
		for user_id in users_missing_folders
		for name in DEFAULT_FOLDER_NAMES
	]
	op.bulk_insert(folders_table, rows_to_insert)


def downgrade() -> None:
	# Data backfills are not safely reversible: we cannot distinguish the
	# default folders this migration created from folders a user later
	# created (or renamed back to a matching name) on their own. No-op by
	# design -- reversing the schema migration below this one still removes
	# the folders table entirely if that's what's needed.
	pass
