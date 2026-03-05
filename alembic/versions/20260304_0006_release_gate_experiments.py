"""link release gates to experiments

Revision ID: 20260304_0006
Revises: 20260304_0005
Create Date: 2026-03-04 12:30:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260304_0006"
down_revision = "20260304_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "release_gate_decisions",
        sa.Column("experiment_name", sa.String(length=100), nullable=False, server_default=""),
    )
    op.create_index(
        op.f("ix_release_gate_decisions_experiment_name"),
        "release_gate_decisions",
        ["experiment_name"],
        unique=False,
    )
    op.alter_column("release_gate_decisions", "experiment_name", server_default=None)


def downgrade() -> None:
    op.drop_index(op.f("ix_release_gate_decisions_experiment_name"), table_name="release_gate_decisions")
    op.drop_column("release_gate_decisions", "experiment_name")

