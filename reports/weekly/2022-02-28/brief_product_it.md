# Product / IT - tuần 2022-02-28 → 2022-03-06
_Nguồn: template (LLM_MODE=off)_

## Payment failed from bank trên mobile / bank account: 21.1% (nền 4.6%)

1,019 lượt thanh toán, tỷ lệ thành công 80.8% (8 tuần trước: 82.4%). CẢNH BÁO: lỗi phía ngân hàng 17.8% (mức nền 8.7%, z = 5.0).

### Điểm chính
- 1,019 lượt thanh toán, tỷ lệ thành công 80.8% (8 tuần trước: 82.4%).
- CẢNH BÁO: lỗi phía ngân hàng 17.8% (mức nền 8.7%, z = 5.0).
- Payment failed from bank · mobile · bank account: 21.1% so với 4.6% (+16.5 điểm %, vượt mức bình thường 74 lỗi).
- Payment failed from bank · mobile · debit card: 36.5% so với 19.6% (+16.9 điểm %, vượt mức bình thường 26 lỗi).
- Payment failed from bank · mobile · credit card: 24.5% so với 21.5% (+2.9 điểm %, vượt mức bình thường 3 lỗi).
- Theo phương thức: debit card 36.9% vs money in app 2.3%.

### Hành động đề xuất
| Việc cần làm | Phụ trách | Chỉ số theo dõi |
|---|---|---|
| Làm việc với ngân hàng / cổng thanh toán về tổ hợp lỗi tăng mạnh nhất | Product / IT | Tỷ lệ lỗi nhóm external theo tuần |
| Thiết kế retry flow: thanh toán lại, đổi phương thức, giữ vé tạm thời | Product | Tỷ lệ hoàn tất thanh toán trên app |
| Gợi ý phương thức ít lỗi hơn ở checkout cho giao dịch rủi ro cao (A/B test) | Product | Tỷ lệ thanh toán thành công |
