# Crypto Market — Power BI

Project: [CryptoMarket.pbip](CryptoMarket.pbip).

## Mở và kết nối

1. Giữ nguyên cả thư mục `powerbi`; mở `CryptoMarket.pbip` bằng Power BI Desktop hỗ trợ PBIP/PBIR.
2. Nếu Desktop yêu cầu bật tính năng Power BI Project/PBIR, bật theo hướng dẫn của phiên bản bạn đang dùng rồi mở lại.
3. Trong **Transform data → Edit parameters**, kiểm tra `Server=localhost:5433`, `Database=crypto_dw`.
4. Refresh, chọn Database credentials. Dùng user/password warehouse trong `.env`; credentials không nằm trong project.
5. Pipeline phải publish GA thành công ít nhất một lần trước khi Refresh.
6. Có thể import `theme.json` qua **View → Themes → Browse for themes**.
7. Sau khi kiểm tra report, có thể Save As `.pbix`. Project hiện không kèm file PBIX đã render.

## Hai trang đã định nghĩa

**Market snapshot**: bộ lọc quote asset mặc định USDT; số cặp đang hoạt động; rolling quote volume 24h; trung bình biến động 24h của các cặp; tuổi snapshot; top 10 tăng/giảm; bảng 10 cặp có quote volume lớn nhất.

**History & coverage**: bộ lọc cặp mặc định BTCUSDT cho giá; bộ lọc quote cho volume; giá quan sát theo thời gian; rolling volume tại từng snapshot; số cặp nhận được/đủ điều kiện/bị loại theo batch.

Các bảng được import độc lập; slicer History và Overview tác động vào từng nhóm chart tương ứng. Không tạo quan hệ many-to-many giữa các batch.

## Quy tắc đọc số liệu

- Một ticker là **cặp giao dịch**, không phải một đồng coin duy nhất.
- Một quote asset mỗi lần phân tích volume. Measure volume trả blank nếu không có đúng một quote trong filter context.
- `price_change_percent_24h` từ API là điểm phần trăm; DAX chia 100 trước khi dùng format %.
- Rolling volume 24h không phải volume phát sinh trong giờ. Không SUM qua nhiều snapshot.
- Trung bình biến động là trung bình không trọng số của các cặp; không phải chỉ số lợi nhuận toàn thị trường.
- Power Query đổi timestamp có timezone về UTC trước khi bỏ timezone, vì model lưu datetime không kèm timezone.
- Một snapshot thật chỉ tạo một điểm trên đồ thị lịch sử. Cần để pipeline chạy nhiều giờ; không giả lập lịch sử.
- Các query import chạy độc lập; nên refresh sau task publish để tránh refresh vắt qua hai release. Transaction publish không tạo một transaction chung cho mọi query Power BI.
- Import refresh khác với lịch ingestion. Power BI Service cần gateway truy cập PostgreSQL local và lịch refresh riêng.

## Mức kiểm chứng

Report/source được tạo bằng định dạng PBIP/PBIR có tài liệu công khai; JSON được kiểm tra theo schema Microsoft. Dữ liệu GA và SQL đã được kiểm thử riêng. **Chưa mở/render trong Power BI Desktop, chưa chạy DAX/M trong Desktop** vì máy thực hiện chưa có Power BI Desktop. Ảnh preview đi kèm là bản minh họa bố cục dựng từ kết quả query thật, không phải ảnh chụp Power BI.

## Tái tạo và kiểm tra source

```bash
python scripts/build_powerbi.py
pip install -r requirements-dev.txt
python scripts/validate_powerbi.py
```

Tài liệu: [PBIR](https://learn.microsoft.com/en-us/power-bi/developer/projects/projects-report), [PostgreSQL connector](https://learn.microsoft.com/en-us/power-query/connectors/postgresql).
