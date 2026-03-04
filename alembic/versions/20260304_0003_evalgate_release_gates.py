"""add evalgate metadata and release gates

Revision ID: 20260304_0003
Revises: 20260302_0002
Create Date: 2026-03-04 10:30:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260304_0003"
down_revision = "20260302_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "eval_runs",
        sa.Column("experiment_name", sa.String(length=100), nullable=False, server_default=""),
    )
    op.add_column(
        "eval_runs",
        sa.Column("evaluator_version", sa.String(length=50), nullable=False, server_default="heuristic-v1"),
    )
    op.add_column(
        "eval_runs",
        sa.Column("run_metadata", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
    )
    op.create_index(op.f("ix_eval_runs_experiment_name"), "eval_runs", ["experiment_name"], unique=False)

    op.create_table(
        "release_gate_decisions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("dataset_name", sa.String(length=100), nullable=False),
        sa.Column("baseline_run_id", sa.String(length=36), nullable=False),
        sa.Column("candidate_run_id", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("metrics", sa.JSON(), nullable=False),
        sa.Column("failures", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_release_gate_decisions_dataset_name"),
        "release_gate_decisions",
        ["dataset_name"],
        unique=False,
    )
    op.create_index(
        op.f("ix_release_gate_decisions_baseline_run_id"),
        "release_gate_decisions",
        ["baseline_run_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_release_gate_decisions_candidate_run_id"),
        "release_gate_decisions",
        ["candidate_run_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_release_gate_decisions_status"),
        "release_gate_decisions",
        ["status"],
        unique=False,
    )

    op.alter_column("eval_runs", "experiment_name", server_default=None)
    op.alter_column("eval_runs", "evaluator_version", server_default=None)
    op.alter_column("eval_runs", "run_metadata", server_default=None)


def downgrade() -> None:
    op.drop_index(op.f("ix_release_gate_decisions_status"), table_name="release_gate_decisions")
    op.drop_index(op.f("ix_release_gate_decisions_candidate_run_id"), table_name="release_gate_decisions")
    op.drop_index(op.f("ix_release_gate_decisions_baseline_run_id"), table_name="release_gate_decisions")
    op.drop_index(op.f("ix_release_gate_decisions_dataset_name"), table_name="release_gate_decisions")
    op.drop_table("release_gate_decisions")

    op.drop_index(op.f("ix_eval_runs_experiment_name"), table_name="eval_runs")
    op.drop_column("eval_runs", "run_metadata")
    op.drop_column("eval_runs", "evaluator_version")
    op.drop_column("eval_runs", "experiment_name")
