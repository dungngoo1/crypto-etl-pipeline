"""Integration test against a disposable, initialized PostgreSQL database only."""
import os
from pathlib import Path
import subprocess
from datetime import datetime, timedelta, timezone

import psycopg2

from ingest_market_data import load_to_bronze, warehouse_connection
from publish_ga import publish

ROOT = Path(__file__).resolve().parents[1]
BATCH_ID = "fixture__integration"
NOW = datetime.now(timezone.utc)


def run_dbt(batch_id=BATCH_ID):
    command = os.getenv("DBT_EXECUTABLE", "/opt/dbt/bin/dbt")
    subprocess.run(
        [command, "build", "--profiles-dir", ".", "--vars", '{"batch_id":"' + batch_id + '"}'],
        cwd=ROOT / "dbt_project", check=True,
    )


def main():
    # Synthetic fixtures, never presented as live market data.
    records, metadata = [], {}
    for symbol, base, quote, status, price, volume in [
        ("BTCUSDT", "BTC", "USDT", "TRADING", "100", "1000"),
        ("ETHBTC", "ETH", "BTC", "TRADING", "0.05", "2"),
        ("OLDUSDT", "OLD", "USDT", "BREAK", "0", "0"),
    ]:
        records.append({
            "symbol": symbol, "lastPrice": price, "openPrice": price,
            "priceChange": "0", "priceChangePercent": "0",
            "highPrice": price, "lowPrice": price, "volume": "10",
            "quoteVolume": volume, "count": 10 if volume != "0" else 0,
            "openTime": 1767225600123, "closeTime": 1767312000123,
        })
        metadata[symbol] = {"symbol": symbol, "baseAsset": base, "quoteAsset": quote,
                            "status": status, "isSpotTradingAllowed": status == "TRADING"}
    load_to_bronze(records, metadata, BATCH_ID, NOW, NOW)
    changed = load_to_bronze(records, metadata, BATCH_ID, NOW, NOW)
    assert changed is False, "Retry must preserve committed batch"
    run_dbt()
    publish(BATCH_ID)
    conn = warehouse_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM bronze.raw_crypto_tickers WHERE batch_id=%s", (BATCH_ID,))
            assert cur.fetchone()[0] == 3
            cur.execute("SELECT count(*) FROM ga.latest_tickers")
            assert cur.fetchone()[0] == 2
            cur.execute("SELECT volume_quote_24h FROM ga.market_overview WHERE batch_id=%s AND quote_asset='USDT'", (BATCH_ID,))
            assert cur.fetchone()[0] == 1000, "Never sum BTC and USDT volumes"
            cur.execute("SELECT extract(milliseconds FROM snapshot_timestamp)::numeric % 1000 FROM silver.stg_crypto_tickers LIMIT 1")
            assert cur.fetchone()[0] == 123, "Preserve milliseconds"
            cur.execute("SELECT batch_id FROM ga.publication_status")
            previous = cur.fetchone()[0]
        try:
            publish("fixture__does_not_exist")
        except ValueError:
            pass
        else:
            raise AssertionError("Uncommitted batch must fail publication")
        with conn.cursor() as cur:
            cur.execute("SELECT batch_id FROM ga.publication_status")
            assert cur.fetchone()[0] == previous, "Failed publication must retain previous release"
    finally:
        conn.close()
    # Force a failure after publication has begun, rather than just before it starts.
    second_batch = "fixture__second"
    later = NOW + timedelta(seconds=1)
    load_to_bronze(records, metadata, second_batch, later, later)
    run_dbt(second_batch)
    conn = warehouse_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("ALTER TABLE ga.symbol_history ADD CONSTRAINT smoke_failure CHECK (batch_id <> 'fixture__second') NOT VALID")
        try:
            publish(second_batch)
        except psycopg2.errors.CheckViolation:
            pass
        else:
            raise AssertionError("Expected a mid-publication constraint failure")
        with conn.cursor() as cur:
            cur.execute("SELECT DISTINCT batch_id FROM ga.latest_tickers")
            assert cur.fetchall() == [(BATCH_ID,)], "Earlier copied tables must roll back too"
            cur.execute("SELECT batch_id FROM ga.publication_status")
            assert cur.fetchone()[0] == BATCH_ID
        with conn:
            with conn.cursor() as cur:
                cur.execute("ALTER TABLE ga.symbol_history DROP CONSTRAINT smoke_failure")
    finally:
        conn.close()
    publish(second_batch)
    print("PASS: idempotency, coverage, quote isolation, milliseconds, preflight and mid-transaction rollback")


if __name__ == "__main__":
    main()
