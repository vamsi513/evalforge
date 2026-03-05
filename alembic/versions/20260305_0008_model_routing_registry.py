"""add model routing registry

Revision ID: 20260305_0008
Revises: 20260304_0007
Create Date: 2026-03-05 09:00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260305_0008"
down_revision = "20260304_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "model_routing_policies",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("workspace_id", sa.String(length=100), nullable=False, server_default="default"),
        sa.Column("use_case", sa.String(length=100), nullable=False),
        sa.Column("version", sa.String(length=50), nullable=False),
        sa.Column("primary_provider", sa.String(length=50), nullable=False),
        sa.Column("primary_model", sa.String(length=100), nullable=False),
        sa.Column("fallback_provider", sa.String(length=50), nullable=False, server_default=""),
        sa.Column("fallback_model", sa.String(length=100), nullable=False, server_default=""),
        sa.Column("max_latency_ms", sa.Float(), nullable=False, server_default="1000.0"),
        sa.Column("max_cost_usd", sa.Float(), nullable=False, server_default="0.01"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
        sa.Column("notes", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "workspace_id",
            "use_case",
            "version",
            name="uq_model_routing_workspace_use_case_version",
        ),
    )
    op.create_index(op.f("ix_model_routing_policies_workspace_id"), "model_routing_policies", ["workspace_id"], unique=False)
    op.create_index(op.f("ix_model_routing_policies_use_case"), "model_routing_policies", ["use_case"], unique=False)
    op.create_index(op.f("ix_model_routing_policies_version"), "model_routing_policies", ["version"], unique=False)
    op.create_index(op.f("ix_model_routing_policies_status"), "model_routing_policies", ["status"], unique=False)
    op.alter_column("model_routing_policies", "workspace_id", server_default=None)
    op.alter_column("model_routing_policies", "fallback_provider", server_default=None)
    op.alter_column("model_routing_policies", "fallback_model", server_default=None)
    op.alter_column("model_routing_policies", "max_latency_ms", server_default=None)
    op.alter_column("model_routing_policies", "max_cost_usd", server_default=None)
    op.alter_column("model_routing_policies", "status", server_default=None)
    op.alter_column("model_routing_policies", "notes", server_default=None)


def downgrade() -> None:
    op.drop_index(op.f("ix_model_routing_policies_status"), table_name="model_routing_policies")
    op.drop_index(op.f("ix_model_routing_policies_version"), table_name="model_routing_policies")
    op.drop_index(op.f("ix_model_routing_policies_use_case"), table_name="model_routing_policies")
    op.drop_index(op.f("ix_model_routing_policies_workspace_id"), table_name="model_routing_policies")
    op.drop_table("model_routing_policies")

