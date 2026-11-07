import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from engine import analyze, demo_price, load_price

st.set_page_config(page_title="Radar Cổ Phiếu", layout="wide")

st.markdown(
    """
    <style>
    .panel {background:#0d1117;border:1px solid #22d3ee;border-radius:8px;padding:10px 14px;margin-bottom:12px;color:#e5e7eb}
    .panel h4 {color:#22d3ee;margin:0 0 6px 0;font-size:15px;text-align:center}
    .panel table {width:100%;font-size:13px;border-collapse:collapse}
    .panel td {padding:3px 4px;border-bottom:1px solid #1f2937}
    .panel td:last-child {text-align:right;font-weight:600}
    .bar {display:inline-block;height:9px;border-radius:3px;vertical-align:middle;margin-right:6px}
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("📡 Radar Cổ Phiếu – Phân tích đa khung & Tín hiệu")
st.caption(
    "Mô hình mô phỏng ý tưởng bảng 'Quantum AI' trên TradingView: Volume Profile, xu hướng đa khung, "
    "cấu trúc thị trường, điểm tin cậy và quản lý vị thế. Công cụ hỗ trợ, KHÔNG phải khuyến nghị đầu tư."
)

# ---------------------------------------------------------------- Sidebar
st.sidebar.header("⚙️ Cấu hình")
use_demo = st.sidebar.toggle("Dùng dữ liệu mẫu (chạy thử)", value=False)
vp_days = st.sidebar.slider("Số phiên tính Volume Profile", 40, 250, 120, 10)
show_days = st.sidebar.slider("Số phiên hiển thị trên biểu đồ", 60, 400, 180, 20)


@st.cache_data(ttl=900, show_spinner=False)
def get_data(ticker: str, demo: bool) -> pd.DataFrame:
    return demo_price(ticker) if demo else load_price(ticker)


def fmt(x: float) -> str:
    return f"{x:,.0f}"


def color_for(score: float) -> str:
    if score >= 60:
        return "#22c55e"
    if score > 0:
        return "#22d3ee"
    if score <= -60:
        return "#ef4444"
    if score < 0:
        return "#f472b6"
    return "#eab308"


def panel(title: str, rows: list[tuple[str, str]]) -> str:
    body = "".join(f"<tr><td>{k}</td><td>{v}</td></tr>" for k, v in rows)
    return f"<div class='panel'><h4>{title}</h4><table>{body}</table></div>"


# ---------------------------------------------------------------- Biểu đồ
def build_chart(res: dict, ticker: str) -> go.Figure:
    df = res["df"].tail(show_days)
    vp = res["vp"]
    ms = res["structure"]
    pos = res["position"]

    fig = make_subplots(
        rows=2, cols=2, shared_yaxes=False, column_widths=[0.82, 0.18],
        row_heights=[0.78, 0.22], horizontal_spacing=0.005, vertical_spacing=0.03,
        specs=[[{}, {}], [{}, None]],
    )
    fig.add_trace(go.Candlestick(
        x=df.index, open=df["open"], high=df["high"], low=df["low"], close=df["close"],
        name=ticker, increasing_line_color="#22d3ee", decreasing_line_color="#f472b6",
    ), row=1, col=1)
    for col, c in (("EMA20", "#facc15"), ("EMA50", "#38bdf8"), ("EMA200", "#a78bfa")):
        fig.add_trace(go.Scatter(x=df.index, y=df[col], name=col, line=dict(width=1.3, color=c)), row=1, col=1)

    # Vùng cung - cầu
    for z in ms["zones"]:
        x0 = max(z["time"], df.index[0])
        fill = "rgba(239,68,68,0.22)" if z["type"] == "Cung" else "rgba(34,197,94,0.22)"
        fig.add_shape(type="rect", x0=x0, x1=df.index[-1], y0=z["bottom"], y1=z["top"],
                      fillcolor=fill, line_width=0, row=1, col=1)
        fig.add_annotation(x=df.index[-1], y=z["top"], text=f"Vùng {z['type']}", showarrow=False,
                           xanchor="right", yanchor="bottom", font=dict(size=10, color="#e5e7eb"), row=1, col=1)

    # BOS / CHoCH
    ev = [e for e in ms["events"] if e[0] >= df.index[0]][-8:]
    for t, p, lab in ev:
        col = "#22c55e" if "↑" in lab else "#ef4444"
        fig.add_annotation(x=t, y=p, text=lab, showarrow=True, arrowhead=2, ax=0, ay=-22 if "↑" in lab else 22,
                           font=dict(size=10, color=col), arrowcolor=col, row=1, col=1)

    # Đỉnh/đáy swing
    sh = ms["swing_high"][ms["swing_high"].index >= df.index[0]]
    sl = ms["swing_low"][ms["swing_low"].index >= df.index[0]]
    fig.add_trace(go.Scatter(x=sh.index, y=sh * 1.01, mode="markers", name="Đỉnh",
                             marker=dict(symbol="triangle-down", color="#f472b6", size=7)), row=1, col=1)
    fig.add_trace(go.Scatter(x=sl.index, y=sl * 0.99, mode="markers", name="Đáy",
                             marker=dict(symbol="triangle-up", color="#22d3ee", size=7)), row=1, col=1)

    # Mức vị thế (chỉ vẽ khi tín hiệu MUA)
    if res["signal"]["direction"] == 1:
        for k, c in (("Giá vào", "#e5e7eb"), ("Cắt lỗ (SL)", "#ef4444"), ("TP1 (1R)", "#22c55e"),
                     ("TP2 (2R)", "#22c55e"), ("TP3 (3R)", "#22c55e")):
            fig.add_hline(y=pos[k], line=dict(color=c, width=1, dash="dot"), row=1, col=1,
                          annotation_text=f"{k}: {fmt(pos[k])}", annotation_position="top left",
                          annotation_font=dict(size=10, color=c))

    # POC
    fig.add_hline(y=res["poc"], line=dict(color="#facc15", width=1, dash="dash"), row=1, col=1,
                  annotation_text=f"POC {fmt(res['poc'])}", annotation_position="bottom right",
                  annotation_font=dict(size=10, color="#facc15"))

    # Volume Profile (cột phải)
    fig.add_trace(go.Bar(y=vp["price"], x=vp["buy"], orientation="h", name="KL mua",
                         marker_color="rgba(34,211,238,0.85)"), row=1, col=2)
    fig.add_trace(go.Bar(y=vp["price"], x=vp["sell"], orientation="h", name="KL bán",
                         marker_color="rgba(244,114,182,0.85)"), row=1, col=2)

    # Khối lượng
    vcol = ["#22d3ee" if c >= o else "#f472b6" for c, o in zip(df["close"], df["open"])]
    fig.add_trace(go.Bar(x=df.index, y=df["volume"], marker_color=vcol, name="Khối lượng", showlegend=False),
                  row=2, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df["VolMA20"], line=dict(color="#facc15", width=1),
                             name="KL TB20", showlegend=False), row=2, col=1)

    y_lo, y_hi = df["low"].min() * 0.97, df["high"].max() * 1.03
    if res["signal"]["direction"] == 1:
        y_lo = min(y_lo, pos["Cắt lỗ (SL)"] * 0.98)
        y_hi = max(y_hi, pos["TP3 (3R)"] * 1.02)
    fig.update_yaxes(range=[y_lo, y_hi], row=1, col=1)
    fig.update_yaxes(range=[y_lo, y_hi], showticklabels=False, row=1, col=2)
    fig.update_xaxes(showticklabels=False, row=1, col=2)
    fig.update_layout(
        barmode="stack", template="plotly_dark", font=dict(color="#e5e7eb"), height=720, paper_bgcolor="#0b0f14", plot_bgcolor="#0b0f14",
        xaxis_rangeslider_visible=False, margin=dict(l=10, r=10, t=30, b=10),
        legend=dict(orientation="h", y=1.04, x=0, font=dict(size=11, color="#e5e7eb")), bargap=0.05,
    )
    fig.update_xaxes(rangebreaks=[dict(bounds=["sat", "mon"])], row=1, col=1)
    fig.update_xaxes(rangebreaks=[dict(bounds=["sat", "mon"])], row=2, col=1)
    return fig


# ---------------------------------------------------------------- Tab 1: phân tích 1 mã
tab1, tab2 = st.tabs(["🔍 Phân tích 1 mã", "🏆 So sánh cùng ngành"])

with tab1:
    ticker = st.text_input("Mã cổ phiếu", "HPG").strip().upper()
    if ticker:
        try:
            with st.spinner(f"Đang tải & phân tích {ticker}..."):
                res = analyze(get_data(ticker, use_demo), lookback_vp=vp_days)
        except Exception as e:
            st.error(f"{e}\n\nGợi ý: bật 'Dùng dữ liệu mẫu' ở thanh bên để chạy thử.")
            st.stop()

        sig = res["signal"]
        pos = res["position"]
        last = res["df"].iloc[-1]

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Giá hiện tại", fmt(last["close"]),
                  f"{(last['close'] / res['df']['close'].iloc[-2] - 1) * 100:+.2f}%")
        c2.metric("Tín hiệu", sig["Tín hiệu"])
        c3.metric("Điểm tin cậy", f"{sig['Điểm tin cậy']:.0f}/100")
        c4.metric("KL so với TB20", f"{res['vol_ratio']:.2f}x")

        left, right = st.columns([3.2, 1])
        with left:
            st.plotly_chart(build_chart(res, ticker), use_container_width=True)
        with right:
            # Radar đa khung
            rows = []
            for _, r in res["radar"].iterrows():
                c = color_for(r["Điểm"])
                bar = f"<span class='bar' style='width:{max(r['Sức mạnh %'] * 0.5, 4):.0f}px;background:{c}'></span>"
                rows.append((r["Khung"], f"<span style='color:{c}'>{r['Xu hướng']}</span><br>{bar}{r['Sức mạnh %']:.0f}%"))
            st.markdown(panel("🛰️ Radar đa khung", rows), unsafe_allow_html=True)
            st.markdown(panel("🧠 Phân tích lõi", list(res["core"].items())), unsafe_allow_html=True)
            st.markdown(panel("📶 Bộ theo dõi tín hiệu", [
                ("Tín hiệu", sig["Tín hiệu"]),
                ("Điểm tin cậy", f"{sig['Điểm tin cậy']:.1f}%"),
                ("Điểm MUA / BÁN", f"{sig['Điểm MUA']:.0f} / {sig['Điểm BÁN']:.0f}"),
                ("ADX hiện tại", sig["ADX"]),
                ("RSI", sig["RSI"]),
                ("Bộ lọc", sig["Bộ lọc"]),
            ]), unsafe_allow_html=True)
            st.markdown(panel("🎯 Kế hoạch vị thế (chiều mua)", [
                (k, f"{v:.2f}%" if k == "Rủi ro %" else fmt(v)) for k, v in pos.items()
            ]), unsafe_allow_html=True)

        with st.expander("📝 Vì sao ra tín hiệu này?", expanded=True):
            for w in sig["Lý do"] or ["Chưa có yếu tố nào nổi bật."]:
                st.write("✔️", w)
            st.caption(
                "Thang điểm tin cậy: Đồng thuận đa khung 30 · EMA 15 · ADX/DI 15 · Dòng tiền 15 · "
                "RSI 10 · Cấu trúc BOS 10 · KL đột biến 5. Tín hiệu MUA/BÁN cần ≥ 65 điểm."
            )

# ---------------------------------------------------------------- Tab 2: so sánh ngành
with tab2:
    tickers_txt = st.text_input("Danh sách mã cùng ngành (cách nhau bởi dấu phẩy)", "HPG, NKG, HSG")
    if st.button("🚀 Phân tích & so sánh"):
        rows = []
        prog = st.progress(0.0)
        tickers = [t.strip().upper() for t in tickers_txt.split(",") if t.strip()]
        for i, t in enumerate(tickers):
            try:
                r = analyze(get_data(t, use_demo), lookback_vp=vp_days)
                s, p = r["signal"], r["position"]
                rows.append({
                    "Mã": t,
                    "Giá": fmt(r["df"]["close"].iloc[-1]),
                    "Tín hiệu": s["Tín hiệu"],
                    "Điểm tin cậy": s["Điểm tin cậy"],
                    "Điểm MUA": s["Điểm MUA"],
                    "Điểm BÁN": s["Điểm BÁN"],
                    "Đồng thuận khung": r["core"]["Đồng thuận đa khung"],
                    "Trạng thái": r["core"]["Trạng thái thị trường"],
                    "Dòng tiền": r["core"]["Dòng tiền 20 phiên"],
                    "SL": fmt(p["Cắt lỗ (SL)"]),
                    "Rủi ro %": round(p["Rủi ro %"], 2),
                })
            except Exception as e:
                st.warning(f"{t}: {e}")
            prog.progress((i + 1) / len(tickers))
        if rows:
            out = pd.DataFrame(rows).sort_values("Điểm MUA", ascending=False).reset_index(drop=True)
            st.success(f"🏆 Mã có điểm MUA cao nhất nhóm: **{out.iloc[0]['Mã']}** ({out.iloc[0]['Điểm MUA']:.0f} điểm)")
            st.dataframe(out, use_container_width=True)
            st.info(
                "💡 Cách dùng: ưu tiên mã TOP có tín hiệu 🟢 và rủi ro % thấp. "
                "Luôn đặt cắt lỗ theo cột SL; mã 🔴 thì hạ tỷ trọng."
            )

st.divider()
st.caption("⚠️ Kết quả dựa trên dữ liệu quá khứ và chỉ báo kỹ thuật, có thể sai. Hãy kết hợp phân tích cơ bản & quản trị vốn.")
