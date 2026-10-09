# Nhật ký sử dụng AI trong project

Project được xây dựng với sự hỗ trợ của **Claude Code** (trợ lý lập trình AI): AI viết phần lớn code, notebook và tài liệu theo yêu cầu và định hướng nghiệp vụ của tôi. Tài liệu này ghi lại **AI được dùng vào việc gì, kết quả được kiểm chứng ra sao, và những chỗ AI làm sai đã được phát hiện** - vì dùng AI hiệu quả không phải là nhận code về dùng ngay, mà là kiểm soát được chất lượng của nó.

## 1. Phân công giữa tôi và AI

| Phần việc | Ai làm |
|---|---|
| Dữ liệu, bài toán, phân tích gốc (`file analyst.ipynb`), slide báo cáo (6 KPI, 4 nhóm khách) | Tôi |
| Định hướng: cần giải quyết vấn đề thật cho nhiều phòng ban, kết hợp AI / automation / model; chọn phạm vi từng giai đoạn | Tôi |
| Rà soát notebook gốc, tìm lỗi, dựng lại phân tích, viết module `src/`, notebook 01–06, dashboard, pipeline, test, tài liệu | AI (Claude Code) |
| Quyết định giữ / bỏ tính năng, chấp nhận các đánh đổi (vd. giữ kết quả âm của model) | Tôi |
| *[Bạn điền: những phần bạn tự viết / tự sửa / tự chạy lại và kiểm tra - vd. đọc từng notebook, chạy lại pipeline, mở file Excel, thử dashboard, sửa nội dung tin nhắn CSKH…]* | Tôi |

## 2. Nguyên tắc dùng AI trong sản phẩm (LLM chạy bên trong hệ thống)

| Nguyên tắc | Cách thực hiện |
|---|---|
| **LLM không được tự tính số** | Python tính toàn bộ số liệu thành FACTS đã format; LLM chỉ diễn đạt |
| **Chống bịa số** | `briefs.validate_numbers` rút mọi con số trong bản tin LLM và đối chiếu với FACTS; có số lạ → bỏ bản LLM, dùng template. Đã thử chèn số giả (`25,000`, `9.1%`) → bị bắt |
| **Hệ thống vẫn chạy khi không có AI** | Không có API key / lỗi mạng / bị từ chối → bản tin template; dòng "Nguồn:" ghi rõ lý do |
| **Text-to-SQL an toàn** | Chỉ cho phép 1 câu `SELECT`, chặn từ khóa sửa dữ liệu, chạy trên SQLite chỉ-đọc |
| **Test không tốn tiền** | `LLM_MODE=off` (Claude) và `GEMINI_MODE=off` (Gemini) trong test; không test nào gọi API |
| **Đo chất lượng LLM bằng bộ câu hỏi có đáp án** | `eval/ask_data_eval.json`: 12 câu hỏi + SQL chuẩn; chấm bằng so kết quả, cho phép thừa cột |
| **Hỏi đáp tài liệu chỉ dựa trên tài liệu (RAG, Gemini)** | Gemini chỉ được trả lời từ các đoạn tài liệu tìm được, mỗi ý ghi nguồn [n]; không có trong tài liệu → nói rõ "không có" thay vì đoán |
| **Chống bịa số cho RAG** | Số trong câu trả lời phải xuất hiện trong đoạn trích, nếu không → chặn câu trả lời, chỉ hiện đoạn trích |
| **RAG vẫn chạy khi Gemini lỗi** | 8 model dự phòng (hết hạn mức / quá tải / quá 15 giây → model sau); mất hết → vẫn tìm đoạn tài liệu bằng từ khóa |
| **Đo chất lượng RAG** | `eval/rag_eval.json`: 14 câu (12 có đáp án + 2 ngoài phạm vi). Kết quả 2026-10-09: tìm đúng tài liệu 12/12, trả lời đúng 14/14 với model chính. Bộ câu do Claude soạn từ chính tài liệu → chỉ là kiểm tra cơ bản |

## 3. Kiểm chứng kết quả AI như thế nào

- **Chạy lại mọi con số trên dữ liệu thật** trước khi ghi vào notebook / README; kết luận viết sau khi xem output.
- **Đối chiếu với nguồn gốc:** đọc lại notebook gốc, README trên GitHub và slide báo cáo (trang KPI, trang phân nhóm khách).
- **So với baseline đơn giản** trước khi kết luận model có giá trị.
- **Thử tình huống xấu:** file lỗi cài sẵn 4 loại lỗi, khách mới thiếu file tham chiếu, mã lỗi mới khai sai, file gửi lại, file Excel đang bị khóa.
- **49 test tự động** (`pytest`; 41 ban đầu + 8 cho RAG); kiểm tra chính bộ test bằng cách cố tình làm hỏng 1 quy tắc (hạ `unknown_status` từ error xuống warning) → 2 test báo đỏ đúng chỗ.

## 4. Những chỗ sai đã được phát hiện và sửa

