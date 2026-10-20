# 🚀 Crypto Market Data Automated ELT Pipeline (Medallion Architecture)

[![Airflow](https://img.shields.io/badge/Orchestration-Apache%20Airflow%202.8-017CEE?style=flat&logo=Apache%20Airflow&logoColor=white)](https://airflow.apache.org/)
[![dbt](https://img.shields.io/badge/Transform-dbt--core%201.11-FF694B?style=flat&logo=dbt&logoColor=white)](https://www.getdbt.com/)
[![PostgreSQL](https://img.shields.io/badge/Warehouse-PostgreSQL%2015-336791?style=flat&logo=PostgreSQL&logoColor=white)](https://www.postgresql.org/)
[![Docker](https://img.shields.io/badge/Containerization-Docker%20Compose-2496ED?style=flat&logo=Docker&logoColor=white)](https://www.docker.com/)
[![Python](https://img.shields.io/badge/Python-3.10-3776AB?style=flat&logo=python&logoColor=white)](https://www.python.org/)

Hệ thống Data Pipeline tự động thu thập dữ liệu biến động giá thị trường tiền điện tử từ Binance REST API, lưu trữ và mô hình hóa theo kiến trúc **Medallion (Bronze - Silver - Gold)** trên kho dữ liệu PostgreSQL, thực hiện kiểm định chất lượng tự động với **dbt-core** và điều phối workflow định kỳ bằng **Apache Airflow**.

---

## 📑 Mục lục
- [Kiến trúc hệ thống](#-kiến-trúc-hệ-thống-architecture)
- [Điểm nổi bật về mặt kỹ thuật](#-điểm-nổi-bật-về-mặt-kỹ-thuật-key-engineering-highlights)
- [Mô hình hóa dữ liệu (Star Schema)](#-mô-hình-hóa-dữ-liệu-star-schema)
- [Tech Stack](#-công-nghệ-sử-dụng-tech-stack)
- [Cấu trúc thư mục](#-cấu-trúc-thư-mục-project-structure)
- [Hướng dẫn triển khai cục bộ (Local Setup)](#-hướng-dẫn-triển-khai-cục-bộ-local-setup)
- [Kiểm thử & Vận hành thủ công (CLI)](#-kiểm-thử--vận-hành-thủ-công-cli)
- [Tác giả](#-tác-giả)

---

## 🏛️ Kiến trúc hệ thống (Architecture)

Quy trình xử lý dữ liệu được thiết kế theo luồng ELT chuẩn hóa với các tầng phân định ranh giới rõ ràng:

```
flowchart TD
    %% Source
    API["🌐 Binance Public REST API<br/>(24h Ticker Watchlist)"]

    %% Python Ingestion
    subgraph Ingestion ["Ingestion Step"]
        PY["🐍 Python Ingestion Script<br/>(Requests + Psycopg2)<br/><i>Idempotent UPSERT (ON CONFLICT)</i>"]
    end

    %% PostgreSQL Data Warehouse
    subgraph DWH ["PostgreSQL 15 Data Warehouse (crypto_dw)"]
        
        subgraph Bronze ["BRONZE SCHEMA"]
            B1[("bronze.raw_crypto_tickers<br/>• Raw JSONB payload<br/>• ingested_at metadata")]
        end

        subgraph Silver ["SILVER SCHEMA"]
            S1[("silver.stg_crypto_tickers<br/>• Parse JSON (->>)<br/>• Strict Type Casting<br/>• Filter null/negative prices")]
        end

        subgraph Gold ["GOLD SCHEMA (Star Schema)"]
            direction TB
            G_DIM[("gold.dim_tokens<br/><i>Dimension Table</i>")]
            G_FACT[("gold.fact_market_metrics<br/><i>Fact Table (MD5 Surrogate Key)</i>")]
            G_DIM -.->|1 : N| G_FACT
        end
    end

    %% Quality Gates / Downstream
    subgraph QualityGate ["Data Quality Gate"]
        TEST{"⚡ dbt test<br/>(Circuit Breaker)"}
        ALERT["🛑 Halt Downstream & Alert<br/>(Exit Code 1)"]
        SUCCESS["✅ Ready for BI / Serving<br/>(Validated Data Mart)"]
    end

    %% Orchestration Flow
    API -->|HTTP GET| PY
    PY -->|UPSERT batch| B1
    B1 -->|"dbt run --select silver"| S1
    S1 -->|"dbt run --select gold"| Gold
    Gold -->|"dbt test"| TEST
    TEST -->|Fail: Unique / Not Null / FK| ALERT
    TEST -->|Pass| SUCCESS

    %% Styling
    classDef source fill:#f9f9f9,stroke:#333,stroke-width:1px;
    classDef bronze fill:#e0a96d,stroke:#7c4700,stroke-width:1px,color:#000;
    classDef silver fill:#dcdde1,stroke:#718093,stroke-width:1px,color:#000;
    classDef gold fill:#f5cd79,stroke:#e15f41,stroke-width:1px,color:#000;
    classDef breaker fill:#ff7675,stroke:#d63031,stroke-width:1px,color:#fff;
    classDef success fill:#55efc4,stroke:#00b894,stroke-width:1px,color:#000;

    class API source;
    class B1 bronze;
    class S1 silver;
    class G_DIM,G_FACT gold;
    class ALERT breaker;
    class SUCCESS success;

```

---

## 💡 Điểm nổi bật về mặt kỹ thuật (Key Engineering Highlights)

### 1. Data Ingestion & Tính Idempotency (Bronze Layer)
- Sử dụng Python trích xuất dữ liệu snapshot 24h ticker của danh mục Watchlist từ Binance API.
- Lưu trữ toàn bộ payload dưới dạng kiểu `JSONB` trong PostgreSQL kèm metadata thời gian (`ingested_at`).
- Triển khai cơ chế **UPSERT** (`INSERT ... ON CONFLICT (symbol, ingested_at) DO UPDATE`) giúp pipeline có tính **Idempotent** (khi chạy lại hoặc retry không sinh dữ liệu trùng lặp).

### 2. Chuẩn hóa & Làm sạch dữ liệu (Silver Layer)
- Tận dụng toán tử `->>` của PostgreSQL trong model `dbt` để trích xuất các trường lồng nhau từ JSON thô.
- Ép kiểu dữ liệu nghiêm ngặt (`NUMERIC` cho giá/volume, `BIGINT` cho số lượng giao dịch, `TIMESTAMPTZ` cho thời gian đóng nến).
- Quy chuẩn hóa tên cột theo định dạng `snake_case` và loại bỏ các bản ghi không hợp lệ hoặc giá âm/null.

### 3. Mô hình hóa dữ liệu (Gold Layer - Star Schema)
- Tách biệt rõ ràng giữa thực thể mô tả (Dimension) và số đo theo thời gian (Fact).
- Sinh Surrogate Key bằng kỹ thuật băm `MD5(CONCAT(symbol, '_', snapshot_timestamp, '_', ingested_at))` đảm bảo tính duy nhất tuyệt đối cho từng snapshot của mỗi đồng coin.

### 4. Data Quality Testing & Circuit Breaker
- Cấu hình kiểm thử tự động với `dbt test` kiểm tra tính toàn vẹn:
  - `unique` & `not_null` cho các cột Surrogate Key.
  - `relationships` kiểm tra ràng buộc toàn vẹn tham chiếu (Referential Integrity) giữa bảng Fact và Dimension.
- Đóng vai trò như một **Circuit Breaker**: nếu dữ liệu không đạt chuẩn kiểm thử, task `dbt test` sẽ trả về lỗi (`exit code 1`), khiến Airflow dừng luồng xử lý downstream và gửi cảnh báo ngay lập tức.

### 5. Điều phối tự động hóa (Airflow Workflow)
- Toàn bộ pipeline được cấu hình chạy tự động theo chu kỳ mỗi giờ (`@hourly`).
- Thiết lập cơ chế tự động phục hồi lỗi (`retries=2`, `retry_delay=2m`).

---

## 📊 Mô hình hóa dữ liệu (Star Schema)

```
erDiagram
    gold_dim_tokens ||--o{ gold_fact_market_metrics : "has metrics (1:N)"

    gold_dim_tokens {
        VARCHAR_32 token_key PK "MD5 Hash Surrogate Key"
        VARCHAR_20 symbol "Trading pair (e.g. BTCUSDT)"
        VARCHAR_20 base_asset "Base currency (e.g. BTC)"
        VARCHAR_20 quote_asset "Quote currency (e.g. USDT)"
    }

    gold_fact_market_metrics {
        VARCHAR_32 metric_key PK "MD5(symbol + snapshot + ingested_at)"
        VARCHAR_32 token_key FK "References gold.dim_tokens"
        NUMERIC current_price "Current ticker price"
        NUMERIC price_change_24h "24h price absolute change"
        NUMERIC price_change_pct "24h price percentage change"
        NUMERIC high_price_24h "24h highest price"
        NUMERIC low_price_24h "24h lowest price"
        NUMERIC volume_base_24h "24h volume in base asset"
        NUMERIC volume_quote_24h "24h volume in quote asset"
        BIGINT trade_count_24h "Total trade counts"
        TIMESTAMPTZ snapshot_timestamp "Ticker close time"
        TIMESTAMPTZ ingested_at "Ingestion execution time"
    }

```

---

## 🛠️ Công nghệ sử dụng (Tech Stack)

| Hạng mục | Công nghệ | Chi tiết sử dụng |
| :--- | :--- | :--- |
| **Ngôn ngữ** | Python 3.10, SQL | Viết script ingestion, dbt models, custom test |
| **Orchestration** | Apache Airflow 2.8.1 | LocalExecutor, BashOperator, DAG scheduling |
| **Transform & Test** | dbt-core 1.11 | `dbt-postgres` adapter, models, data quality testing |
| **Data Warehouse** | PostgreSQL 15 | Cơ sở dữ liệu lưu trữ 3 tầng schemas |
| **Hạ tầng & Đóng gói**| Docker & Docker Compose | Container hóa toàn bộ service môi trường độc lập |
| **Thư viện Python** | `requests`, `psycopg2-binary` | Kết nối API, execute batch insert PostgreSQL |

---

## 📂 Cấu trúc thư mục (Project Structure)

```text
crypto-etl-pipeline/
├── dags/
│   └── crypto_elt_pipeline.py            # Airflow DAG định nghĩa lịch chạy & task dependencies
├── dbt_project/
│   ├── models/
│   │   ├── sources.yml                   # Khai báo Bronze source tables
│   │   ├── silver/
│   │   │   └── stg_crypto_tickers.sql    # Chuyển đổi JSON thô thành bảng quan hệ
│   │   └── gold/
│   │       ├── dim_tokens.sql            # Dimension Table (Metadata token)
│   │       ├── fact_market_metrics.sql   # Fact Table (Số đo thị trường theo thời gian)
│   │       └── schema.yml                # Data tests: unique, not_null, foreign keys
│   ├── dbt_project.yml                   # Cấu hình chính của dbt project
│   └── profiles.yml                      # Cấu hình kết nối tới Postgres Warehouse
├── scripts/
│   ├── init_warehouse.sql                # SQL script khởi tạo 3 schema & bảng Bronze
│   └── ingest_market_data.py             # Script trích xuất Binance API & nạp vào Bronze
├── docker-compose.yml                    # Thiết lập cụm Airflow & Postgres Warehouse
├── requirements.txt                      # Python dependencies
└── README.md                             # Tài liệu kỹ thuật dự án
```

---

## 🚀 Hướng dẫn triển khai cục bộ (Local Setup)

### 1. Yêu cầu hệ thống
- Đã cài đặt [Docker](https://docs.docker.com/get-docker/) & Docker Compose.
- Khuyến nghị RAM trống tối thiểu: 4GB.

### 2. Khởi chạy toàn bộ hệ thống
Clone repository và kích hoạt container bằng một lệnh duy nhất:

```bash
# Clone repository
git clone https://github.com/dungngoo1/crypto-etl-pipeline.git
cd crypto-etl-pipeline

# Khởi chạy Docker Compose
docker compose up -d
```

### 3. Thông tin kết nối & Dịch vụ

| Dịch vụ | URL / Địa chỉ | Tài khoản / Thông số |
| :--- | :--- | :--- |
| **Airflow Web UI** | [http://localhost:8080](http://localhost:8080) | Username: `admin` \| Password: `admin` |
| **Postgres Warehouse** | `localhost:5433` | DB: `crypto_dw` \| User: `dw_user` \| Pass: `dw_password` |

---

## 🧪 Kiểm thử & Vận hành thủ công (CLI)

Bạn có thể kích chạy độc lập từng bước kiểm thử thông qua terminal:

**1. Kích chạy Python Ingestion (Tầng Bronze):**
```bash
docker exec -it crypto-etl-pipeline-airflow-scheduler-1 python /opt/airflow/scripts/ingest_market_data.py
```

**2. Chạy dbt Transformation (Tầng Silver & Gold):**
```bash
docker exec -it crypto-etl-pipeline-airflow-scheduler-1 bash -c "cd /opt/airflow/dbt_project && dbt run --profiles-dir ."
```

**3. Chạy Data Quality Tests (Circuit Breaker):**
```bash
docker exec -it crypto-etl-pipeline-airflow-scheduler-1 bash -c "cd /opt/airflow/dbt_project && dbt test --profiles-dir ."
```

---

## 👤 Tác giả

- **Ngô Quốc Dũng** - Fresher Data Engineer
- **GitHub:** [@dungngoo1](https://github.com/dungngoo1)
- **LinkedIn:** [quocdungngo](https://linkedin.com/in/quocdungngo/)
- **Email:** dung.nq0410@gmail.com



