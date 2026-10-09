# Runbook vận hành - Báo cáo tuần & giám sát thanh toán

Tài liệu cho **người vận hành** hệ thống (người chạy báo cáo, xử lý khi dữ liệu lỗi). Các phòng ban nhận báo cáo xem [huong_dan_phong_ban.md](huong_dan_phong_ban.md).

## 1. Hệ thống làm gì, khi nào

| Khi nào | Việc | Kết quả |
|---|---|---|
| Mỗi ngày (khi có file mới) | Nạp file vào kho, kiểm tra chất lượng | Kho dữ liệu cập nhật, log chất lượng `reports/data_quality/dq_log.csv`, log vận hành `reports/daily/daily_ops.csv` |
| **08:00 thứ Hai** | Báo cáo tuần trước (thứ Hai → Chủ nhật) | Email cho 5 phòng ban + file Excel + bản tin + CSV trong `reports/weekly/<thứ Hai>/`, bản mới nhất ở `reports/BAO_CAO_MOI_NHAT.xlsx` |
| Bất kỳ lúc nào | Dashboard | Xem theo tuần, tải bảng |

## 2. Chạy báo cáo tuần

Chọn **một** cách:

| Cách | Làm gì | Ghi chú |
|---|---|---|
| Bấm tay | Bấm đúp `1_CHAY_BAO_CAO_TUAN.bat` | Xong tự mở file Excel; nếu dữ liệu lỗi, cửa sổ báo đỏ và mở thư mục `data/quarantine` |
| Lịch trên máy | Bấm đúp `3_DAT_LICH_TU_CHAY_THU_HAI.bat` (1 lần) | Máy phải **bật** lúc 08:00 thứ Hai. Hủy: `schtasks /Delete /TN "BaoCaoVanHanhTuan" /F` |
| GitHub Actions | `.github/workflows/weekly_pipeline.yml` chạy trên máy chủ GitHub | Cần khai báo Secrets (mục 7). Chạy test trước, test hỏng thì không gửi báo cáo |

Mỗi lần chạy ghi log vào `reports/logs/run_<thời điểm>.log`.

Lệnh tương đương (cho người dùng terminal):

```bash
python -m src.pipeline --ingest --send-email         # cái mà file .bat chạy
python -m src.pipeline --week 2022-02-28 --no-llm    # chạy lại 1 tuần cũ, không gọi LLM
python -m src.ingest status                          # đã nạp tới ngày nào, có file lỗi không
```

## 3. Khi có dữ liệu mới

Bỏ file vào `data/incoming/` theo đúng tên:

| File | Khi nào | Cột bắt buộc |
|---|---|---|
| `ticket_history_YYYY-MM-DD.csv` | Mỗi ngày | `ticket_id, customer_id, paying_method, theater_name, device_number, original_price, discount_value, final_price, time, status_id, campaign_id, movie_name` |
| `customer_YYYY-MM-DD.csv` | Có khách mới / khách đổi thông tin | `customer_id, usergender, dob` |
| `campaign_YYYY-MM-DD.csv` | Có campaign mới | `campaign_id, campaign_type` |
| `device_detail_YYYY-MM-DD.csv` | Có thiết bị mới | `device_number, model, platform` |
| `status_detail_YYYY-MM-DD.csv` | Có mã trạng thái / mã lỗi mới | `status_id, description, error_group` (`customer` / `external` / `internal`) |
| `ticket_history_<tên bất kỳ>.csv` | File xuất gộp nhiều ngày | Như file ngày - hệ thống tự tách theo ngày |

- Trong cùng 1 ngày, bảng tham chiếu được cập nhật **trước** giao dịch → khách đăng ký và mua cùng ngày vẫn qua.
- Muốn gửi bản sửa của file tham chiếu cùng ngày: đặt tên có hậu tố, vd. `status_detail_2023-01-05__fixed.csv`.
- File nạp xong được chuyển sang `data/archive/` → `data/incoming/` chỉ còn file đang chờ.

## 4. Khi pipeline DỪNG vì dữ liệu lỗi

Hệ thống **không ra báo cáo** khi dữ liệu mới không đạt kiểm tra (tránh gửi số sai cho các phòng ban). File lỗi nằm trong `data/quarantine/`, chi tiết lỗi trong `reports/data_quality/<tên file>.json`.

