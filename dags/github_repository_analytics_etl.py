from datetime import timedelta

import pendulum
from airflow.providers.standard.operators.bash import BashOperator
from airflow.sdk import DAG


PROJECT_DIR = "/opt/airflow/project"


def make_stage_task(task_id: str, command: str, timeout_minutes: int = 10) -> BashOperator:
    return BashOperator(
        task_id=task_id,
        bash_command=f"""
            set -euo pipefail
            cd {PROJECT_DIR}
            {command}
        """,
        execution_timeout=timedelta(minutes=timeout_minutes),
    )


with DAG(
    dag_id="github_repository_analytics_etl",
    description="Orchestrates the GitHub Repository Analytics ETL pipeline",

    # Scheduling
    start_date=pendulum.datetime(2026, 11, 4, tz="Asia/Kolkata"),
    schedule="0 2 * * *",
    catchup=False,

    # Prevent overlapping pipeline executions
    max_active_runs=1,
    max_active_tasks=1,

    # Stop a DAG run if it takes too long
    dagrun_timeout=timedelta(hours=1),

    # Default task settings
    default_args={
        "owner": "data-engineering",
        "retries": 2,
        "retry_delay": timedelta(minutes=5),
        "retry_exponential_backoff": True,
        "max_retry_delay": timedelta(minutes=15),
    },

    tags=["github", "etl", "data-engineering"],

    doc_md="""
    # GitHub Repository Analytics ETL

    ## Workflow
    1. **extract_github_data**: Incremental fetch from GitHub API into raw files + pending checkpoint.
    2. **load_raw_data**: Load extracted JSON/CSV payloads into PostgreSQL raw tables.
    3. **transform_data**: Clean, deduplicate, and standardize raw records.
    4. **validate_clean_data**: Run schema, null, and business-rule checks on staging data.
    5. **load_data_warehouse**: Upsert dimension and fact tables.
    6. **validate_warehouse**: Verify row counts, foreign keys, and warehouse integrity.
    7. **commit_checkpoint**: Atomically advance the incremental extraction watermark.
    """,
) as dag:

    extract = make_stage_task(
        task_id="extract_github_data",
        command="python -m scripts.extract",
        timeout_minutes=15,
    )

    load_raw = make_stage_task(
        task_id="load_raw_data",
        command="-m scripts.load_raw",
        timeout_minutes=10,
    )

    transform = make_stage_task(
        task_id="transform_data",
        command="python -m scripts.transform",
        timeout_minutes=10,
    )

    validate_clean = make_stage_task(
        task_id="validate_clean_data",
        command="python -m scripts.validate",
        timeout_minutes=5,
    )

    load_warehouse = make_stage_task(
        task_id="load_data_warehouse",
        command="python -m scripts.load_warehouse",
        timeout_minutes=10,
    )

    validate_warehouse = make_stage_task(
        task_id="validate_warehouse",
        command="python -m scripts.validate_warehouse",
        timeout_minutes=5,
    )

    commit_checkpoint = make_stage_task(
        task_id="commit_checkpoint",
        command="python -m scripts.run_pipeline --commit-checkpoint",
        timeout_minutes=2,
    )

    (
        extract
        >> load_raw
        >> transform
        >> validate_clean
        >> load_warehouse
        >> validate_warehouse
        >> commit_checkpoint
    )