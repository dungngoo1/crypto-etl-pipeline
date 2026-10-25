"""Publish tested GA candidates transactionally; failure preserves the previous release."""
import argparse
import logging

from psycopg2 import sql

from ingest_market_data import warehouse_connection

MARTS = ("market_overview", "latest_tickers", "symbol_history")


def publish(batch_id):
    conn = warehouse_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("SELECT pg_advisory_xact_lock(8172402)")
                cur.execute("SELECT captured_at FROM bronze.ingestion_batches WHERE batch_id = %s", (batch_id,))
                batch = cur.fetchone()
                if not batch:
                    raise ValueError(f"Uncommitted batch: {batch_id}")
                cur.execute("SELECT DISTINCT batch_id FROM ga_candidate.latest_tickers")
                if cur.fetchall() != [(batch_id,)]:
                    raise ValueError("Candidate is empty or belongs to a different batch")
                for name in MARTS:
                    target = sql.Identifier("ga", name)
                    source = sql.Identifier("ga_candidate", name)
                    cur.execute(sql.SQL("CREATE TABLE IF NOT EXISTS {} (LIKE {} INCLUDING ALL)").format(target, source))
                    # DELETE preserves old MVCC snapshots for concurrent BI readers.
                    cur.execute(sql.SQL("DELETE FROM {}").format(target))
                    cur.execute(sql.SQL("INSERT INTO {} SELECT * FROM {}").format(target, source))
                cur.execute("""
                    INSERT INTO ga.publication_status(singleton, batch_id, captured_at)
                    VALUES (TRUE, %s, %s)
                    ON CONFLICT(singleton) DO UPDATE SET batch_id = EXCLUDED.batch_id,
                      captured_at = EXCLUDED.captured_at, published_at = CURRENT_TIMESTAMP
                """, (batch_id, batch[0]))
        logging.info("Published GA batch %s", batch_id)
    finally:
        conn.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch-id", required=True)
    publish(parser.parse_args().batch_id)
