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


def check_db_connection() -> bool:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def _ensure_sqlite_runtime_compatibility() -> None:
    if not settings.database_url.startswith("sqlite"):
        return

    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())

    with engine.begin() as connection:
        if "datasets" in existing_tables:
            dataset_columns = {column["name"] for column in inspect(engine).get_columns("datasets")}
            if "workspace_id" not in dataset_columns:
                connection.execute(
                    text("ALTER TABLE datasets ADD COLUMN workspace_id VARCHAR(100) NOT NULL DEFAULT 'default'")
                )
            dataset_indexes = {index["name"] for index in inspect(engine).get_indexes("datasets")}
            if "ix_datasets_workspace_id" not in dataset_indexes:
                connection.execute(text("CREATE INDEX ix_datasets_workspace_id ON datasets (workspace_id)"))

        if "eval_runs" in existing_tables:
            existing_columns = {column["name"] for column in inspector.get_columns("eval_runs")}
            if "workspace_id" not in existing_columns:
                connection.execute(
                    text("ALTER TABLE eval_runs ADD COLUMN workspace_id VARCHAR(100) NOT NULL DEFAULT 'default'")
                )
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
                if "ix_eval_runs_workspace_id" not in indexes:
                    connection.execute(text("CREATE INDEX ix_eval_runs_workspace_id ON eval_runs (workspace_id)"))
                if "ix_eval_runs_experiment_name" not in indexes:
                    connection.execute(text("CREATE INDEX ix_eval_runs_experiment_name ON eval_runs (experiment_name)"))

        if "eval_jobs" in existing_tables:
            job_columns = {column["name"] for column in inspect(engine).get_columns("eval_jobs")}
            if "workspace_id" not in job_columns:
                connection.execute(
                    text("ALTER TABLE eval_jobs ADD COLUMN workspace_id VARCHAR(100) NOT NULL DEFAULT 'default'")
                )
            job_indexes = {index["name"] for index in inspect(engine).get_indexes("eval_jobs")}
            if "ix_eval_jobs_workspace_id" not in job_indexes:
                connection.execute(text("CREATE INDEX ix_eval_jobs_workspace_id ON eval_jobs (workspace_id)"))

        if "experiments" not in existing_tables:
            connection.execute(
                text(
                    """
                    CREATE TABLE experiments (
                        id VARCHAR(36) NOT NULL PRIMARY KEY,
                        workspace_id VARCHAR(100) NOT NULL DEFAULT 'default',
                        name VARCHAR(100) NOT NULL,
                        dataset_name VARCHAR(100) NOT NULL,
                        owner VARCHAR(100) NOT NULL,
                        status VARCHAR(20) NOT NULL DEFAULT 'draft',
                        description TEXT NOT NULL DEFAULT '',
                        baseline_run_id VARCHAR(36) NOT NULL DEFAULT '',
                        candidate_run_id VARCHAR(36) NOT NULL DEFAULT '',
                        experiment_metadata JSON NOT NULL DEFAULT '{}',
                        created_at DATETIME NOT NULL,
                        updated_at DATETIME NOT NULL
                    )
                    """
                )
            )
            connection.execute(text("CREATE INDEX ix_experiments_workspace_id ON experiments (workspace_id)"))
            connection.execute(text("CREATE INDEX ix_experiments_name ON experiments (name)"))
            connection.execute(text("CREATE INDEX ix_experiments_dataset_name ON experiments (dataset_name)"))
            connection.execute(text("CREATE INDEX ix_experiments_status ON experiments (status)"))
            connection.execute(
                text(
                    "CREATE UNIQUE INDEX uq_experiment_workspace_name_idx "
                    "ON experiments (workspace_id, name)"
                )
            )

        if "evaluator_definitions" not in existing_tables:
            connection.execute(
                text(
                    """
                    CREATE TABLE evaluator_definitions (
                        id VARCHAR(36) NOT NULL PRIMARY KEY,
                        name VARCHAR(100) NOT NULL,
                        version VARCHAR(50) NOT NULL,
                        kind VARCHAR(50) NOT NULL,
                        status VARCHAR(20) NOT NULL DEFAULT 'active',
                        description TEXT NOT NULL DEFAULT '',
                        config JSON NOT NULL DEFAULT '{}',
                        created_at DATETIME NOT NULL,
                        updated_at DATETIME NOT NULL
                    )
                    """
                )
            )
            connection.execute(text("CREATE INDEX ix_evaluator_definitions_name ON evaluator_definitions (name)"))
            connection.execute(
                text("CREATE INDEX ix_evaluator_definitions_version ON evaluator_definitions (version)")
            )
            connection.execute(text("CREATE INDEX ix_evaluator_definitions_kind ON evaluator_definitions (kind)"))
            connection.execute(text("CREATE INDEX ix_evaluator_definitions_status ON evaluator_definitions (status)"))
            connection.execute(
                text(
                    "CREATE UNIQUE INDEX uq_evaluator_name_version_idx "
                    "ON evaluator_definitions (name, version)"
                )
            )

        if "model_routing_policies" not in existing_tables:
            connection.execute(
                text(
                    """
                    CREATE TABLE model_routing_policies (
                        id VARCHAR(36) NOT NULL PRIMARY KEY,
                        workspace_id VARCHAR(100) NOT NULL DEFAULT 'default',
                        use_case VARCHAR(100) NOT NULL,
                        version VARCHAR(50) NOT NULL,
                        primary_provider VARCHAR(50) NOT NULL,
                        primary_model VARCHAR(100) NOT NULL,
                        fallback_provider VARCHAR(50) NOT NULL DEFAULT '',
                        fallback_model VARCHAR(100) NOT NULL DEFAULT '',
                        max_latency_ms FLOAT NOT NULL DEFAULT 1000.0,
                        max_cost_usd FLOAT NOT NULL DEFAULT 0.01,
                        status VARCHAR(20) NOT NULL DEFAULT 'active',
                        notes TEXT NOT NULL DEFAULT '',
                        created_at DATETIME NOT NULL,
                        updated_at DATETIME NOT NULL
                    )
                    """
                )
            )
            connection.execute(
                text("CREATE INDEX ix_model_routing_policies_workspace_id ON model_routing_policies (workspace_id)")
            )
            connection.execute(text("CREATE INDEX ix_model_routing_policies_use_case ON model_routing_policies (use_case)"))
            connection.execute(text("CREATE INDEX ix_model_routing_policies_version ON model_routing_policies (version)"))
            connection.execute(text("CREATE INDEX ix_model_routing_policies_status ON model_routing_policies (status)"))
            connection.execute(
                text(
                    "CREATE UNIQUE INDEX uq_model_routing_workspace_use_case_version_idx "
                    "ON model_routing_policies (workspace_id, use_case, version)"
                )
            )

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

        if "golden_cases" in existing_tables:
            golden_case_columns = {column["name"] for column in inspect(engine).get_columns("golden_cases")}
            if "scenario" not in golden_case_columns:
                connection.execute(
                    text("ALTER TABLE golden_cases ADD COLUMN scenario VARCHAR(100) NOT NULL DEFAULT 'general'")
                )
            if "slice_name" not in golden_case_columns:
                connection.execute(
                    text("ALTER TABLE golden_cases ADD COLUMN slice_name VARCHAR(100) NOT NULL DEFAULT 'default'")
                )
            if "severity" not in golden_case_columns:
                connection.execute(
                    text("ALTER TABLE golden_cases ADD COLUMN severity VARCHAR(20) NOT NULL DEFAULT 'medium'")
                )
            if "required_json_fields" not in golden_case_columns:
                connection.execute(
                    text("ALTER TABLE golden_cases ADD COLUMN required_json_fields JSON NOT NULL DEFAULT '[]'")
                )
            golden_case_indexes = {index["name"] for index in inspect(engine).get_indexes("golden_cases")}
            if "ix_golden_cases_scenario" not in golden_case_indexes:
                connection.execute(text("CREATE INDEX ix_golden_cases_scenario ON golden_cases (scenario)"))
            if "ix_golden_cases_slice_name" not in golden_case_indexes:
                connection.execute(text("CREATE INDEX ix_golden_cases_slice_name ON golden_cases (slice_name)"))
            if "ix_golden_cases_severity" not in golden_case_indexes:
                connection.execute(text("CREATE INDEX ix_golden_cases_severity ON golden_cases (severity)"))

        if "release_gate_decisions" in existing_tables:
            gate_columns = {column["name"] for column in inspect(engine).get_columns("release_gate_decisions")}
            if "workspace_id" not in gate_columns:
                connection.execute(
                    text(
                        "ALTER TABLE release_gate_decisions "
                        "ADD COLUMN workspace_id VARCHAR(100) NOT NULL DEFAULT 'default'"
                    )
                )
            gate_indexes = {index["name"] for index in inspect(engine).get_indexes("release_gate_decisions")}
            if "ix_release_gate_decisions_workspace_id" not in gate_indexes:
                connection.execute(
                    text("CREATE INDEX ix_release_gate_decisions_workspace_id ON release_gate_decisions (workspace_id)")
                )
