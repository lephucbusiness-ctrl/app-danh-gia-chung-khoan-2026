# Radar Cổ Phiếu – Phân tích đa khung & Tín hiệu

App Streamlit mô phỏng ý tưởng bảng "Quantum AI" (TradingView) cho cổ phiếu Việt Nam.

![Ảnh màn hình](docs/screenshot.png)

## Các khối chức năng
| Khối | Nội dung |
|---|---|
| Biểu đồ nến | EMA20/50/200, đỉnh/đáy swing, BOS/CHoCH, vùng Cung/Cầu, POC |
| Volume Profile | Khối lượng xếp chồng theo vùng giá, tách mua (xanh) / bán (hồng) |
| Radar đa khung | Xu hướng & sức mạnh khung Ngày / Tuần / Tháng |
| Phân tích lõi | Đồng thuận đa khung, trạng thái thị trường (ADX), nén biến động (Squeeze), dòng tiền 20 phiên |
| Bộ theo dõi tín hiệu | MUA / BÁN / CHỜ, điểm tin cậy 0–100, bộ lọc |
| Kế hoạch vị thế | Giá vào, cắt lỗ theo ATR, TP1–TP3 (1R/2R/3R) |
| So sánh ngành | Chấm điểm nhiều mã, xếp hạng mã tốt nhất |

## Thang điểm tin cậy (100)
Đồng thuận đa khung 30 · EMA xếp hướng 15 · ADX/DI 15 · Dòng tiền 15 · RSI 10 · Cấu trúc BOS 10 · KL đột biến 5.
Tín hiệu MUA cần ≥ 65 điểm **và** bộ lọc đạt (ADX ≥ 20, không đang nén).

## Chạy
```
pip install -r requirements.txt
streamlit run app.py
```
Không có mạng / vnstock lỗi → bật "Dùng dữ liệu mẫu" ở thanh bên.

⚠️ Công cụ hỗ trợ, không phải khuyến nghị đầu tư.
