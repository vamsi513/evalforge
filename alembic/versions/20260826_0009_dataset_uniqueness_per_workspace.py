"""scope dataset uniqueness to workspace

Revision ID: 20260826_0009
Revises: 20260305_0008
Create Date: 2026-08-26 00:00:00
"""

from alembic import op

revision = "20260826_0009"
down_revision = "20260305_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("datasets") as batch_op:
        batch_op.drop_constraint("uq_dataset_name", type_="unique")
        batch_op.create_unique_constraint(
            "uq_dataset_workspace_name", ["workspace_id", "name"]
        )


def downgrade() -> None:
    with op.batch_alter_table("datasets") as batch_op:
        batch_op.drop_constraint("uq_dataset_workspace_name", type_="unique")
        batch_op.create_unique_constraint("uq_dataset_name", ["name"])
