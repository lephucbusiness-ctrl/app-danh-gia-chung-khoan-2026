import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from vnstock import *

# Cấu hình giao diện Streamlit
st.set_page_config(page_title="Hệ thống So sánh & Dự báo Cổ phiếu", layout="wide")

st.title("📊 Ứng dụng Tư duy & Phân tích Cổ phiếu Tối ưu (FA + TA)")
st.caption("Công cụ chấm điểm độc lập, so sánh cùng ngành và dự báo tín hiệu mua/bán.")

# Sidebar - Chọn tham số
st.sidebar.header("Cấu hình Phân tích")
industry_tickers = st.sidebar.text_input(
    "Nhập danh sách mã cổ phiếu cùng ngành (cách nhau bởi dấu phẩy):",
    "HPG, NKG, HSG"
)
list_tickers = [ticker.strip().upper() for ticker in industry_tickers.split(",")]

# Hàm tính toán điểm số và tín hiệu
def analyze_stock(ticker):
    try:
        # 1. Lấy dữ liệu lịch sử giá 1 năm
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')
        df_price = stock_historical_data(ticker, start_date, end_date, "1D", "stock")
        
        if df_price.empty:
            return None

        # Tính toán Kỹ thuật (TA)
        df_price['MA20'] = df_price['close'].rolling(20).mean()
        df_price['MA50'] = df_price['close'].rolling(50).mean()
        df_price['MA200'] = df_price['close'].rolling(200).mean()
        df_price['Vol_MA20'] = df_price['volume'].rolling(20).mean()
        
        latest = df_price.iloc[-1]
        
        # Bảng chấm điểm TA (Max 50 điểm)
        ta_score = 0
        if latest['close'] > latest['MA20'] > latest['MA50']:
            ta_score += 20
        elif latest['close'] > latest['MA20']:
            ta_score += 10
            
        if latest['volume'] > 1.5 * latest['Vol_MA20']:
            ta_score += 15
        elif latest['volume'] > latest['Vol_MA20']:
            ta_score += 8
            
        if latest['close'] > df_price.iloc[-2]['close']:
            ta_score += 15

        fa_score = 35 # Điểm cơ bản tham chiếu

        total_score = ta_score + fa_score

        # Dự báo Tín hiệu Mua / Bán
        signal = "🟡 CHỜ TÍCH LŨY"
        if total_score >= 75 and latest['close'] > latest['MA20'] and latest['volume'] > 1.2 * latest['Vol_MA20']:
            signal = "🟢 MUA KÍCH HOẠT (Breakout)"
        elif latest['close'] < latest['MA50'] or total_score < 40:
            signal = "🔴 CẮT LỖ / BÁN"

        return {
            "Mã CK": ticker,
            "Giá Hiện Tại": f"{latest['close']:,} VNĐ",
            "Điểm FA (/50)": fa_score,
            "Điểm TA (/50)": ta_score,
            "Tổng Điểm (/100)": total_score,
            "Biến Động Vol": f"{round(latest['volume'] / latest['Vol_MA20'], 2)}x",
            "Tín Hiệu Dự Báo": signal
        }
    except Exception as e:
        st.error(f"Lỗi khi xử lý mã {ticker}: {e}")
        return None

# Nút thực thi phân tích
if st.button("🚀 Phân Tích & So Sánh Ngành"):
    with st.spinner("Đang tải dữ liệu thời gian thực và chấm điểm..."):
        results = []
        for ticker in list_tickers:
            data = analyze_stock(ticker)
            if data:
                results.append(data)
        
        if results:
            df_res = pd.DataFrame(results)
            df_res = df_res.sort_values(by="Tổng Điểm (/100)", ascending=False).reset_index(drop=True)
            
            top_pick = df_res.iloc[0]['Mã CK']
            st.success(f"🏆 **MÃ TỐI ƯU NHẤT NGÀNH TẠI THỜI ĐIỂM HIỆN TẠI:** **{top_pick}**")
            
            st.subheader("📊 Bảng So Sánh Chỉ Số & Chấm Điểm Chi Tiết")
            st.dataframe(df_res, use_container_width=True)
            
            st.info("""
            💡 **Hướng dẫn hành động:**
            - **Mã TOP 1:** Ưu tiên giải ngân khi có tín hiệu MUA.
            - **Tín hiệu 🔴 CẮT LỖ/BÁN:** Bắt buộc hạ tỷ trọng nếu cổ phiếu vi phạm MA50 hoặc điểm dưới 40.
            """)
