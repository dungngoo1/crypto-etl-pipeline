import os
import json
import logging
import requests
import psycopg2
from psycopg2.extras import execute_values
from datetime import datetime, timezone

# 1. Cấu hình Logging để Airflow bắt log rõ ràng
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

# 2. Lấy thông tin kết nối từ biến môi trường (hoặc fallback về mặc định)
DB_HOST = os.getenv("WAREHOUSE_HOST", "postgres-warehouse")
DB_PORT = os.getenv("WAREHOUSE_PORT", "5432")
DB_NAME = os.getenv("WAREHOUSE_DB", "crypto_dw")
DB_USER = os.getenv("WAREHOUSE_USER", "dw_user")
DB_PASSWORD = os.getenv("WAREHOUSE_PASSWORD", "dw_password")

# Danh sách các cặp token cần theo dõi
WATCHLIST = [
    "BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "ADAUSDT", "DOGEUSDT",
    "XRPUSDT", "AVAXUSDT", "LINKUSDT", "DOTUSDT", "NEARUSDT", "MATICUSDT",
    "LTCUSDT", "UNIUSDT", "ATOMUSDT", "APTUSDT", "SUIUSDT", "ARBUSDT", "OPUSDT"
]

def fetch_ticker_data():
    """Trích xuất (Extract) dữ liệu 24h ticker từ Binance Public API."""
    url = "https://api.binance.com/api/v3/ticker/24hr"
    logger.info("Đang gọi REST API: %s", url)
    
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        # Lọc đúng các đồng trong watchlist
        filtered = [item for item in data if item.get("symbol") in WATCHLIST]
        logger.info("Lấy thành công %d token từ API", len(filtered))
        return filtered
    except Exception as e:
        logger.error("Lỗi khi fetch API: %s", str(e))
        raise

def load_to_bronze(records):
    """Nạp (Load) dữ liệu nguyên bản (JSONB) vào schema Bronze với cơ chế Idempotent UPSERT."""
    if not records:
        logger.warning("Không có dữ liệu để load!")
        return

    # Chuẩn bị dữ liệu để insert batch
    ingested_at = datetime.now(timezone.utc)
    data_to_insert = [
        (
            item["symbol"],
            json.dumps(item), # Lưu toàn bộ raw JSON payload
            ingested_at
        )
        for item in records
    ]

    # Query nạp dữ liệu: Idempotent bằng ON CONFLICT DO UPDATE
    upsert_query = """
        INSERT INTO bronze.raw_crypto_tickers (symbol, raw_payload, ingested_at)
        VALUES %s
        ON CONFLICT (symbol, ingested_at) 
        DO UPDATE SET raw_payload = EXCLUDED.raw_payload;
    """

    conn = None
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD
        )
        with conn.cursor() as cur:
            execute_values(cur, upsert_query, data_to_insert)
            conn.commit()
            logger.info("Đã nạp thành công %d bản ghi vào bronze.raw_crypto_tickers lúc %s", len(data_to_insert), ingested_at)
    except Exception as e:
        logger.error("Lỗi khi nạp dữ liệu vào Bronze: %s", str(e))
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    logger.info("Bắt đầu Ingestion Pipeline...")
    tickers = fetch_ticker_data()
    load_to_bronze(tickers)
    logger.info("Hoàn tất Ingestion Pipeline!")