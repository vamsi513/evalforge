"""initial schema

Revision ID: 20260301_0001
Revises:
Create Date: 2026-03-01 22:15:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260301_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "datasets",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("owner", sa.String(length=100), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", name="uq_dataset_name"),
    )

    op.create_table(
        "eval_runs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("dataset_name", sa.String(length=100), nullable=False),
        sa.Column("prompt_version", sa.String(length=50), nullable=False),
        sa.Column("model_name", sa.String(length=100), nullable=False),
        sa.Column("average_score", sa.Float(), nullable=False),
        sa.Column("results", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_eval_runs_dataset_name"), "eval_runs", ["dataset_name"], unique=False)

    op.create_table(
        "prompt_templates",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("dataset_name", sa.String(length=100), nullable=False),
        sa.Column("version", sa.String(length=50), nullable=False),
        sa.Column("system_prompt", sa.Text(), nullable=False),
        sa.Column("task_prompt", sa.Text(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("dataset_name", "version", name="uq_prompt_template_version"),
    )
    op.create_index(
        op.f("ix_prompt_templates_dataset_name"), "prompt_templates", ["dataset_name"], unique=False
    )

    op.create_table(
        "golden_cases",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("dataset_name", sa.String(length=100), nullable=False),
        sa.Column("input_prompt", sa.Text(), nullable=False),
        sa.Column("expected_keyword", sa.String(length=200), nullable=False),
        sa.Column("reference_answer", sa.Text(), nullable=False),
        sa.Column("rubric", sa.JSON(), nullable=False),
        sa.Column("tags", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_golden_cases_dataset_name"), "golden_cases", ["dataset_name"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_golden_cases_dataset_name"), table_name="golden_cases")
    op.drop_table("golden_cases")
    op.drop_index(op.f("ix_prompt_templates_dataset_name"), table_name="prompt_templates")
    op.drop_table("prompt_templates")
    op.drop_index(op.f("ix_eval_runs_dataset_name"), table_name="eval_runs")
    op.drop_table("eval_runs")
    op.drop_table("datasets")
