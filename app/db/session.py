from collections.abc import Generator

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.db.base import Base
from app.db import models  # noqa: F401


connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(
    settings.database_url,
    future=True,
    connect_args=connect_args,
    pool_pre_ping=True,
    echo=settings.database_echo,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def init_db() -> None:
    if settings.auto_create_tables:
        Base.metadata.create_all(bind=engine)
        _ensure_sqlite_runtime_compatibility()


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _ensure_sqlite_runtime_compatibility() -> None:
    if not settings.database_url.startswith("sqlite"):
        return

    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())

    with engine.begin() as connection:
        if "eval_runs" in existing_tables:
            existing_columns = {column["name"] for column in inspector.get_columns("eval_runs")}
            if "experiment_name" not in existing_columns:
                connection.execute(
                    text("ALTER TABLE eval_runs ADD COLUMN experiment_name VARCHAR(100) NOT NULL DEFAULT ''")
                )
            if "evaluator_version" not in existing_columns:
                connection.execute(
                    text(
                        "ALTER TABLE eval_runs ADD COLUMN evaluator_version "
                        "VARCHAR(50) NOT NULL DEFAULT 'heuristic-v1'"
                    )
                )
            if "run_metadata" not in existing_columns:
                connection.execute(
                    text("ALTER TABLE eval_runs ADD COLUMN run_metadata JSON NOT NULL DEFAULT '{}' ")
                )
            refreshed_columns = {column["name"] for column in inspect(engine).get_columns("eval_runs")}
            if "experiment_name" in refreshed_columns:
                indexes = {index["name"] for index in inspect(engine).get_indexes("eval_runs")}
                if "ix_eval_runs_experiment_name" not in indexes:
                    connection.execute(text("CREATE INDEX ix_eval_runs_experiment_name ON eval_runs (experiment_name)"))

        if "release_gate_decisions" not in existing_tables:
            connection.execute(
                text(
                    """
                    CREATE TABLE release_gate_decisions (
                        id VARCHAR(36) NOT NULL PRIMARY KEY,
                        dataset_name VARCHAR(100) NOT NULL,
                        baseline_run_id VARCHAR(36) NOT NULL,
                        candidate_run_id VARCHAR(36) NOT NULL,
                        status VARCHAR(20) NOT NULL,
                        summary TEXT NOT NULL,
                        metrics JSON NOT NULL,
                        failures JSON NOT NULL,
                        created_at DATETIME NOT NULL
                    )
                    """
                )
            )
            connection.execute(
                text(
                    "CREATE INDEX ix_release_gate_decisions_dataset_name "
                    "ON release_gate_decisions (dataset_name)"
                )
            )
            connection.execute(
                text(
                    "CREATE INDEX ix_release_gate_decisions_baseline_run_id "
                    "ON release_gate_decisions (baseline_run_id)"
                )
            )
            connection.execute(
                text(
                    "CREATE INDEX ix_release_gate_decisions_candidate_run_id "
                    "ON release_gate_decisions (candidate_run_id)"
                )
            )
            connection.execute(
                text(
                    "CREATE INDEX ix_release_gate_decisions_status "
                    "ON release_gate_decisions (status)"
                )
            )
