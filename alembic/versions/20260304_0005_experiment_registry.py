"""add experiment registry

Revision ID: 20260304_0005
Revises: 20260304_0004
Create Date: 2026-03-04 12:00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260304_0005"
down_revision = "20260304_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "experiments",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("workspace_id", sa.String(length=100), nullable=False, server_default="default"),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("dataset_name", sa.String(length=100), nullable=False),
        sa.Column("owner", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="draft"),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("baseline_run_id", sa.String(length=36), nullable=False, server_default=""),
        sa.Column("candidate_run_id", sa.String(length=36), nullable=False, server_default=""),
        sa.Column("experiment_metadata", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workspace_id", "name", name="uq_experiment_workspace_name"),
    )
    op.create_index(op.f("ix_experiments_workspace_id"), "experiments", ["workspace_id"], unique=False)
    op.create_index(op.f("ix_experiments_name"), "experiments", ["name"], unique=False)
    op.create_index(op.f("ix_experiments_dataset_name"), "experiments", ["dataset_name"], unique=False)
    op.create_index(op.f("ix_experiments_status"), "experiments", ["status"], unique=False)
    op.alter_column("experiments", "workspace_id", server_default=None)
    op.alter_column("experiments", "status", server_default=None)
    op.alter_column("experiments", "description", server_default=None)
    op.alter_column("experiments", "baseline_run_id", server_default=None)
    op.alter_column("experiments", "candidate_run_id", server_default=None)
    op.alter_column("experiments", "experiment_metadata", server_default=None)


def downgrade() -> None:
    op.drop_index(op.f("ix_experiments_status"), table_name="experiments")
    op.drop_index(op.f("ix_experiments_dataset_name"), table_name="experiments")
    op.drop_index(op.f("ix_experiments_name"), table_name="experiments")
    op.drop_index(op.f("ix_experiments_workspace_id"), table_name="experiments")
    op.drop_table("experiments")

