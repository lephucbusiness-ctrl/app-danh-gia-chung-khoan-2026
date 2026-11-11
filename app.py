import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from engine import analyze, demo_price, load_price
from fundamentals import demo_fundamentals, load_fundamentals, overall, score_fundamentals
from scanner import UNIVERSE, VN30_REF, scan

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


@st.cache_data(ttl=6 * 3600, show_spinner=False)
def get_fa(ticker: str, demo: bool) -> tuple[dict, str | None]:
    """Trả về (kết quả chấm FA, thông báo lỗi nếu có). Lỗi -> chấm trung tính."""
    try:
        m = demo_fundamentals(ticker) if demo else load_fundamentals(ticker)
        return score_fundamentals(m), None
    except Exception as e:
        return score_fundamentals({}), str(e)


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
tab0, tab1, tab2 = st.tabs(["🔎 Truy tìm cổ phiếu", "🔍 Phân tích 1 mã", "🏆 So sánh cùng ngành"])

# ---------------------------------------------------------------- Tab 0: truy tìm (quét thị trường)
with tab0:
    st.markdown("Quét nhiều mã cùng lúc → chấm **Tổng điểm (FA + TA)** → lọc ra mã đáng chú ý.")
    groups = ["⭐ VN30 (tham khảo)"] + list(UNIVERSE.keys())
    cA, cB = st.columns([3, 1])
    with cA:
        chosen = st.multiselect("Chọn nhóm ngành cần quét", groups, default=["⭐ VN30 (tham khảo)"],
                                placeholder="Chọn một hoặc nhiều nhóm")
    with cB:
        scan_all = st.checkbox(f"Quét TẤT CẢ ({sum(len(v) for v in UNIVERSE.values())} mã)")
    extra = st.text_input("Thêm mã khác (không bắt buộc, cách nhau bởi dấu phẩy)", "")

    universe = []
    if scan_all:
        universe = [t for ts in UNIVERSE.values() for t in ts]
    else:
        for g in chosen:
            universe += VN30_REF if g.startswith("⭐") else UNIVERSE[g]
    universe += [t.strip().upper() for t in extra.split(",") if t.strip()]
    universe = list(dict.fromkeys(universe))  # bỏ trùng, giữ thứ tự
    st.caption(f"Sẽ quét **{len(universe)} mã**. Khoảng 1–3 phút với 100 mã (lần sau nhanh hơn).")

    if st.button("🚀 BẮT ĐẦU TRUY TÌM", type="primary", disabled=not universe):
        bar = st.progress(0.0, text="Đang quét...")

        def _p(done, total, t):
            bar.progress(done / total, text=f"Đã quét {done}/{total} mã (vừa xong: {t})")

        rows, errs = scan(universe, use_demo, vp_days, progress=_p)
        bar.empty()
        st.session_state["scan_rows"] = rows
        st.session_state["scan_errs"] = errs
        st.session_state["scan_time"] = pd.Timestamp.now().strftime("%H:%M %d/%m/%Y")

    rows = st.session_state.get("scan_rows")
    if rows:
        errs = st.session_state.get("scan_errs", {})
        res_df = pd.DataFrame(rows)

        st.markdown(f"#### 🎛️ Bộ lọc  ·  _quét lúc {st.session_state['scan_time']}, {len(res_df)} mã_")
        f1, f2, f3, f4 = st.columns(4)
        min_total = f1.slider("Tổng điểm tối thiểu", 0, 100, 60, 5)
        sig_opt = f2.selectbox("Tín hiệu kỹ thuật", ["Tất cả", "Chỉ 🟢 MUA", "MUA + Chờ xác nhận", "Tránh 🔴 BÁN"])
        min_liq = f3.number_input("GTGD TB tối thiểu (tỷ/phiên)", 0.0, 2000.0, 10.0, 5.0,
                                  help="Lọc bỏ mã ít thanh khoản, khó mua bán")
        max_risk = f4.slider("Rủi ro tối đa đến điểm cắt lỗ (%)", 2, 20, 10)

        m = (res_df["Tổng điểm"] >= min_total) & (res_df["GTGD TB20 (tỷ)"] >= min_liq) & (res_df["Rủi ro %"] <= max_risk)
        if sig_opt == "Chỉ 🟢 MUA":
            m &= res_df["_dir"] == 1
        elif sig_opt == "MUA + Chờ xác nhận":
            m &= (res_df["_dir"] == 1) | res_df["Tín hiệu KT"].str.contains("XÁC NHẬN MUA")
        elif sig_opt == "Tránh 🔴 BÁN":
            m &= res_df["_dir"] != -1
        view = res_df[m].sort_values("Tổng điểm", ascending=False).reset_index(drop=True)

        # Thẻ TOP 5
        st.markdown(f"### 🏆 Tìm thấy **{len(view)} mã** đạt tiêu chí")
        if view.empty:
            st.info("Không có mã nào đạt. Thử hạ 'Tổng điểm tối thiểu' hoặc 'GTGD TB tối thiểu'.")
        else:
            cards = st.columns(min(5, len(view)))
            for c, (_, r) in zip(cards, view.head(5).iterrows()):
                c.metric(f"{r['Mã']} · {r['Ngành']}", f"{r['Tổng điểm']:.0f}/100",
                         f"{r['% 1 tháng']:+.1f}% / 1 tháng" if pd.notna(r["% 1 tháng"]) else None)
                c.caption(f"{r['Tín hiệu KT']}  \nGiá {fmt(r['Giá'])} · SL {fmt(r['Cắt lỗ'])}")

            show = view.drop(columns=["_dir"]).copy()
            show.index = show.index + 1
            st.dataframe(
                show, use_container_width=True, height=min(38 * (len(show) + 1), 600),
                column_config={
                    "Tổng điểm": st.column_config.ProgressColumn("Tổng điểm", min_value=0, max_value=100, format="%.0f"),
                    "Giá": st.column_config.NumberColumn(format="%,.0f"),
                    "Cắt lỗ": st.column_config.NumberColumn(format="%,.0f"),
                    "% 1 tuần": st.column_config.NumberColumn(format="%+.1f%%"),
                    "% 1 tháng": st.column_config.NumberColumn(format="%+.1f%%"),
                },
            )
            st.download_button("⬇️ Tải kết quả (Excel/CSV)", show.to_csv(index_label="Hạng").encode("utf-8-sig"),
                               file_name="truy-tim-co-phieu.csv", mime="text/csv")

            # Điểm nóng theo ngành
            with st.expander("📊 Ngành nào đang mạnh? (điểm trung bình theo ngành)"):
                sec = (res_df.groupby("Ngành")
                       .agg(**{"Điểm TB": ("Tổng điểm", "mean"), "Số mã": ("Mã", "count"),
                               "Số mã tín hiệu MUA": ("_dir", lambda s: int((s == 1).sum()))})
                       .sort_values("Điểm TB", ascending=False).round(1))
                st.dataframe(sec, use_container_width=True)

            # Xem nhanh biểu đồ
            st.markdown("#### 🔍 Xem nhanh biểu đồ")
            pick = st.selectbox("Chọn mã", view["Mã"].tolist())
            if pick:
                try:
                    pres = analyze(get_data(pick, use_demo), lookback_vp=vp_days)
                    st.plotly_chart(build_chart(pres, pick), use_container_width=True)
                    st.caption("Xem đầy đủ bảng tín hiệu & sức khỏe doanh nghiệp ở tab 🔍 Phân tích 1 mã.")
                except Exception as e:
                    st.warning(f"Không vẽ được {pick}: {e}")

        if errs:
            with st.expander(f"⚠️ {len(errs)} mã không lấy được dữ liệu"):
                for t, e in errs.items():
                    st.write(f"**{t}**: {e}")

