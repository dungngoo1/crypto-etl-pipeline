from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.bash import BashOperator

# Cấu hình tham số mặc định cho toàn bộ các Task
default_args = {
    'owner': 'dungngo',
    'depends_on_past': False,
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 2,
    'retry_delay': timedelta(minutes=2),
}

with DAG(
    dag_id='crypto_medallion_elt_pipeline',
    default_args=default_args,
    description='Automated ELT Pipeline ingest Binance API to Bronze, transform Silver/Gold via dbt',
    schedule_interval='@hourly',  # Chạy tự động mỗi giờ một lần
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=['crypto', 'medallion', 'dbt', 'postgres'],
) as dag:

    # Task 1: Ingest dữ liệu REST API nạp vào bảng Bronze
    extract_and_load_bronze = BashOperator(
        task_id='extract_and_load_bronze',
        bash_command='python /opt/airflow/scripts/ingest_market_data.py',
    )

    # Task 2: Chuyển đổi và làm sạch dữ liệu lên tầng Silver
    transform_silver = BashOperator(
        task_id='transform_silver',
        bash_command='cd /opt/airflow/dbt_project && dbt run --select silver --profiles-dir .',
    )

    # Task 3: Mô hình hóa dữ liệu theo Star Schema (Fact & Dim) lên tầng Gold
    transform_gold = BashOperator(
        task_id='transform_gold',
        bash_command='cd /opt/airflow/dbt_project && dbt run --select gold --profiles-dir .',
    )

    # Task 4: Kiểm thử chất lượng dữ liệu (Data Quality Testing & Circuit Breaker)
    data_quality_test = BashOperator(
        task_id='data_quality_test',
        bash_command='cd /opt/airflow/dbt_project && dbt test --profiles-dir .',
    )

    # Thiết lập luồng thực thi tuần tự (Task Dependencies)
    extract_and_load_bronze >> transform_silver >> transform_gold >> data_quality_test