| Lỗi (`check`) | Nghĩa là | Ai xử lý | Cách khắc phục |
|---|---|---|---|
| `schema` | Thiếu cột | Bên xuất dữ liệu | Xuất lại đủ cột (mục 3) |
| `parse_types` | Thời gian / giá / mã không đọc được | Bên xuất dữ liệu | Kiểm tra định dạng (thời gian dạng `YYYY-MM-DD HH:MM:SS`) |
| `key_nulls` | Thiếu `ticket_id`, `customer_id`, `time`, `status_id` hoặc `paying_method` | Bên xuất dữ liệu | Xuất lại |
| `ticket_id_conflict` | 1 mã giao dịch có 2 nội dung khác nhau | Bên xuất dữ liệu | Xác định bản đúng |
| `already_loaded` | Giao dịch đã có trong kho (gửi trùng) | Người vận hành | Bỏ các dòng đã gửi trước đó |
| `unknown_customer` | Khách chưa có trong bảng khách hàng | Bên xuất dữ liệu | Gửi kèm `customer_<ngày>.csv` |
| `unknown_campaign` | Campaign chưa khai báo | Marketing / bên xuất dữ liệu | Gửi kèm `campaign_<ngày>.csv` |
| `unknown_status` | Mã trạng thái/lỗi mới | Product / IT | Gửi `status_detail_<ngày>.csv` có mô tả + nhóm lỗi |
| `invalid_error_group` | Mã lỗi mới khai nhóm lỗi không hợp lệ | Product / IT | Sửa thành `customer` / `external` / `internal` |
| `price_rules` | Giá âm, giảm giá > giá gốc, hoặc giá cuối ≠ gốc − giảm | Tài chính / bên xuất dữ liệu | Kiểm tra lại giá |
| `date_matches_file` | Có dòng không thuộc ngày trong tên file | Bên xuất dữ liệu | Đổi tên file hoặc gửi dạng file xuất nhiều ngày |
| `file_resent_with_different_content` | Gửi lại file của ngày **đã nạp** nhưng nội dung khác | Người vận hành + bên xuất dữ liệu | Không tự ghi đè số đã báo cáo; thống nhất cách xử lý chênh lệch |
| `cannot_split_export` | File xuất nhiều ngày có dòng không đọc được thời gian | Bên xuất dữ liệu | Xuất lại |

**Sau khi có bản sửa:** đặt file đúng vào `data/incoming/` (file giao dịch bị cách ly có thể giữ nguyên tên vì chưa được tính là đã nạp), xóa file cũ trong `data/quarantine/`, chạy lại `1_CHAY_BAO_CAO_TUAN.bat`. Bản sửa nạp thành công thì lỗi cũ tự được đánh dấu đã xử lý (`python -m src.ingest status`).

**Cảnh báo (`warning`) không dừng pipeline**, chỉ cần xem định kỳ: `exact_duplicates` (dòng trùng hoàn toàn, đã tự loại), `unknown_device`, `unknown_paying_method`, `volume` (số dòng trong ngày < 0.1 lần hoặc > 10 lần trung vị 28 ngày - thường do mở bán phim lớn hoặc rạp đóng/mở lại), `updates_existing` (bản ghi tham chiếu cũ bị đổi thông tin).

## 5. Khi báo cáo có cảnh báo đỏ

| Cảnh báo | Điều kiện | Ai làm gì |
|---|---|---|
| Lỗi thanh toán tăng bất thường (theo nhóm `customer` / `external` / `internal`) | Tỷ lệ lỗi tuần ≥ mức nền (trung vị 8 tuần trước) + 3 lần độ lệch, tuần có ≥ 100 lượt thanh toán | **Product/IT**: xem bảng "mã lỗi × nền tảng × phương thức" để biết khoanh vùng → liên hệ ngân hàng/cổng thanh toán. **CSKH**: gửi tin nhắn mẫu, hướng dẫn khách dùng Ví trong app |
| Khách mới bị mất ở bước thanh toán | Khách có lần thanh toán đầu tiên trong tuần bị lỗi và chưa mua lại được | **Marketing + CSKH**: chạy chiến dịch cứu đơn |

Cảnh báo không hoàn hảo: backtest 2022 có 6 cảnh báo, 3 thuộc đợt lỗi ngân hàng thật, 3 ở nhóm lỗi hiếm (nhiễu). Một tuần đỏ đơn lẻ ở nhóm `internal` nên xác minh trước khi hành động.

## 6. Chạy lại tuần cũ (backfill)

```bash
python -m src.pipeline --week 2022-02-28 --source warehouse --no-llm
```

Mọi số liệu chỉ dùng dữ liệu tới hết tuần được chọn, nên chạy lại tuần cũ cho đúng kết quả của thời điểm đó.

## 7. Cấu hình

