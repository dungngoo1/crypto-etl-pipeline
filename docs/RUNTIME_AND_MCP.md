# Xác nhận Docker, Airflow và Power BI

## Trạng thái hiện tại

- Docker Desktop đã được mở và hiển thị **Engine running**.
- Docker CLI trong môi trường agent bị **permission denied** khi truy cập Engine. Chưa build/chạy được bản sửa qua Docker trong môi trường này.
- Power BI Desktop installer 2.159.883.0 đã tải từ Microsoft; chữ ký Authenticode **Valid**, signer Microsoft Corporation.
- Chủ máy chọn tự hoàn tất cài đặt. MCP đã phát hiện một instance Power BI Desktop/Analysis Services.
- Microsoft Power BI browser integration đã được cài. Nó phục vụ Power BI Service qua trình duyệt, không thay thế MCP local cho Desktop.
- MCP local Microsoft **1.0.0** đã khởi động thành công: **21 nhóm công cụ**.
- Đã mở BIM dự án qua MCP: **4 bảng, 45 cột, 9 measures**.
- Thử kết nối Desktop bằng MCP thất bại ở bước **OpenAdomd**; chưa xác định chắc nguyên nhân. Không coi việc phát hiện port là bằng chứng đã kết nối.
- Chưa refresh PostgreSQL trong Desktop, chưa chạy DAX và chưa kiểm tra render report.

## Cần thêm những gì để xác nhận Airflow?

Không cần gửi mật khẩu, API key hoặc file .env. Cần kết quả chạy trên Windows account có quyền truy cập Docker Engine:

| Kiểm tra | Bằng chứng cần có |
|---|---|
| Docker Engine | docker version có cả Client và Server |
| Build | docker compose up -d --build thành công |
| Khởi tạo | airflow-init exit 0, không lỗi migration |
| Containers | Webserver/scheduler và hai Postgres hoạt động |
| DAG import | Không có import errors cho DAG dự án |
| Chạy thật | Một run mới có bốn task success, gồm publish_ga |
| Dữ liệu | publication batch đúng run; ticker_count = raw_rows = gold_rows; GA có dữ liệu |
| Power BI | Refresh thành công, so sánh cùng quote/batch với SQL |

Chạy trong PowerShell của bạn, tại thư mục repo:

```powershell
Copy-Item .env.example .env
# Chỉnh thông tin local trong .env nếu chưa có.
.\scripts\verify_runtime.ps1
```

Chỉ dùng Copy-Item nếu **chưa có .env**; không ghi đè cấu hình đang dùng. Với database phiên bản cũ, làm migration theo README trước khi chạy pipeline mới.

Sau khi kiểm tra cấu hình và migration:

```powershell
.\scripts\verify_runtime.ps1 -StartPipeline
```

Script không xóa container/volume. Tùy chọn StartPipeline sẽ build/up services, unpause DAG, trigger một run kiểm chứng và chờ kết quả. Logs được lưu trong **.local/runtime-YYYYMMDD_HHMMSS/**; chỉ cần cung cấp các log liên quan nếu có lỗi, không gửi .env. Script đã được parse kiểm tra cú pháp PowerShell, **chưa được chạy đầu cuối với Docker** trong phiên này.

Nếu chính sách máy chặn chạy script, không tự thay execution policy; có thể chạy các lệnh Docker trực tiếp:

```powershell
docker version
docker compose ps -a
docker compose logs --tail 150 airflow-init airflow-scheduler
docker compose exec -T airflow-scheduler airflow dags list-import-errors --output json
```

## MCP local của Microsoft

Server dùng **stdio**. Instance Analysis Services của Desktop có port localhost được cấp khi mở report; port này có thể thay đổi. Không hard-code 58514 hoặc một port từ lần chạy trước.

Cấu hình mẫu cho Codex:

```toml
[mcp_servers.powerbi_authoring_local]
command = "C:/path/to/powerbi-modeling-mcp.exe"
args = ["--start", "--accepteula", "--audit-log-path=C:/path/to/writable/audit"]
startup_timeout_sec = 60
tool_timeout_sec = 120
```

Chỉ dùng accepteula sau khi đã đồng ý [EULA Microsoft](https://github.com/microsoft/powerbi-modeling-mcp/blob/main/EULA.txt). Chủ máy đã đồng ý trong chat; cấu hình local đã được thêm vào Codex, giữ nguyên các cấu hình khác. Binary và audit directory thực tế đang nằm trong thư mục outputs/tools của phiên làm việc; không di chuyển chúng nếu vẫn dùng cấu hình đó.

Nếu server chưa xuất hiện trong Codex, mở lại ứng dụng để nạp cấu hình rồi kiểm tra danh sách MCP. Việc kết nối plugin Power BI qua trình duyệt không tự nạp server local này.

Kiểm tra read-only bằng script sau khi đã đồng ý EULA:

```powershell
python scripts/check_powerbi_mcp.py --server "C:/path/to/powerbi-modeling-mcp.exe" --accept-eula
```

Lệnh trên đọc BIM offline. Kiểm tra Desktop:

```powershell
python scripts/check_powerbi_mcp.py --server "C:/path/to/powerbi-modeling-mcp.exe" --accept-eula --desktop --output ".local/mcp-desktop.json"
```

Chỉ mở một report Desktop khi dùng script discovery này. Nên mở **CryptoMarket.pbip** và chạy MCP bằng cùng Windows account với Desktop. Đây là hướng kiểm tra, không phải kết luận chắc chắn về nguyên nhân OpenAdomd.

MCP authoring hỗ trợ semantic model/DAX; không thay thế thao tác bố cục report trong Desktop hoặc chỉnh PBIR source.

## Sau khi mở CryptoMarket trong Desktop

1. Giữ nguyên thư mục powerbi rồi mở CryptoMarket.pbip.
2. Kiểm tra Server=localhost:5433, Database theo .env.
3. Nhập credentials warehouse trong Desktop, không gửi qua chat.
4. Refresh sau khi task publish_ga thành công.
5. Chọn quote USDT; đối chiếu Active pairs và Volume 24h với SQL cùng batch.
6. Kiểm tra phần trăm, timezone UTC, slicer và hai trang report.
7. Để pipeline chạy thêm nhiều giờ để có lịch sử thật.

Ví dụ SQL đối chiếu:

```sql
SELECT count(*) AS pairs, sum(volume_quote_24h) AS quote_volume_24h
FROM ga.latest_tickers
WHERE quote_asset = 'USDT';
```

DAX đối chiếu sau khi kết nối đúng model:

```dax
EVALUATE
ROW(
    "Pairs USDT", CALCULATE([Active pairs], Latest[quote_asset] = "USDT"),
    "Volume USDT", CALCULATE([Volume 24h], Latest[quote_asset] = "USDT")
)
```

Các query SQL/DAX phải dựa trên cùng release dữ liệu; không dùng số 516 hoặc 1.382 của snapshot cũ làm hằng số kiểm thử.

## Tài liệu chính thức

- [Power BI Authoring MCP](https://learn.microsoft.com/en-us/power-bi/developer/mcp/power-bi-authoring-mcp)
- [Microsoft MCP repository](https://github.com/microsoft/powerbi-modeling-mcp)
- [Power BI Desktop download](https://www.microsoft.com/en-us/download/details.aspx?id=58494)
- [Codex MCP configuration](https://learn.chatgpt.com/docs/extend/mcp)
