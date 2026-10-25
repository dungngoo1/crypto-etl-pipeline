FROM apache/airflow:2.8.1-python3.10
USER airflow
# Preserve Airflow constraints; isolate dbt's different dependencies.
RUN pip install --no-cache-dir "apache-airflow==2.8.1" requests==2.31.0 psycopg2-binary==2.9.9 \
    --constraint https://raw.githubusercontent.com/apache/airflow/constraints-2.8.1/constraints-3.10.txt
USER root
RUN python -m venv /opt/dbt && chown -R airflow:0 /opt/dbt
USER airflow
COPY --chown=airflow:0 requirements-dbt.txt /tmp/requirements-dbt.txt
RUN PIP_USER=false /opt/dbt/bin/pip install --no-cache-dir -r /tmp/requirements-dbt.txt
