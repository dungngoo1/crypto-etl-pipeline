# Crypto Market Data Automated ELT Pipeline (Medallion Architecture)

[![Airflow](https://img.shields.io/badge/Orchestration-Apache%20Airflow%202.8-017CEE?style=flat&logo=Apache%20Airflow&logoColor=white)](https://airflow.apache.org/)
[![dbt](https://img.shields.io/badge/Transform-dbt--core%201.11-FF694B?style=flat&logo=dbt&logoColor=white)](https://www.getdbt.com/)
[![PostgreSQL](https://img.shields.io/badge/Warehouse-PostgreSQL%2015-336791?style=flat&logo=PostgreSQL&logoColor=white)](https://www.postgresql.org/)
[![Docker](https://img.shields.io/badge/Containerization-Docker%20Compose-2496ED?style=flat&logo=Docker&logoColor=white)](https://www.docker.com/)

Hệ thống Data Pipeline tự động thu thập dữ liệu biến động giá thị trường tiền điện tử từ Binance REST API, lưu trữ và mô hình hóa theo kiến trúc **Medallion (Bronze - Silver - Gold)** trên kho dữ liệu PostgreSQL, thực hiện kiểm định chất lượng tự động với **dbt-core** và điều phối định kỳ bằng **Apache Airflow**.

---

## 🏛️ Kiến trúc dữ liệu (Data Architecture)

Dự án áp dụng mô hình luồng dữ liệu phân tầng nhằm đảm bảo tính toàn vẹn, khả năng mở rộng và chất lượng dữ liệu:

┌─────────────────────────────────┐
│     Binance Public REST API     │
└────────────────┬────────────────┘
│
│ (1) Ingestion Script (Requests + Psycopg2)
│     Cơ chế Idempotent UPSERT (ON CONFLICT DO UPDATE)
▼
┌─────────────────────────────────┐
│         BRONZE SCHEMA           │
│   (bronze.raw_crypto_tickers)   │ -> Dữ liệu thô nguyên bản JSONB + Metadata
└────────────────┬────────────────┘
│
│ (2) dbt run --select silver
│     Parse JSON (->>), ép kiểu dữ liệu, snake_case
▼
┌─────────────────────────────────┐
│         SILVER SCHEMA           │
│   (silver.stg_crypto_tickers)   │ -> Bảng dữ liệu sạch, chuẩn hóa cấu trúc
└────────────────┬────────────────┘
│
│ (3) dbt run --select gold
│     Surrogate Key Hash (MD5), Dimensional Modeling
▼
┌─────────────────────────────────┐
│          GOLD SCHEMA            │
│ ┌─────────────────────────────┐ │
│ │  dim_tokens (Dimension)     │ │ -> Phục vụ phân tích theo danh mục
│ └──────────────┬──────────────┘ │
│                │ 1:N            │
│ ┌──────────────▼──────────────┐ │
│ │ fact_market_metrics (Fact)  │ │ -> Lưu vết chuỗi thời gian biến động giá
│ └─────────────────────────────┘ │
└────────────────┬────────────────┘
│
│ (4) dbt test
▼
┌─────────────────────────────────┐
│         CIRCUIT BREAKER         │ -> Kiểm tra Unique, Not Null, Referential
│      (Data Quality Gates)       │    Integrity; ngắt pipeline nếu sai lệch
└─────────────────────────────────┘



---

## 💡 Điểm nổi bật về mặt kỹ thuật (Key Engineering Highlights)

- **Idempotency & Data Ingestion (Bronze Layer):** 
  Script Python sử dụng câu lệnh `INSERT ... ON CONFLICT (symbol, ingested_at) DO UPDATE` để đảm bảo tính Idempotent khi pipeline thực thi lại (retry hoặc backfill) mà không tạo ra bản ghi nhân bản hay sai lệch dữ liệu.
- **Data Transformation & Modeling (Silver & Gold Layers):** 
  - **Silver:** Bóc tách JSON payload sang các trường dữ liệu quan hệ với kiểu chuẩn (`NUMERIC`, `BIGINT`, `TIMESTAMPTZ`), lọc bỏ dữ liệu rác.
  - **Gold:** Xây dựng mô hình hình sao (Star Schema). Tạo Surrogate Key cho Dimension và Fact bằng hàm băm `MD5` kết hợp chuỗi định danh duy nhất (`symbol`, `snapshot_timestamp`, `ingested_at`).
- **Data Quality & Circuit Breaker (dbt test):** 
  Thiết lập bộ kiểm thử tự động gồm các ràng buộc `unique`, `not_null` cho Primary Keys và `relationships` kiểm tra khóa ngoại giữa Fact và Dimension. Nếu bất kỳ bài kiểm tra nào thất bại, `dbt test` trả về exit code `1`, kích hoạt cơ chế Circuit Breaker dừng toàn bộ downstream pipeline trong Airflow để bảo vệ kho dữ liệu.
- **Workflow Orchestration (Apache Airflow):** 
  Đóng gói toàn bộ cụm dịch vụ qua Docker Compose; điều phối luồng tuần tự (`Bronze >> Silver >> Gold >> Data Quality Test`) theo lịch trình `@hourly` với cơ chế retry tự động (`retries=2`, `retry_delay=2m`).

---

## 🛠️ Công nghệ sử dụng (Tech Stack)

| Hạng mục | Công nghệ |
| :--- | :--- |
| **Ngôn ngữ** | Python 3.10, SQL |
| **Orchestration** | Apache Airflow 2.8.1 (LocalExecutor) |
| **Transformation & Testing** | dbt-core 1.11 (Adapter: dbt-postgres) |
| **Data Warehouse** | PostgreSQL 15 |
| **Containerization** | Docker, Docker Compose |
| **Thư viện chính** | `requests`, `psycopg2-binary`, `execute_values` |

---

## 📂 Cấu trúc thư mục (Directory Structure)

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
├── requirements.txt                      # Python dependencies nội bộ
└── README.md


🚀 Hướng dẫn cài đặt & Khởi chạy (Local Setup)
1. Yêu cầu tiên quyết
Đã cài đặt Docker và Docker Compose.

RAM trống tối thiểu: 4GB.

2. Khởi động hệ thống
Mở terminal tại thư mục gốc và chạy lệnh:

Bash
docker compose up -d
Docker sẽ tự động tải các container, chạy script khởi tạo Database, cài đặt dbt-postgres và kích hoạt Webserver/Scheduler của Airflow.

3. Thông tin kết nối & Dịch vụ
Apache Airflow Web UI:

URL: http://localhost:8080

Tài khoản: admin | Mật khẩu: admin

PostgreSQL Warehouse:

Host: localhost | Cổng: 5433

Database: crypto_dw

User: dw_user | Mật khẩu: dw_password

Schemas: bronze, silver, gold

🧪 Vận hành & Kiểm thử thủ công (CLI Testing)
Nếu muốn kích chạy từng công đoạn trực tiếp qua Command Line:

Chạy script Ingestion nạp tầng Bronze:

Bash
docker exec -it crypto-etl-pipeline-airflow-scheduler-1 python /opt/airflow/scripts/ingest_market_data.py
Chạy transform tầng Silver & Gold qua dbt:

Bash
docker exec -it crypto-etl-pipeline-airflow-scheduler-1 bash -c "cd /opt/airflow/dbt_project && dbt run --profiles-dir ."
Chạy kiểm định chất lượng dữ liệu (dbt test):

Bash
docker exec -it crypto-etl-pipeline-airflow-scheduler-1 bash -c "cd /opt/airflow/dbt_project && dbt test --profiles-dir ."
👤 Tác giả
Ngô Quốc Dũng - Fresher Data Engineer

GitHub: @dungngoo1

LinkedIn: quocdungngo

Email: dung.nq0410@gmail.com