with tab1:
    ticker = st.text_input("Mã cổ phiếu", "HPG").strip().upper()
    if ticker:
        try:
            with st.spinner(f"Đang tải & phân tích {ticker}..."):
                res = analyze(get_data(ticker, use_demo), lookback_vp=vp_days)
                fa, fa_err = get_fa(ticker, use_demo)
        except Exception as e:
            st.error(f"{e}\n\nGợi ý: bật 'Dùng dữ liệu mẫu' ở thanh bên để chạy thử.")
            st.stop()

        sig = res["signal"]
        pos = res["position"]
        last = res["df"].iloc[-1]

        tot = overall(fa["score"], sig["Điểm MUA"], sig["direction"] == 1)

        c0, c1, c2, c3, c4 = st.columns([1.3, 1, 1.2, 1, 1])
        c0.metric("⭐ TỔNG ĐIỂM", f"{tot['total']:.0f}/100", tot["verdict"], delta_color="off", delta_arrow="off")
        c1.metric("Giá hiện tại", fmt(last["close"]),
                  f"{(last['close'] / res['df']['close'].iloc[-2] - 1) * 100:+.2f}%")
        c2.metric("Tín hiệu kỹ thuật", sig["Tín hiệu"])
        c3.metric("Điểm cơ bản (FA)", f"{fa['score']:.0f}/50", fa["grade"].split(" - ")[0], delta_color="off", delta_arrow="off")
        c4.metric("Điểm kỹ thuật (TA)", f"{sig['Điểm MUA'] / 2:.0f}/50", f"KL {res['vol_ratio']:.2f}x TB20",
                  delta_color="off", delta_arrow="off")

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

        fa_col, why_col = st.columns([1.1, 1])
        with fa_col:
            st.subheader(f"🏦 Sức khỏe doanh nghiệp: {fa['grade']}")
            if fa_err:
                st.warning("Chưa lấy được báo cáo tài chính → FA đang tính điểm trung tính (25/50). "
                           f"Chi tiết: {fa_err}")
            elif fa["missing"]:
                st.caption(f"⚠️ Thiếu {fa['missing']} chỉ tiêu → cho điểm trung tính. Nguồn: {fa['source']}")
            else:
                st.caption(f"Nguồn: {fa['source']} · số liệu năm gần nhất")
            st.dataframe(fa["table"], use_container_width=True, hide_index=True)
            st.caption("Thang FA 50: ROE 15 · Tăng trưởng LNST 10 · P/E 10 · Nợ/Vốn chủ 10 · P/B 5")
        with why_col, st.expander("📝 Vì sao ra tín hiệu kỹ thuật này?", expanded=True):
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
                fa, fa_err = get_fa(t, use_demo)
                tot = overall(fa["score"], s["Điểm MUA"], s["direction"] == 1)
                fa_vals = dict(zip(fa["table"]["Tiêu chí"], fa["table"]["Giá trị"]))
                rows.append({
                    "Mã": t,
                    "Tổng điểm": tot["total"],
                    "Đánh giá": tot["verdict"],
                    "FA /50": fa["score"] if not fa_err else None,
                    "TA /50": round(s["Điểm MUA"] / 2, 1),
                    "Tín hiệu KT": s["Tín hiệu"],
                    "Giá": fmt(r["df"]["close"].iloc[-1]),
                    "ROE": fa_vals.get("ROE"),
                    "P/E": fa_vals.get("P/E"),
                    "Tăng trưởng LN": fa_vals.get("Tăng trưởng LNST"),
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
            out = pd.DataFrame(rows).sort_values("Tổng điểm", ascending=False).reset_index(drop=True)
            out.index = out.index + 1
            st.success(f"🏆 Mã tốt nhất nhóm: **{out.iloc[0]['Mã']}** – {out.iloc[0]['Tổng điểm']:.0f}/100 "
                       f"({out.iloc[0]['Đánh giá']})")
            st.dataframe(
                out, use_container_width=True,
                column_config={"Tổng điểm": st.column_config.ProgressColumn(
                    "Tổng điểm", min_value=0, max_value=100, format="%.0f")},
            )
            if out["FA /50"].isna().any():
                st.caption("Ô FA trống = chưa lấy được báo cáo tài chính, đang tính trung tính 25/50.")
            st.info(
                "💡 Cách dùng: Tổng điểm = Cơ bản (doanh nghiệp tốt, giá hợp lý) + Kỹ thuật (đúng thời điểm). "
                "Ưu tiên mã TOP có tín hiệu 🟢 và rủi ro % thấp. "
                "Luôn đặt cắt lỗ theo cột SL; mã 🔴 thì hạ tỷ trọng."
            )

st.divider()
st.caption("⚠️ Kết quả dựa trên dữ liệu quá khứ và chỉ báo kỹ thuật, có thể sai. Hãy kết hợp phân tích cơ bản & quản trị vốn.")
