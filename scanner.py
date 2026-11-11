"""
TRUY TÌM CỔ PHIẾU - quét nhiều mã cùng lúc, chấm điểm và lọc.

Danh sách mã theo ngành dưới đây là danh sách THAM KHẢO các mã thanh khoản tốt,
có thể lệch so với rổ chỉ số chính thức (VN30, VN100...). Sửa trực tiếp tại đây nếu cần.
"""
from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from engine import analyze, demo_price, load_price
from fundamentals import demo_fundamentals, load_fundamentals, overall, score_fundamentals

UNIVERSE: dict[str, list[str]] = {
    "Ngân hàng": ["VCB", "BID", "CTG", "TCB", "MBB", "VPB", "ACB", "HDB", "STB", "VIB", "TPB",
                  "SHB", "LPB", "MSB", "EIB", "OCB", "SSB"],
    "Chứng khoán": ["SSI", "VND", "HCM", "VCI", "SHS", "MBS", "FTS", "BSI", "CTS", "VIX"],
    "Bất động sản & KCN": ["VHM", "VIC", "VRE", "NVL", "KDH", "NLG", "DXG", "PDR", "DIG", "KBC",
                           "IDC", "SZC", "NTL", "CEO", "BCM", "SIP"],
    "Thép & Vật liệu xây dựng": ["HPG", "HSG", "NKG", "SMC", "TLH", "VGC", "HT1", "BMP", "NTP"],
    "Xây dựng & Đầu tư công": ["VCG", "HHV", "CII", "LCG", "FCN", "C4G", "CTD", "PC1"],
    "Bán lẻ & Tiêu dùng": ["MWG", "PNJ", "FRT", "DGW", "MSN", "VNM", "SAB", "QNS", "KDC"],
    "Dầu khí": ["GAS", "PLX", "PVD", "PVS", "BSR", "PVT", "OIL"],
    "Điện & Năng lượng": ["POW", "REE", "GEG", "NT2", "HDG"],
    "Công nghệ & Viễn thông": ["FPT", "CMG", "CTR", "VGI", "ELC"],
    "Hóa chất & Phân bón": ["DGC", "DPM", "DCM", "CSV"],
    "Thủy sản & Nông nghiệp": ["VHC", "ANV", "IDI", "FMC", "HAG", "DBC", "PAN", "BAF"],
    "Cảng, Logistics & Hàng không": ["GMD", "HAH", "VSC", "VTP", "HVN", "VJC", "ACV", "SCS"],
    "Cao su": ["GVR", "PHR", "DPR"],
    "Bảo hiểm": ["BVH", "BMI"],
}

VN30_REF = ["ACB", "BCM", "BID", "BVH", "CTG", "FPT", "GAS", "GVR", "HDB", "HPG", "LPB", "MBB",
            "MSN", "MWG", "PLX", "SAB", "SHB", "SSB", "SSI", "STB", "TCB", "TPB", "VCB", "VHM",
            "VIB", "VIC", "VJC", "VNM", "VPB", "VRE"]

SECTOR_OF = {t: s for s, ts in UNIVERSE.items() for t in ts}


def scan_one(ticker: str, demo: bool, vp_days: int = 120) -> dict:
    df = demo_price(ticker) if demo else load_price(ticker)
    src = "Dữ liệu mẫu" if demo else df.attrs.get("source", "")
    r = analyze(df, lookback_vp=vp_days)
    s, p, last = r["signal"], r["position"], r["df"].iloc[-1]
    try:
        fa = score_fundamentals(demo_fundamentals(ticker) if demo else load_fundamentals(ticker))
        fa_ok = True
    except Exception:
        fa, fa_ok = score_fundamentals({}), False
    tot = overall(fa["score"], s["Điểm MUA"], s["direction"] == 1)
    vals = dict(zip(fa["table"]["Tiêu chí"], fa["table"]["Giá trị"]))
    tail = r["df"].tail(20)
    liquidity = float((tail["close"] * tail["volume"]).mean() / 1e9)  # tỷ đồng / phiên
    close = r["df"]["close"]
    return {
        "Mã": ticker,
        "Ngành": SECTOR_OF.get(ticker, "Khác"),
        "Tổng điểm": tot["total"],
        "Đánh giá": tot["verdict"],
        "Tín hiệu KT": s["Tín hiệu"],
        "FA /50": fa["score"] if fa_ok else None,
        "TA /50": round(s["Điểm MUA"] / 2, 1),
        "Giá": float(last["close"]),
        "% 1 tuần": (close.iloc[-1] / close.iloc[-6] - 1) * 100 if len(close) > 6 else None,
        "% 1 tháng": (close.iloc[-1] / close.iloc[-22] - 1) * 100 if len(close) > 22 else None,
        "GTGD TB20 (tỷ)": round(liquidity, 1),
        "KL/TB20": round(r["vol_ratio"], 2),
        "Xu hướng khung": r["core"]["Đồng thuận đa khung"],
        "Biến động": r["core"]["Biến động"],
        "ROE": vals.get("ROE"),
        "P/E": vals.get("P/E"),
        "Tăng trưởng LN": vals.get("Tăng trưởng LNST"),
        "Cắt lỗ": float(p["Cắt lỗ (SL)"]),
        "Rủi ro %": round(p["Rủi ro %"], 2),
        "Nguồn giá": src,
        "_dir": s["direction"],
    }


def scan(tickers: list[str], demo: bool, vp_days: int = 120, workers: int = 3, progress=None):
    """Quét song song. progress(done, total, ticker) để cập nhật thanh tiến trình."""
    rows, errors = [], {}
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(scan_one, t, demo, vp_days): t for t in tickers}
        for i, f in enumerate(as_completed(futs), 1):
            t = futs[f]
            try:
                rows.append(f.result())
            except Exception as e:
                errors[t] = str(e)
            if progress:
                progress(i, len(tickers), t)
    # Mã lỗi (thường do nguồn giới hạn số lần gọi): chờ rồi quét lại lần lượt, chậm rãi
    if errors:
        time.sleep(3)
    for t in list(errors):
        try:
            rows.append(scan_one(t, demo, vp_days))
            del errors[t]
        except Exception as e:
            errors[t] = str(e)
        time.sleep(1.5)
    return rows, errors