### 4.1 Lỗi trong phân tích gốc (do rà soát notebook gốc)
| Lỗi | Hậu quả | Sửa |
|---|---|---|
| Cohort "2022" lọc `time < "2020-01-01"` | Vẽ lại dữ liệu 2019, kết luận "2019 và 2022 như nhau" không có cơ sở | Lọc đúng năm; kết quả thật: retention tháng 1 là 4.3% (2019) vs 3.7% (2022) |
| Bảng giá trị khách chỉ tính khách có ≥1 giao dịch thành công | **13,701 khách chưa từng mua được vé bị loại khỏi phân tích** - đây hóa ra là phát hiện quan trọng nhất | Tính trên toàn bộ lượt thanh toán |
| Biểu đồ nhóm khách lỗi vẽ nhầm biến | So một biểu đồ với chính nó | Sửa biến |
| Chỉ phân tích 6/7 mã lỗi | Thiếu "Payment overdue" | Đủ 7 mã |
| Tuổi theo `date.today()` | Kết quả đổi mỗi lần chạy | Tuổi tại ngày cuối dữ liệu |
| README: "75% khách 26–35 tuổi", "55% dùng iOS", "cuối tuần 1.5 lần" | Không tái lập được từ dữ liệu | Thay bằng số tính lại: 54%, 37% (47.5% thiết bị không rõ hệ điều hành), ~1.8 lần |

### 4.2 Lỗi do AI tạo ra, phát hiện khi kiểm chứng
| Lỗi | Phát hiện bằng cách nào | Sửa |
|---|---|---|
| Phép so sánh "khách success rate < 1 vs toàn bộ giao dịch lỗi" luôn ra giống hệt nhau (luẩn quẩn) | Đọc output: 2 cột trùng từng số | So "khách chưa từng mua được" vs "khách lỗi nhưng vẫn mua được" |
| Tài chính tháng 10/2022 báo tiền giảm giá thấp bất thường (1,405 vs 4,821) | Số lệch hẳn so với tháng trước | Tháng chưa đủ cửa sổ 90 ngày → ẩn cả tháng thay vì lấy nửa tháng |
| Luật "khách giá trị cao" thiếu điều kiện còn hoạt động (TB 549 ngày chưa mua) | Xem số ngày trung bình của nhóm | Thêm điều kiện mua gần nhất ≤ 180 ngày |
| Bản tin lãnh đạo lấy KPI tháng 1 thay vì tháng 2 | Đối chiếu tháng với tuần báo cáo | Sửa điều kiện "tháng đã kết thúc" |
| Chi tiêu TB/khách hiện "8" (mất phần lẻ, giá vé ~7.8) | Đọc bản tin | Giữ 2 số lẻ cho giá trị nhỏ |
| Bộ chống bịa số chặn nhầm cụm "90 ngày" | Chạy bộ kiểm tra trên chính bản tin template | Đưa định nghĩa khung thời gian vào FACTS |
| Ngưỡng cảnh báo số dòng/ngày báo ở 11% số ngày | Xem phân bố tỷ lệ trên dữ liệu thật | Nới ngưỡng còn ~5% |
| **Thiết kế nạp dữ liệu chặn mọi ngày có khách mới** (bảng tham chiếu cố định) | Thử dữ liệu "ngày mới" có khách mới | Thêm file cập nhật bảng tham chiếu, xử lý trước giao dịch cùng ngày |
| Biểu thức `kind != TICKETS and 0 or 1` luôn ra 1 | Tự rà code trước khi chạy | Viết lại rõ ràng |
| `SMTP_PORT` rỗng trên GitHub Actions làm lỗi `int('')` | Thử với biến môi trường rỗng | `int(os.getenv(...) or 587)` |
| Pipeline lỗi khi file Excel mới nhất đang mở | Thử khóa file rồi chạy | Bắt `PermissionError`, chỉ cảnh báo |
| Chấm Text-to-SQL quá khắt khe (thừa cột = sai) | Đọc lại logic chấm | Cho phép thừa cột, không cho sai giá trị |
| README ghi "Evaluated" khi bộ đánh giá LLM **chưa chạy** | Rà lại câu chữ | Sửa thành "not yet run" |

### 4.3 Kết quả âm được giữ lại (không "làm đẹp" số)
- Model rủi ro thanh toán chỉ nhỉnh hơn luật 1 biến (AUC 0.77 vs 0.75) → kết luận nghiệp vụ là hướng khách sang phương thức ít lỗi, không phải "model phức tạp".
- Dự đoán khách quay lại từ lần mua đầu: AUC 0.53; dự đoán giao dịch lỗi tự được mua lại: AUC 0.52 → không dùng, chuyển sang liên hệ lại **toàn bộ** khách lỗi.

## 5. Chưa làm / giới hạn
- **Bộ đánh giá Text-to-SQL đã chạy với Gemini** (2026-10-09): 12/12 đúng, nhưng các câu do nhiều model khác nhau trả lời (model chính hết hạn mức) → chưa có kết quả riêng cho từng model. Chưa so với Claude (chưa có key).
- **6 model Gemini dự phòng** mới chỉ được thử với 1 câu hỏi mỗi model, chưa chạy đủ bộ 14 câu (tốn hạn mức).
- Mọi kết quả là **backtest trên dữ liệu lịch sử**; luồng nạp dữ liệu theo ngày là **mô phỏng** từ file lịch sử.
- *[Bạn điền: điều bạn học được khi làm việc với AI - vd. lúc nào phải dừng lại kiểm tra số, cách đặt yêu cầu để AI làm đúng phạm vi…]*
