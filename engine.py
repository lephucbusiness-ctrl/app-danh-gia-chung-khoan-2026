"""
Bộ máy phân tích (engine) - mô phỏng các khối trong video "Quantum AI":
  1. Multi-TF Radar      : xu hướng theo nhiều khung (Ngày / Tuần / Tháng)
  2. Core Analytics      : đồng thuận đa khung, trạng thái thị trường, nén biến động, dòng tiền
  3. Signal Tracker      : tín hiệu mới nhất, điểm tin cậy, ADX, bộ lọc
  4. Position Status     : giá vào, cắt lỗ (SL), chốt lời (TP1-TP3)
  5. Volume Profile      : khối lượng xếp chồng theo vùng giá (mua / bán), POC
  6. Cấu trúc thị trường : đỉnh/đáy swing, BOS, vùng cung - cầu

Toàn bộ chỉ dùng pandas/numpy, không phụ thuộc nguồn dữ liệu.
"""
from __future__ import annotations

from datetime import datetime, timedelta

import zlib

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# 0. TẢI DỮ LIỆU
# ---------------------------------------------------------------------------
def _normalize(df: pd.DataFrame) -> pd.DataFrame:
    df = df.rename(columns=str.lower).copy()
    if "time" in df.columns:
        df["time"] = pd.to_datetime(df["time"])
        df = df.set_index("time")
    elif "tradingdate" in df.columns:
        df["tradingdate"] = pd.to_datetime(df["tradingdate"])
        df = df.set_index("tradingdate")
    df.index = pd.to_datetime(df.index)
    df = df[["open", "high", "low", "close", "volume"]].astype(float)
    return df.sort_index().dropna()


def load_price(ticker: str, days: int = 730) -> pd.DataFrame:
    """Lấy giá ngày (Yahoo Finance -> TCBS). Xem datasource.py."""
    from datasource import load_price as _load

    return _load(ticker, days)


def demo_price(ticker: str, days: int = 500) -> pd.DataFrame:
    """Dữ liệu giả lập để chạy thử khi không có mạng."""
    seed = zlib.crc32(ticker.encode())
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range(end=datetime.now().date(), periods=days)
    drift = rng.normal(0.0004, 0.0003)
    ret = rng.normal(drift, 0.018, days)
    close = 20000 * np.exp(np.cumsum(ret))
    open_ = close * (1 + rng.normal(0, 0.006, days))
    high = np.maximum(open_, close) * (1 + np.abs(rng.normal(0, 0.008, days)))
    low = np.minimum(open_, close) * (1 - np.abs(rng.normal(0, 0.008, days)))
    vol = rng.lognormal(14, 0.5, days) * (1 + 3 * np.abs(ret))
    df = pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": vol}, index=idx
    )
    return df.round({"open": -1, "high": -1, "low": -1, "close": -1, "volume": 0})


# ---------------------------------------------------------------------------
# 1. CHỈ BÁO KỸ THUẬT
# ---------------------------------------------------------------------------
def ema(s: pd.Series, n: int) -> pd.Series:
    return s.ewm(span=n, adjust=False).mean()


def rsi(close: pd.Series, n: int = 14) -> pd.Series:
    d = close.diff()
    up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    rs = up / dn.replace(0, np.nan)
    return (100 - 100 / (1 + rs)).fillna(50)


def atr(df: pd.DataFrame, n: int = 14) -> pd.Series:
    pc = df["close"].shift()
    tr = pd.concat(
        [df["high"] - df["low"], (df["high"] - pc).abs(), (df["low"] - pc).abs()], axis=1
    ).max(axis=1)
    return tr.ewm(alpha=1 / n, adjust=False).mean()


