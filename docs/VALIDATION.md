# Kết quả kiểm chứng

Lần kiểm tra ngày **25/10/2026**. Repo nền: `bdbce1cc48c3cd5eb23c6c5ac30261876f6838bc`.

## Môi trường đã dùng

PostgreSQL **15.6** chạy riêng trên localhost trong workspace, Python **3.13**, dbt-core **1.12.5**, dbt-postgres **1.11.0**. Không dùng database dự án đang chạy trên máy người dùng.

Image triển khai vẫn dùng Python 3.10 / Airflow 2.8.1 như README. Do Docker Engine chưa chạy được trong phiên thực hiện, **chưa xác nhận Docker build và vận hành đầy đủ Airflow trong container**. PostgreSQL/SQL được kiểm tra trực tiếp thay thế, không được coi là bằng chứng Airflow UI đã chạy xanh.

## Kết quả

| Hạng mục | Kết quả |
|---|---|
| Python unit tests | 5/5 pass: all quotes/inactive retained, payload rỗng/error, duplicate, missing active ticker, timezone |
| Python syntax + lint | compileall pass; Ruff E9/F63/F7/F82 pass |
| Docker Compose | `docker compose --env-file .env.example config --quiet` pass |
| dbt với fixture | 6 model + 35 data test pass, hai batch giả lập |
| Retry cùng batch | Không tăng số raw rows, snapshot đã commit giữ nguyên |
| Đơn vị volume | Fixture USDT=1000 và BTC=2 vẫn cho USDT=1000, không thành 1002 |
| Timestamp | Phần mili giây 123 được giữ sau transform |
| Publish lỗi trước khi ghi | Không thay release cũ |
| Publish lỗi giữa transaction | Cố tình vi phạm constraint ở bảng thứ ba; bảng đã ghi trước đó cũng rollback |
| Migration từ schema gốc | Hàng raw cũ được giữ trong bảng legacy, bảng mới sẵn sàng; chạy SQL lần hai thành công |
| Source freshness dữ liệu thật | Cả 2 source pass |
| dbt với dữ liệu thật | 6 model + 35 data test pass |
| Power BI source | 26 file PBIP/PBIR/JSON có schema đều pass schema Microsoft |
| Power BI bindings | Cột model khớp schema GA thật; 41 tham chiếu field trong visual hợp lệ |
| Power BI Desktop | Chưa render, chưa xác nhận DAX/M trong Desktop |
| GitHub Actions | Đã viết workflow; chưa chạy trên GitHub |

Migration được kiểm tra qua psycopg2 sau khi mở rộng directive `\ir init_warehouse.sql` thành nội dung file init. Chưa chạy psql trong container.

## Snapshot thật đã kiểm tra

Nguồn: Binance Spot `/api/v3/ticker/24hr` và `/api/v3/exchangeInfo`.

- Thời gian nhận ticker response: **2026-10-25 08:30:58 UTC / 15:30:58 UTC+7**.
- Raw tickers: **3.739**.
- Silver và Gold giữ đủ **3.739** hàng của batch.
- Đủ điều kiện phân tích: **1.382** cặp.
- Inactive: **2.353**; thiếu metadata: **3**; giá không dương: **1**.
- Trong nhóm USDT: **516** cặp đủ điều kiện tại snapshot này.
- Các con số chỉ mô tả lần chạy đó, không phải số ticker cố định.

Xem [summary.json](evidence/summary.json), [kết quả dbt live](evidence/live-test-results.json), [log build live](evidence/live-build.log), [log freshness](evidence/freshness.log), [kết quả fixture](evidence/fixture-test-results.json), [log integration](evidence/fixture-test.log).

CSV trong `docs/evidence/` là **export tĩnh của dữ liệu GA thật tại thời điểm nêu trên**. Chúng phục vụ kiểm chứng/preview; project Power BI kết nối PostgreSQL để refresh, không tự lấy dữ liệu mới từ những CSV này.

## Giới hạn và bước tiếp theo trên máy triển khai

1. Chạy Docker build/up, Trigger DAG và xác nhận bốn task thành công.
2. Mở `powerbi/CryptoMarket.pbip` bằng Power BI Desktop, nhập credentials PostgreSQL và Refresh.
3. Kiểm tra filter USDT/BTCUSDT, định dạng %, timestamp UTC và kết quả measure.
4. Để pipeline chạy qua nhiều giờ để có chuỗi thời gian thật.
5. Lên lịch Power BI refresh sau publish; các query Import độc lập có thể vắt qua hai release nếu refresh đúng lúc publish. Transaction SQL không biến nhiều query BI thành một transaction chung.

Ảnh dashboard-preview.png là bố cục dựng từ CSV query thật, không phải screenshot Power BI. Không tạo ảnh Airflow xanh hoặc history giả để minh họa.

## Phạm vi thay đổi

Sửa code và tài liệu trong bản clone local; chưa push, mở PR hoặc sửa repository trên GitHub.

## Bổ sung kiểm tra MCP / minh họa

MCP local 1.0.0 đã initialize và liệt kê 21 nhóm công cụ. ConnectBimFile mở được CryptoMarket: 4 bảng, 45 cột, 9 measures. Thử kết nối instance Desktop thất bại ở OpenAdomd; chưa refresh, chạy DAX hay render trong Desktop. Docker UI báo Engine running nhưng CLI bị permission denied. Xem [runtime guide](RUNTIME_AND_MCP.md). Hai hình kiến trúc/tech stack đã được render SVG/PNG và kiểm tra trực quan.
