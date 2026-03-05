"""add scenario metadata to golden cases

Revision ID: 20260304_0004
Revises: 20260304_0003
Create Date: 2026-03-04 11:15:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260304_0004"
down_revision = "20260304_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "golden_cases",
        sa.Column("scenario", sa.String(length=100), nullable=False, server_default="general"),
    )
    op.add_column(
        "golden_cases",
        sa.Column("slice_name", sa.String(length=100), nullable=False, server_default="default"),
    )
    op.add_column(
        "golden_cases",
        sa.Column("severity", sa.String(length=20), nullable=False, server_default="medium"),
    )
    op.create_index(op.f("ix_golden_cases_scenario"), "golden_cases", ["scenario"], unique=False)
    op.create_index(op.f("ix_golden_cases_slice_name"), "golden_cases", ["slice_name"], unique=False)
    op.create_index(op.f("ix_golden_cases_severity"), "golden_cases", ["severity"], unique=False)
    op.alter_column("golden_cases", "scenario", server_default=None)
    op.alter_column("golden_cases", "slice_name", server_default=None)
    op.alter_column("golden_cases", "severity", server_default=None)


def downgrade() -> None:
    op.drop_index(op.f("ix_golden_cases_severity"), table_name="golden_cases")
    op.drop_index(op.f("ix_golden_cases_slice_name"), table_name="golden_cases")
    op.drop_index(op.f("ix_golden_cases_scenario"), table_name="golden_cases")
    op.drop_column("golden_cases", "severity")
    op.drop_column("golden_cases", "slice_name")
    op.drop_column("golden_cases", "scenario")