def adx(df: pd.DataFrame, n: int = 14) -> tuple[pd.Series, pd.Series, pd.Series]:
    up = df["high"].diff()
    dn = -df["low"].diff()
    plus_dm = np.where((up > dn) & (up > 0), up, 0.0)
    minus_dm = np.where((dn > up) & (dn > 0), dn, 0.0)
    a = atr(df, n)
    plus_di = 100 * pd.Series(plus_dm, index=df.index).ewm(alpha=1 / n, adjust=False).mean() / a
    minus_di = 100 * pd.Series(minus_dm, index=df.index).ewm(alpha=1 / n, adjust=False).mean() / a
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    return dx.ewm(alpha=1 / n, adjust=False).mean().fillna(0), plus_di, minus_di


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["EMA20"] = ema(df["close"], 20)
    df["EMA50"] = ema(df["close"], 50)
    df["EMA200"] = ema(df["close"], 200)
    df["RSI"] = rsi(df["close"])
    df["ATR"] = atr(df)
    df["ADX"], df["DI+"], df["DI-"] = adx(df)
    df["VolMA20"] = df["volume"].rolling(20).mean()
    # Bollinger & Keltner -> nén biến động (squeeze)
    ma20 = df["close"].rolling(20).mean()
    sd20 = df["close"].rolling(20).std()
    df["BB_up"], df["BB_dn"] = ma20 + 2 * sd20, ma20 - 2 * sd20
    df["KC_up"], df["KC_dn"] = ma20 + 1.5 * df["ATR"], ma20 - 1.5 * df["ATR"]
    df["Squeeze"] = (df["BB_up"] < df["KC_up"]) & (df["BB_dn"] > df["KC_dn"])
    return df


