# Hướng dẫn sử dụng cho các phòng ban

Bạn **không cần cài hay chạy gì**. Mỗi sáng thứ Hai bạn nhận 1 email:

- **Tiêu đề** có dấu ⚠ nếu tuần đó có cảnh báo.
- **Nội dung** là bản tin của phòng bạn: tiêu đề, tóm tắt, điểm chính, hành động đề xuất (ai làm, theo dõi chỉ số nào).
- **File Excel đính kèm**: sheet *Tóm tắt* + sheet của phòng bạn + *Chất lượng dữ liệu*. Ban lãnh đạo nhận đủ cả 5 phòng.
- Nút **Mở dashboard** (nếu đã có link) để xem các tuần khác và tải bảng đầy đủ.

> **Số liệu đến từ đâu:** hệ thống tính toàn bộ con số từ dữ liệu giao dịch. Nếu bản tin do AI viết, AI chỉ được diễn đạt lại các con số đã tính sẵn; bản tin có con số lạ sẽ bị loại và thay bằng bản tin mẫu. Dòng "Nguồn:" trong bản tin cho biết bản nào được dùng.

> **Nếu thấy "Chất lượng dữ liệu: LỖI"** ở sheet Tóm tắt: dữ liệu mới nhất chưa vào báo cáo vì không đạt kiểm tra. Báo cáo vẫn đúng tới thời điểm trước đó; bộ phận vận hành đang xử lý.

---

## Ban lãnh đạo
**Bạn nhận:** 6 nhóm KPI của tháng gần nhất so với tháng trước + tóm tắt cả 5 phòng.

| Đọc thế nào | |
|---|---|
| Cột "Đánh giá" xanh / đỏ | Tốt hơn / xấu hơn tháng trước **theo chiều tốt của từng chỉ số** (tỷ lệ lỗi giảm = xanh) |
| `n/a` | Chưa đủ thời gian để đo (vd. "mua lần 2 trong 90 ngày" cần 90 ngày sau tháng đó) |

**Nên hỏi trong họp:** tỷ lệ thanh toán thành công có giảm không, có cảnh báo lỗi ngân hàng không, campaign nào đang tốn tiền mà không giữ được khách.

## Marketing
**Bạn nhận:**
1. **Phân nhóm khách** (theo slide chiến lược giữ chân) và hướng xử lý cho từng nhóm:

| Nhóm | Hướng xử lý |
|---|---|
| Khách giá trị cao | Membership, ưu đãi đặc quyền, đặt vé sớm phim hot |
| Khách mua một lần (mới) | Coupon cho lần mua thứ hai trong 7–14 ngày |
| Khách lâu chưa quay lại | Kéo lại bằng phim mới, voucher quay lại, thông báo cá nhân hóa |
| Khách nhạy khuyến mãi | Chuyển từ giảm giá trực tiếp sang tích điểm, voucher cá nhân hóa |

2. **Top khách theo điểm quay lại** (file `marketing_targets.csv` có đầy đủ). Điểm càng cao càng nên ưu tiên. ⚠ Độ chính xác **vừa phải**: nhóm điểm cao mua lại khoảng **1.8 lần** trung bình - dùng để **ưu tiên ngân sách**, không phải để chắc chắn ai sẽ quay lại.
3. **Campaign nào chỉ hút khách một lần** - theo loại và theo từng mã campaign. Ô đỏ = ≥ 95% khách mới chỉ mua 1 lần. Cột "Giảm giá / 1 khách quay lại" là chi phí thật để giữ được 1 khách.

⚠ So sánh campaign là quan sát, chưa phải nhân quả (mỗi campaign nhắm tệp khách khác nhau) - muốn kết luận chắc nên chạy thử nghiệm A/B.

## CSKH
**Bạn nhận:** **danh sách cứu đơn** - khách bị lỗi thanh toán trong tuần và **chưa** mua lại được, kèm sẵn **tin nhắn gửi khách theo mã lỗi**.

| Cách làm | |
|---|---|
| Ưu tiên dòng tô đỏ | Lỗi phía ngân hàng (khách không tự sửa được) |
| Lọc theo cột | File có sẵn bộ lọc (phương thức, loại lỗi…) |
| Khi có cảnh báo lỗi ngân hàng | Chủ động hướng dẫn khách chuyển sang **Ví trong app** (tỷ lệ lỗi ~2.6% so với 20–27% của thẻ/tài khoản ngân hàng) |

