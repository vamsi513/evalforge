"""add evaluator registry

Revision ID: 20260304_0007
Revises: 20260304_0006
Create Date: 2026-03-04 13:00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260304_0007"
down_revision = "20260304_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "evaluator_definitions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("version", sa.String(length=50), nullable=False),
        sa.Column("kind", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("config", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", "version", name="uq_evaluator_name_version"),
    )
    op.create_index(op.f("ix_evaluator_definitions_name"), "evaluator_definitions", ["name"], unique=False)
    op.create_index(op.f("ix_evaluator_definitions_version"), "evaluator_definitions", ["version"], unique=False)
    op.create_index(op.f("ix_evaluator_definitions_kind"), "evaluator_definitions", ["kind"], unique=False)
    op.create_index(op.f("ix_evaluator_definitions_status"), "evaluator_definitions", ["status"], unique=False)
    op.alter_column("evaluator_definitions", "status", server_default=None)
    op.alter_column("evaluator_definitions", "description", server_default=None)
    op.alter_column("evaluator_definitions", "config", server_default=None)


def downgrade() -> None:
    op.drop_index(op.f("ix_evaluator_definitions_status"), table_name="evaluator_definitions")
    op.drop_index(op.f("ix_evaluator_definitions_kind"), table_name="evaluator_definitions")
    op.drop_index(op.f("ix_evaluator_definitions_version"), table_name="evaluator_definitions")
    op.drop_index(op.f("ix_evaluator_definitions_name"), table_name="evaluator_definitions")
    op.drop_table("evaluator_definitions")

