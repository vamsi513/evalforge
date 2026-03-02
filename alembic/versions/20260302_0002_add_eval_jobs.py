"""add eval jobs

Revision ID: 20260302_0002
Revises: 20260301_0001
Create Date: 2026-03-02 11:30:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260302_0002"
down_revision = "20260301_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "eval_jobs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("job_type", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("dataset_name", sa.String(length=100), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("result", sa.JSON(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_eval_jobs_dataset_name"), "eval_jobs", ["dataset_name"], unique=False)
    op.create_index(op.f("ix_eval_jobs_status"), "eval_jobs", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_eval_jobs_status"), table_name="eval_jobs")
    op.drop_index(op.f("ix_eval_jobs_dataset_name"), table_name="eval_jobs")
    op.drop_table("eval_jobs")