# ---------------------------------------------------------------------------
# 2. RADAR ĐA KHUNG THỜI GIAN
# ---------------------------------------------------------------------------
def resample(df: pd.DataFrame, rule: str) -> pd.DataFrame:
    agg = {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
    return df[["open", "high", "low", "close", "volume"]].resample(rule).agg(agg).dropna()


def trend_bias(df: pd.DataFrame) -> dict:
    """Chấm xu hướng 1 khung: điểm -100 (giảm mạnh) .. +100 (tăng mạnh)."""
    if len(df) < 12:
        return {"bias": "Thiếu dữ liệu", "score": 0, "strength": 0.0}
    c = df["close"]
    fast, slow = ema(c, 9), ema(c, 21)
    a, _, _ = adx(df, 9)
    score = 0
    score += 35 if fast.iloc[-1] > slow.iloc[-1] else -35
    score += 25 if c.iloc[-1] > fast.iloc[-1] else -25
    score += 20 if fast.iloc[-1] > fast.iloc[-3] else -20
    r = rsi(c, 9).iloc[-1]
    score += 20 if r > 55 else (-20 if r < 45 else 0)
    strength = float(min(a.iloc[-1], 60) / 60 * 100)
    if score >= 60:
        bias = "Tăng mạnh"
    elif score > 0:
        bias = "Tăng nhẹ"
    elif score <= -60:
        bias = "Giảm mạnh"
    elif score < 0:
        bias = "Giảm nhẹ"
    else:
        bias = "Đi ngang"
    if strength < 25 and abs(score) < 60:
        bias = "Đi ngang (" + ("tăng" if score > 0 else "giảm") + ")"
    return {"bias": bias, "score": score, "strength": round(strength, 1)}


def mtf_radar(df: pd.DataFrame) -> pd.DataFrame:
    frames = {
        "Ngày (1D)": df,
        "Tuần (1W)": resample(df, "W-FRI"),
        "Tháng (1M)": resample(df, "ME"),
    }
    rows = []
    for name, d in frames.items():
        tb = trend_bias(d)
        rows.append({"Khung": name, "Xu hướng": tb["bias"], "Điểm": tb["score"], "Sức mạnh %": tb["strength"]})
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# 3. CẤU TRÚC THỊ TRƯỜNG: SWING, BOS, VÙNG CUNG - CẦU
# ---------------------------------------------------------------------------
def swings(df: pd.DataFrame, n: int = 5) -> tuple[pd.Series, pd.Series]:
    hi = df["high"]
    lo = df["low"]
    win = 2 * n + 1
    sh = hi[(hi == hi.rolling(win, center=True).max())]
    sl = lo[(lo == lo.rolling(win, center=True).min())]
    return sh, sl


def market_structure(df: pd.DataFrame, n: int = 5) -> dict:
    sh, sl = swings(df, n)
    events = []  # (time, price, label)
    last_h = last_l = None
    trend = 0
    sh_iter, sl_iter = sh.to_dict(), sl.to_dict()
    for t, row in df.iterrows():
        # đỉnh/đáy chỉ được "xác nhận" sau n phiên
        if last_h is not None and row["close"] > last_h[1]:
            label = "BOS ↑" if trend >= 0 else "CHoCH ↑"
            events.append((t, last_h[1], label))
            trend, last_h = 1, None
        elif last_l is not None and row["close"] < last_l[1]:
            label = "BOS ↓" if trend <= 0 else "CHoCH ↓"
            events.append((t, last_l[1], label))
            trend, last_l = -1, None
        pos = df.index.get_loc(t)
        if pos >= n:
            pt = df.index[pos - n]
            if pt in sh_iter:
                last_h = (pt, sh_iter[pt])
            if pt in sl_iter:
                last_l = (pt, sl_iter[pt])
    # vùng cung (đỉnh swing gần nhất phía trên giá) & cầu (đáy swing gần nhất phía dưới)
    price = df["close"].iloc[-1]
    zones = []
    for t, h in sh[sh > price].iloc[::-1].items():
        body_top = max(df.at[t, "open"], df.at[t, "close"])
        zones.append({"type": "Cung", "time": t, "top": h, "bottom": body_top})
        break
    for t, l in sl[sl < price].iloc[::-1].items():
        body_bot = min(df.at[t, "open"], df.at[t, "close"])
        zones.append({"type": "Cầu", "time": t, "top": body_bot, "bottom": l})
        break
    return {"swing_high": sh, "swing_low": sl, "events": events, "trend": trend, "zones": zones}


# ---------------------------------------------------------------------------
# 4. VOLUME PROFILE (khối lượng theo vùng giá, tách mua/bán)
# ---------------------------------------------------------------------------
def volume_profile(df: pd.DataFrame, bins: int = 40) -> pd.DataFrame:
    lo, hi = df["low"].min(), df["high"].max()
    edges = np.linspace(lo, hi, bins + 1)
    mid = (edges[:-1] + edges[1:]) / 2
    buy = np.zeros(bins)
    sell = np.zeros(bins)
    typical = (df["high"] + df["low"] + df["close"]) / 3
    idx = np.clip(np.digitize(typical, edges) - 1, 0, bins - 1)
    up = (df["close"] >= df["open"]).to_numpy()
    vol = df["volume"].to_numpy()
    np.add.at(buy, idx[up], vol[up])
    np.add.at(sell, idx[~up], vol[~up])
    vp = pd.DataFrame({"price": mid, "buy": buy, "sell": sell})
    vp["total"] = vp["buy"] + vp["sell"]
    # Value Area 70%
    order = vp["total"].sort_values(ascending=False)
    cum = order.cumsum() / vp["total"].sum()
    va_idx = order.index[: (cum <= 0.7).sum() + 1]
    vp["value_area"] = vp.index.isin(va_idx)
    return vp


# ---------------------------------------------------------------------------
# 5. BỘ MÁY TÍN HIỆU + ĐIỂM TIN CẬY + QUẢN LÝ VỊ THẾ
# ---------------------------------------------------------------------------
def analyze(df_raw: pd.DataFrame, lookback_vp: int = 120) -> dict:
    df = add_indicators(df_raw)
    last = df.iloc[-1]
    radar = mtf_radar(df_raw)
    ms = market_structure(df.tail(250))
    vp = volume_profile(df.tail(lookback_vp))
    poc = float(vp.loc[vp["total"].idxmax(), "price"])

    # --- Core analytics
    bull_tf = int((radar["Điểm"] > 0).sum())
    bear_tf = int((radar["Điểm"] < 0).sum())
    agreement = max(bull_tf, bear_tf) / len(radar)
    mtf_dir = 1 if bull_tf > bear_tf else (-1 if bear_tf > bull_tf else 0)

    adx_v = float(last["ADX"])
    regime = "Có xu hướng" if adx_v >= 25 else ("Chớm xu hướng" if adx_v >= 20 else "Đi ngang (sideway)")

    squeeze_now = bool(last["Squeeze"])
    squeeze_recent = bool(df["Squeeze"].iloc[-6:-1].any())
    if squeeze_now:
        vol_state = "Đang nén (sắp bùng nổ)"
    elif squeeze_recent:
        vol_state = "Vừa thoát nén (bùng nổ)"
    else:
        vol_state = "Bình thường"

    last20 = df.tail(20)
    up_vol = last20.loc[last20["close"] >= last20["open"], "volume"].sum()
    dn_vol = last20.loc[last20["close"] < last20["open"], "volume"].sum()
    flow = (up_vol - dn_vol) / max(up_vol + dn_vol, 1)  # -1..+1
    flow_txt = f"{'Mua chủ động' if flow > 0.1 else 'Bán chủ động' if flow < -0.1 else 'Cân bằng'} ({flow:+.0%})"
    vol_ratio = float(last["volume"] / last["VolMA20"]) if last["VolMA20"] else 1.0

    # --- Điểm tin cậy (0-100) cho hướng MUA và hướng BÁN
    def score(direction: int) -> tuple[float, list[str]]:
        pts, why = 0.0, []
        if mtf_dir == direction:
            pts += 30 * agreement
            why.append(f"Đồng thuận đa khung {max(bull_tf, bear_tf)}/{len(radar)}")
        ema_ok = (last["close"] > last["EMA20"] > last["EMA50"]) if direction == 1 else (
            last["close"] < last["EMA20"] < last["EMA50"])
        if ema_ok:
            pts += 15
            why.append("Giá & EMA20/50 xếp đúng hướng")
        di_ok = (last["DI+"] > last["DI-"]) if direction == 1 else (last["DI-"] > last["DI+"])
        if di_ok:
            pts += 15 * min(adx_v, 40) / 40
            why.append(f"ADX {adx_v:.0f} ủng hộ")
        if flow * direction > 0.1:
            pts += 15 * min(abs(flow) / 0.5, 1)
            why.append("Dòng tiền cùng chiều")
        if vol_ratio > 1.2:
            pts += 5
            why.append(f"Khối lượng đột biến {vol_ratio:.1f}x")
        r = last["RSI"]
        if (direction == 1 and 50 < r < 72) or (direction == -1 and 28 < r < 50):
            pts += 10
            why.append(f"RSI {r:.0f} thuận chiều, chưa quá mua/bán")
        if ms["trend"] == direction:
            pts += 10
            why.append("Cấu trúc (BOS) cùng chiều")
        return round(min(pts, 100), 1), why

    buy_s, buy_why = score(1)
    sell_s, sell_why = score(-1)

    filter_ok = adx_v >= 20 and not squeeze_now
    if buy_s >= 65 and buy_s > sell_s and filter_ok:
        signal, conf, why, direction = "🟢 MUA", buy_s, buy_why, 1
    elif buy_s >= 65 and buy_s > sell_s:
        signal, conf, why, direction = "🟡 CHỜ XÁC NHẬN MUA", buy_s, buy_why + [
            "⚠️ Bộ lọc chưa đạt (ADX < 20 hoặc đang nén) → chờ thêm"], 0
    elif sell_s >= 65 and sell_s > buy_s:
        signal, conf, why, direction = "🔴 BÁN / HẠ TỶ TRỌNG", sell_s, sell_why, -1
    else:
        signal, conf, why, direction = "🟡 CHỜ (chưa đủ xác nhận)", max(buy_s, sell_s), (
            buy_why if buy_s >= sell_s else sell_why), 0

    engine_filter = "Sẵn sàng" if filter_ok else ("Chờ - đang nén" if squeeze_now else "Chờ - ADX yếu")

    # --- Quản lý vị thế (chỉ tính cho chiều MUA vì TTCK VN không bán khống cơ sở)
    entry = float(last["close"])
    a = float(last["ATR"])
    recent_low = float(df["low"].tail(10).min())
    sl = min(entry - 1.5 * a, recent_low - 0.2 * a)
    risk = entry - sl
    position = {
        "Giá vào": entry,
        "Cắt lỗ (SL)": sl,
        "TP1 (1R)": entry + risk,
        "TP2 (2R)": entry + 2 * risk,
        "TP3 (3R)": entry + 3 * risk,
        "Rủi ro %": risk / entry * 100,
    }

    return {
        "df": df,
        "radar": radar,
        "structure": ms,
        "vp": vp,
        "poc": poc,
        "core": {
            "Đồng thuận đa khung": f"{max(bull_tf, bear_tf)}/{len(radar)} "
            + ("Tăng" if mtf_dir == 1 else "Giảm" if mtf_dir == -1 else "Lẫn lộn"),
            "Trạng thái thị trường": regime,
            "Biến động": vol_state,
            "Dòng tiền 20 phiên": flow_txt,
        },
        "signal": {
            "Tín hiệu": signal,
            "Điểm tin cậy": conf,
            "Điểm MUA": buy_s,
            "Điểm BÁN": sell_s,
            "ADX": round(adx_v, 1),
            "RSI": round(float(last["RSI"]), 1),
            "Bộ lọc": engine_filter,
            "Lý do": why,
            "direction": direction,
        },
        "position": position,
        "vol_ratio": vol_ratio,
    }
