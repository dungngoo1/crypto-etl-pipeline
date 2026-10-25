# Data dictionary

## Các khóa và thời gian

| Cột | Kiểu PostgreSQL | Ý nghĩa |
|---|---|---|
| symbol | text | Cặp giao dịch Binance, có thể Unicode; không phải coin ID |
| batch_id | text | Airflow run_id hoặc ID thủ công; định danh batch immutable |
| batch_timestamp | timestamptz | Nhãn lịch chạy; Airflow truyền data_interval_end |
| ingested_at / captured_at | timestamptz | Thời điểm nhận ticker response; mọi hàng trong batch dùng cùng giá trị |
| window_open_timestamp | timestamptz | openTime của cửa sổ ticker |
| snapshot_timestamp | timestamptz | closeTime của ticker, giữ mili giây |
| published_at | timestamptz | Thời điểm release GA được publish |
| token_key | text | MD5(symbol), khóa dimension cặp |
| metric_key | text | MD5 biểu diễn có phân cách/độ dài của symbol và batch ID |

Timestamp lưu có timezone; Power BI chuyển về UTC rồi mới bỏ timezone.

## Bronze

`raw_crypto_tickers`: symbol + batch_id là primary key. `raw_payload` là JSON ticker nguyên bản; `metadata_payload` là exchangeInfo.symbols entry của cùng symbol, hoặc {} khi không có. `ingestion_batches.ticker_count` là số ticker API trả về; manifest commit cùng raw rows.

## Silver / Gold fact

| Cột | Đơn vị / ý nghĩa |
|---|---|
| base_asset / quote_asset | Mã asset từ exchangeInfo; thiếu thì NULL |
| trading_status | Status tại lúc lấy metadata; UNKNOWN nếu thiếu |
| is_spot_trading_allowed | Quyền spot tại lúc lấy metadata |
| current_price | Giá gần nhất, quote / một đơn vị base |
| open_price_24h | Giá đầu cửa sổ rolling 24h; không phải giá mở cửa ngày UTC |
| price_change_24h | Chênh lệch giá, đơn vị quote / base |
| price_change_percent_24h | Điểm phần trăm: 5 nghĩa là 5%, không phải 500% |
| high_price_24h / low_price_24h | Giá cao/thấp trong cửa sổ rolling, quote / base |
| volume_base_24h | Số đơn vị base giao dịch trong cửa sổ |
| volume_quote_24h | Số đơn vị quote giao dịch trong cửa sổ |
| trade_count_24h | Số giao dịch trong cửa sổ |
| is_analytics_eligible | Cặp được đưa vào GA latest/history hay không |
| exclusion_reason | missing_metadata / inactive / nonpositive_price / no_activity; NULL nếu đủ điều kiện |

Các số đo giá/volume dùng numeric để giữ độ chính xác SQL. Semantic model Power BI dùng double cho biểu đồ; không dùng report này cho đối soát kế toán.

## Gold dimension

`dim_tokens` một hàng mỗi symbol. Ưu tiên metadata đã biết mới nhất, tránh một lần thiếu metadata xóa thông tin asset cũ. `latest_trading_status` là status từ hàng được chọn, không phải SCD2; fact vẫn giữ status từng snapshot.

## GA

| Bảng / cột | Ý nghĩa |
|---|---|
| latest_tickers | Chỉ batch được chỉ định, không lấy latest riêng từng symbol |
| gain_rank / loss_rank | Dense rank theo % change trong từng quote; đồng hạng có thể làm top 10 có > 10 hàng |
| volume_rank | Row number theo volume giảm dần, symbol là tie-break |
| market_overview.returned_pairs | Số raw/typed rows trong nhóm batch + quote |
| active_pairs | Số cặp đủ điều kiện phân tích; không bằng số coin duy nhất |
| excluded_pairs | returned_pairs - active_pairs |
| advancing_pairs / declining_pairs | Số cặp đủ điều kiện có % change > 0 / < 0 |
| avg_change_percent_24h | Trung bình không trọng số trên các cặp đủ điều kiện |
| volume_quote_24h | Tổng rolling quote volume trong một quote và một batch |
| symbol_history | Các snapshot đủ điều kiện tới thời điểm capture của batch publish |
| publication_status | Một hàng định danh release GA hiện tại |

Volume không additive theo thời gian vì cửa sổ chồng lấn. Không cộng khác quote. Không có market cap, USD normalization, calendar OHLC hoặc exact hourly traded volume trong nguồn hiện tại.
