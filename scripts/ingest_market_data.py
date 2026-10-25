"""Capture every returned Binance ticker atomically, once per logical batch."""
import argparse
from datetime import datetime, timezone
import logging
import os

import psycopg2
from psycopg2.extras import Json, execute_values
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def warehouse_connection():
    return psycopg2.connect(
        host=os.getenv("WAREHOUSE_HOST", "postgres-warehouse"),
        port=os.getenv("WAREHOUSE_PORT", "5432"),
        dbname=os.getenv("WAREHOUSE_DB", "crypto_dw"),
        user=os.getenv("WAREHOUSE_USER", "dw_user"),
        password=os.environ["WAREHOUSE_PASSWORD"], connect_timeout=15,
    )


def api_session():
    session = requests.Session()
    retry = Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504],
                  allowed_methods=["GET"], respect_retry_after_header=True)
    session.mount("https://", HTTPAdapter(max_retries=retry))
    return session


def fetch_snapshot(session):
    base = os.getenv("BINANCE_BASE_URL", "https://api.binance.com").rstrip("/")
    # No symbol/symbols parameter and no watchlist.
    response = session.get(f"{base}/api/v3/ticker/24hr", timeout=(10, 60))
    response.raise_for_status()
    tickers = response.json()
    captured_at = datetime.now(timezone.utc)
    if not isinstance(tickers, list) or not tickers:
        raise ValueError("Expected a nonempty array from ticker/24hr")
    symbols = [row.get("symbol") for row in tickers if isinstance(row, dict)]
    if len(symbols) != len(tickers) or any(not s for s in symbols):
        raise ValueError("Every ticker must have a symbol")
    if len(set(symbols)) != len(symbols):
        raise ValueError("Duplicate symbols in ticker response")
    response = session.get(f"{base}/api/v3/exchangeInfo", timeout=(10, 60))
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict) or not payload.get("symbols"):
        raise ValueError("Expected nonempty exchangeInfo.symbols")
    metadata = {row["symbol"]: row for row in payload["symbols"]}
    required = {s for s, row in metadata.items()
                if row.get("status") == "TRADING" and row.get("isSpotTradingAllowed", False)}
    missing = required - set(symbols)
    if missing:
        raise ValueError(f"Missing active spot tickers ({len(missing)}): {sorted(missing)[:20]}")
    logger.info("Captured %d tickers; %d active spot symbols expected", len(tickers), len(required))
    return tickers, metadata, captured_at


def load_to_bronze(records, metadata, batch_id, batch_timestamp, captured_at):
    if not records:
        raise ValueError("Refusing to load an empty snapshot")
    rows = [(item["symbol"], batch_id, batch_timestamp, captured_at,
             Json(item), Json(metadata.get(item["symbol"], {}))) for item in records]
    conn = warehouse_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("SELECT pg_advisory_xact_lock(8172401)")
                cur.execute("SELECT 1 FROM bronze.ingestion_batches WHERE batch_id = %s", (batch_id,))
                if cur.fetchone():
                    logger.info("Batch %s already committed; keeping original snapshot", batch_id)
                    return False
                execute_values(cur, """
                    INSERT INTO bronze.raw_crypto_tickers
                        (symbol, batch_id, batch_timestamp, ingested_at, raw_payload, metadata_payload)
                    VALUES %s
                """, rows, page_size=1000)
                cur.execute("""
                    INSERT INTO bronze.ingestion_batches
                        (batch_id, batch_timestamp, captured_at, ticker_count)
                    VALUES (%s, %s, %s, %s)
                """, (batch_id, batch_timestamp, captured_at, len(records)))
        logger.info("Committed batch %s: %d tickers", batch_id, len(records))
        return True
    finally:
        conn.close()


def parse_timestamp(value):
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None:
        raise ValueError("Timestamp must include a timezone")
    return result.astimezone(timezone.utc)


def main():
    now = datetime.now(timezone.utc)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch-id", default=f"manual__{now.isoformat()}")
    parser.add_argument("--batch-timestamp", default=now.isoformat())
    args = parser.parse_args()
    timestamp = parse_timestamp(args.batch_timestamp)
    conn = warehouse_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM bronze.ingestion_batches WHERE batch_id = %s", (args.batch_id,))
            if cur.fetchone():
                logger.info("Batch already committed: %s", args.batch_id)
                return
    finally:
        conn.close()
    with api_session() as session:
        records, metadata, captured_at = fetch_snapshot(session)
    load_to_bronze(records, metadata, args.batch_id, timestamp, captured_at)


if __name__ == "__main__":
    main()