| Ở đâu | Khóa | Dùng cho |
|---|---|---|
| `.env` (máy) / GitHub Secrets | `ANTHROPIC_API_KEY` | LLM viết bản tin (bỏ trống → template, vẫn chạy). `LLM_MODE=off` để tắt hẳn |
| | `GEMINI_API_KEY` | Tab "Hỏi dữ liệu": **Hỏi tài liệu & báo cáo** (RAG; bỏ trống → chỉ tìm đoạn tài liệu, không viết câu trả lời) và **Hỏi số liệu (SQL)** (bỏ trống → không dùng được). `GEMINI_MODE=off` để tắt. Danh sách model dự phòng: `GEMINI_MODELS` trong `src/config.py`. Thêm tài liệu / bản tin mới: tự được nhúng ở lần hỏi sau (khởi động lại dashboard) hoặc `python -m src.rag build` |
| | `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `EMAIL_FROM` | Gửi email. **Chưa cấu hình → không gửi**, chỉ lưu bản xem trước `.eml` trong `reports/weekly/<tuần>/outbox/` |
| | `DASHBOARD_URL` | Nút "Mở dashboard" trong email |
| | `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` | Tóm tắt qua Telegram (`--notify`) |
| `config/recipients.json` / Secret `RECIPIENTS_JSON` | danh sách email theo phòng | Mẫu: `config/recipients.example.json`. File thật không đưa lên Git |

Lần đầu bật email: điền **email của chính bạn** cho mọi phòng, chạy thử, kiểm tra hộp thư, rồi mới điền email thật.

### Bí mật - không bao giờ đưa lên GitHub
- Key, mật khẩu, token **chỉ** để trong `.env` (máy) / GitHub Secrets / Streamlit Secrets - không viết vào code, tài liệu, notebook.
- Trước mỗi lần đẩy code: `python scripts/check_secrets.py` phải báo `OK`. Lần đầu sau `git init`: `python scripts/check_secrets.py --install-hook` để tự quét mỗi lần commit.
- Lỡ đẩy key lên GitHub: **tạo key mới ngay** (Google AI Studio / Anthropic Console / BotFather) rồi mới xóa khỏi repo - xóa file không xóa được lịch sử git.

## 8. Bảo trì định kỳ

| Tần suất | Việc |
|---|---|
| Mỗi tuần | Xem tab **Dữ liệu** trên dashboard: có file bị chặn / nhiều cảnh báo bất thường không |
| Mỗi tháng | `python -m src.marts` để làm mới dataset cho analyst (nếu không chạy tự động) |
| Mỗi quý | **Train lại model rủi ro thanh toán** (notebook 03) - model hiện train trên 2019-2021 |
| Khi sửa code | `python -m pytest -q` phải xanh hết trước khi dùng |
| Khi thay đổi quy trình nghiệp vụ | Xem lại ngưỡng cảnh báo (`src/config.py`), mẫu tin nhắn CSKH (`src/briefs.py`), luật phân nhóm khách (`src/marketing.py`) |

## 9. Sự cố thường gặp

| Hiện tượng | Nguyên nhân | Cách xử lý |
|---|---|---|
| Cửa sổ `.bat` báo `python` không tìm thấy | Máy không có env `analyst` của Anaconda | Cài Anaconda + `pip install -r requirements.txt`, hoặc sửa đường dẫn `PY` trong `scripts/chay_tu_dong.bat` |
| Log có "KHÔNG cập nhật được BAO_CAO_MOI_NHAT.xlsx" | File đang mở trong Excel nên Windows khóa | Đóng Excel, chạy lại; báo cáo tuần vẫn có trong `reports/weekly/<tuần>/` |
| Dashboard báo cổng 8501 đang bận | Đã có 1 dashboard đang chạy | Dùng luôn cửa sổ đó, hoặc đóng nó rồi mở lại |
| Bản tin ghi "Nguồn: template (…)" | Chưa có API key / LLM bị tắt / LLM dùng số không có trong dữ liệu | Bình thường - bản template dùng đúng số liệu. Lý do nằm trong ngoặc |
| Email không tới | Chưa cấu hình SMTP hoặc phòng đó chưa có người nhận | Xem `deliveries` trong `reports/weekly/<tuần>/summary.json`: `saved_to_outbox` / `no_recipients` / `sent` |
| Gmail từ chối đăng nhập | Dùng mật khẩu thường | Dùng **App password** (cần bật xác minh 2 bước) |

## 10. Vị trí file

| Thư mục | Nội dung |
|---|---|
| `data/incoming/` | File đang chờ nạp |
| `data/archive/` | File đã nạp (giữ để truy vết) |
| `data/quarantine/` | File bị chặn |
| `data/warehouse/` | Kho dữ liệu (parquet) + bảng tham chiếu đã cập nhật + trạng thái `_state.json` |
| `data/marts/` | Dataset cho analyst + `data_dictionary.md` |
| `reports/weekly/<tuần>/` | Excel, bản tin `.md`, CSV từng phòng, `summary.json`, `outbox/` |
| `reports/data_quality/`, `reports/daily/`, `reports/logs/` | Log chất lượng, log vận hành ngày, log mỗi lần chạy |
