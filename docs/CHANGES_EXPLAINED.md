# Các thay đổi và lý do

Đối chiếu README/code gốc tại commit `bdbce1cc48c3cd5eb23c6c5ac30261876f6838bc`.

| File / vị trí | Trước | Sau | Vì sao |
|---|---|---|---|
| scripts/ingest_market_data.py | Lọc WATCHLIST | Giữ toàn bộ ticker response | Đúng phạm vi all tickers bạn yêu cầu |
| scripts/ingest_market_data.py | Không lấy exchangeInfo | Lưu metadata từng cặp cùng raw ticker | All tickers có nhiều quote; không thể giả định USDT |
| scripts/ingest_market_data.py + init_warehouse.sql | Khóa symbol + datetime.now | Khóa symbol + batch_id; manifest transaction; batch immutable | Retry không sinh snapshot trùng hoặc thay snapshot đã commit |
| scripts/ingest_market_data.py | Kết quả rỗng chỉ warning | Fail rỗng/trùng symbol/thiếu active spot ticker | Tránh báo thành công giả với dữ liệu cũ |
| stg_crypto_tickers.sql | Loại giá <= 0 khỏi bảng | Giữ toàn bộ và gắn exclusion_reason | Cặp inactive có thể giá 0; cần audit đủ all tickers |
| stg_crypto_tickers.sql | Chia BIGINT / 1000 | Chia double / 1000.0 | Không mất mili giây |
| dim_tokens.sql | REPLACE USDT, quote cố định | Đọc base/quote từ exchange metadata | Hỗ trợ ETHBTC, BTCUSDC, quote khác và symbol Unicode |
| fact_market_metrics.sql | Khóa chứa thời gian nạp | Khóa symbol + batch_id theo định dạng xác định | Giữ grain ổn định; test unique tiếp tục bắt buộc |
| models/ga/* | Chưa có | Overview theo batch/quote, latest tickers, symbol history | Cung cấp dữ liệu phân tích rõ grain và đơn vị |
| scripts/publish_ga.py | Gold ghi trực tiếp trước test | GA candidate được test rồi copy trong transaction | BI giữ release cũ nếu build/test/publication lỗi |
| DAG | dbt run rồi dbt test cuối | source freshness → dbt build → publish GA | Kiểm tra trở thành điều kiện thật trước serving |
| DAG | Có thể chồng DAG run | max_active_runs=1 | Tránh rebuild cùng bảng/artifact đồng thời |
| Dockerfile | pip mỗi lần container khởi động | Cài lúc build, dbt venv riêng | Khởi động ổn định hơn và tách dependency Airflow/dbt |
| requirements-dbt.txt | File yêu cầu và Compose không khớp | Ghim core 1.12.5 / adapter 1.11.0 | Cùng phiên bản đã dùng kiểm thử SQL local |
| docker-compose.yml | Thiếu metadata volume | airflow_metadata named volume | Giữ database Airflow qua các lần down/up |
| docker-compose.yml + profiles.yml | Credentials hard-code | .env.example / environment | Cấu hình tập trung, không commit secrets thật |
| docker-compose.yml | Bind toàn bộ interfaces | Bind localhost | Phù hợp demo local |
| migrate_v2.sql | Chưa có đường nâng cấp | Giữ bảng raw cũ dạng legacy | Không xóa lịch sử, không gán giả metadata cho dữ liệu cũ |
| README | Ảnh trong code fence | ER diagram Mermaid + preview có nhãn | Hiển thị trực tiếp và đúng kiến trúc mới |
| README | Cam kết alert, uniqueness tuyệt đối | Mô tả task failure, MD5 và giới hạn thật | Tài liệu phải đúng hành vi triển khai |
| tests + CI | Chưa có CI | Unit + PostgreSQL integration + lint | Kiểm chứng dữ liệu, retry và publication |
| powerbi/* | Chưa có report | Hai trang PBIP/PBIR và semantic model | Có source dashboard chỉnh sửa được, không chỉ mô tả ý tưởng |

## Những quyết định có chủ đích

**GA** là extension phục vụ phân tích sau Gold; schema `ga_candidate` chỉ là khu vực build/test kỹ thuật.

**Chưa làm incremental:** full rebuild dễ kiểm tra trong demo, nhưng phải theo dõi tăng trưởng dữ liệu. Khi chuyển incremental, cần xử lý retry, batch đến muộn, retention và consistency giữa dimension/fact.

**Không làm mart_daily_ohlc:** endpoint hiện tại là ticker rolling 24h. Dựng OHLC ngày từ vài snapshot giờ sẽ tạo độ chính xác giả. Muốn OHLC ngày cần ingest kline riêng.

**Không thêm Slack/SMTP giả:** hiện task failure và logs là cơ chế quan sát. Muốn alert thật cần destination và credentials do chủ repo cấu hình.

**Không cộng volume khác quote:** dashboard lọc một quote; chưa có tỷ giá quy đổi và không gọi tổng volume là USD.

**Tên dim_tokens được giữ** để giảm đổi tên trong repo; bảng thực tế có grain là trading pair, đã ghi rõ trong dictionary.

**Nâng cấp database không tự nhập lịch sử legacy vào GA:** legacy chỉ có watchlist và thiếu metadata. Bảng cũ còn nguyên để audit; một migration lịch sử có kiểm chứng là công việc riêng.

## Cần xác nhận trên máy triển khai

- Docker build và Airflow UI với image Linux đã chọn.
- Mở project trong Power BI Desktop, nhập credentials, Refresh và kiểm tra DAX/M/render.
- Để pipeline chạy nhiều giờ để có đường lịch sử thật.
- Nếu triển khai production: nâng cấp Airflow, khóa dependency bắc cầu, user BI chỉ đọc, secrets manager, retention/partitioning, monitoring và notification thật.

Ảnh rời ở root được chuyển vào `docs/legacy-star-schema.png` để lưu tham khảo lịch sử; sơ đồ hiện hành nằm trong README.

Dockerfile đặt `PIP_USER=false` riêng khi cài dbt, vì image Airflow bật user install mặc định. Logs Airflow được giữ trong named volume riêng.