Mẫu tin nhắn theo mã lỗi:

| Mã | Lỗi | Tin nhắn |
|---|---|---|
| -1 | Payment overdue | Đơn đặt vé đã quá hạn thanh toán, ghế vẫn có thể còn - đặt lại trong 1 chạm |
| -2 | Insufficient funds | Tài khoản chưa đủ số dư - thanh toán bằng Ví trong app để giữ ghế |
| -3 | No response from your bank | Ngân hàng chưa phản hồi, chưa bị trừ tiền - thử lại hoặc chọn Ví trong app |
| -4 | Password locked | Tài khoản bị khóa tạm - chọn "Quên mật khẩu" để mở khóa |
| -5 | Payment failed from bank | Lỗi từ phía ngân hàng - thử lại sau ít phút hoặc chọn Ví trong app |
| -6 | Need verify your account | Cần xác minh tài khoản - hoàn tất trong 2 phút |
| -7 | Transaction temporarily limited | Giao dịch bị giới hạn tạm thời - đội hỗ trợ sẽ liên hệ |

Muốn sửa nội dung tin nhắn: báo bộ phận vận hành (nội dung nằm trong `src/briefs.py`, `RECOVERY_MESSAGES`).

## Product / IT
**Bạn nhận:**
1. **Biểu đồ lỗi phía ngân hàng 26 tuần**, dòng đỏ = tuần có cảnh báo (tỷ lệ lỗi cao bất thường so với 8 tuần trước).
2. **Bảng khoanh vùng: mã lỗi × nền tảng × phương thức** - tuần này vs 8 tuần trước. Ô đỏ = tăng > 5 điểm %. Cột "Lỗi vượt mức" = số lỗi nhiều hơn bình thường.

Ví dụ thật (tuần 28/02/2022): *Payment failed from bank* trên mobile qua bank account tăng **4.6% → 21.1%** → đủ cụ thể để liên hệ đúng ngân hàng / cổng thanh toán.

**Khi có mã lỗi mới** trong hệ thống: cần khai báo mô tả + nhóm lỗi (`customer` / `external` / `internal`) cho bộ phận vận hành, nếu không dữ liệu ngày đó sẽ bị dừng lại (xem [runbook](runbook.md), mục 4).

## Tài chính
**Bạn nhận:**
- **Giá trị đơn lỗi không được mua lại trong 7 ngày** theo tháng.
- **Tiền giảm giá rơi vào khách không quay lại trong 90 ngày** theo tháng.
- Biểu đồ so sánh 2 khoản này.

Tháng gần nhất để trống là **bình thường** - chưa đủ 7 / 90 ngày để biết khách có quay lại không. Số liệu là **cận dưới** của thiệt hại (chưa có chi phí quảng cáo, giá trị vòng đời). Đơn vị tiền theo dữ liệu nguồn.

---

## Câu hỏi thường gặp
**Tôi muốn xem tuần khác?** Mở dashboard, chọn tuần ở thanh bên trái.

**Tôi muốn số liệu thô để tự phân tích?** Mỗi bảng trên dashboard có nút Tải; dataset đầy đủ cho analyst nằm ở `data/marts/` (kèm từ điển dữ liệu).

**Số trong email khác số tôi tự tính?** Kiểm tra định nghĩa chỉ số trong [data_workflow.md](data_workflow.md), mục 3. Nếu vẫn lệch, gửi cho bộ phận vận hành: tên chỉ số, tuần, con số của bạn và cách bạn tính.

**Có câu hỏi về cách tính chỉ số, quy trình xử lý hay nội dung bản tin?** Mở dashboard → tab **Hỏi dữ liệu** → **Hỏi tài liệu & báo cáo**, gõ câu hỏi tiếng Việt (vd. *"Khi có cảnh báo lỗi ngân hàng thì CSKH cần làm gì?"*). AI trả lời **chỉ từ tài liệu và bản tin** của hệ thống, mỗi ý có nguồn [1], [2]… bấm vào để xem nguyên văn. Tài liệu không có → hệ thống nói rõ là không có, không đoán. Câu hỏi cần tính số (doanh thu, số vé theo tháng…) dùng chế độ **Hỏi số liệu (SQL)**.

**Muốn thêm / bớt người nhận email?** Báo bộ phận vận hành (danh sách nằm trong `config/recipients.json`).
