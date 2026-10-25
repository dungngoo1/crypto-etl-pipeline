# dbt transformation project

See [the main README](../README.md) for setup and [the dictionary](../docs/DATA_DICTIONARY.md) for grains and units.

Models: Silver -> Gold -> GA candidates. Only the Python publish step exposes tested candidates in schema ga.

Run with the same batch ID as ingestion:

```bash
/opt/dbt/bin/dbt source freshness --profiles-dir .
/opt/dbt/bin/dbt build --profiles-dir . --vars "{batch_id: manual_demo_001}"
```

Credentials come from WAREHOUSE_* environment variables. Do not run dbt and the scheduled DAG concurrently.
