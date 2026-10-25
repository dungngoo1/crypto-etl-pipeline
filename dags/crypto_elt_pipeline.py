from datetime import datetime, timedelta, timezone

from airflow import DAG
from airflow.operators.bash import BashOperator

DBT = "cd /opt/airflow/dbt_project && /opt/dbt/bin/dbt"

with DAG(
    dag_id="crypto_medallion_elt_pipeline",
    default_args={"owner": "dungngo", "retries": 2, "retry_delay": timedelta(minutes=2),
                  "email_on_failure": False, "email_on_retry": False},
    description="All Binance spot tickers: Bronze -> Silver -> Gold -> tested GA -> Power BI",
    schedule_interval="@hourly",
    start_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
    catchup=False, max_active_runs=1,
    tags=["crypto", "medallion", "dbt", "postgres", "ga"],
) as dag:
    ingest = BashOperator(
        task_id="extract_and_load_bronze",
        bash_command='python /opt/airflow/scripts/ingest_market_data.py --batch-id "$BATCH_ID" --batch-timestamp "$BATCH_TIMESTAMP"',
        env={"BATCH_ID": "{{ run_id }}", "BATCH_TIMESTAMP": "{{ data_interval_end.isoformat() }}"},
        append_env=True,
    )
    freshness = BashOperator(
        task_id="source_freshness",
        bash_command=f"{DBT} source freshness --profiles-dir .",
    )
    build = BashOperator(
        task_id="build_and_test_medallion",
        bash_command=f'{DBT} build --profiles-dir . --vars "$DBT_VARS"',
        env={"DBT_VARS": '{{ {"batch_id": run_id} | tojson }}'},
        append_env=True,
    )
    publish = BashOperator(
        task_id="publish_ga",
        bash_command='python /opt/airflow/scripts/publish_ga.py --batch-id "$BATCH_ID"',
        env={"BATCH_ID": "{{ run_id }}"}, append_env=True,
    )
    ingest >> freshness >> build >> publish
