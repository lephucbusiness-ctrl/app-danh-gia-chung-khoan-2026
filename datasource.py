"""
Nguồn dữ liệu (không dùng vnstock - gói này đang bị PyPI cách ly).

Thứ tự thử:
  Giá lịch sử : 1) Yahoo Finance (mã dạng HPG.VN, chủ yếu sàn HOSE)
                2) VNDirect  3) Vietcap  (có cả HNX, UPCoM)  4) TCBS
  Chỉ số TC   : 1) API công khai TCBS                         2) Yahoo Finance
"""
from __future__ import annotations

import time
from datetime import datetime, timedelta

import pandas as pd
import requests

HEADERS = {"User-Agent": "Mozilla/5.0 (radar-co-phieu)", "Accept": "application/json"}
TCBS = "https://apipubaws.tcbs.com.vn"


def _clean(df: pd.DataFrame) -> pd.DataFrame:
    df = df.rename(columns=str.lower)
    df.index = pd.to_datetime(df.index)
    if df.index.tz is not None:
        df.index = df.index.tz_localize(None)
    df.index = df.index.normalize()
    df = df[["open", "high", "low", "close", "volume"]].astype(float)
    df = df[(df["close"] > 0)].dropna()
    return df[~df.index.duplicated(keep="last")].sort_index()


# ----------------------------------------------------------------- GIÁ
def price_yahoo(ticker: str, days: int) -> pd.DataFrame:
    import yfinance as yf

    df = yf.Ticker(f"{ticker}.VN").history(
        start=(datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d"),
        interval="1d", auto_adjust=False,
    )
    if df is None or df.empty:
        raise ValueError("Yahoo không có dữ liệu")
    return _clean(df)


def price_tcbs(ticker: str, days: int) -> pd.DataFrame:
    now = int(time.time())
    r = requests.get(
        f"{TCBS}/stock-insight/v2/stock/bars-long-term",
        params={"ticker": ticker, "type": "stock", "resolution": "D",
                "from": now - days * 86400, "to": now, "countBack": days},
        headers=HEADERS, timeout=20,
    )
    if r.status_code != 200:  # thử bản API cũ
        r = requests.get(
            f"{TCBS}/stock-insight/v1/stock/bars-long-term",
            params={"ticker": ticker, "type": "stock", "resolution": "D",
                    "from": now - days * 86400, "to": now},
            headers=HEADERS, timeout=20,
        )
    r.raise_for_status()
    data = r.json().get("data") or []
    if not data:
        raise ValueError("TCBS không có dữ liệu")
    df = pd.DataFrame(data)
    df.index = pd.to_datetime(df["tradingDate"].astype(str).str[:10])
    return _clean(df)


def _from_arrays(t, o, h, l, c, v) -> pd.DataFrame:
    """Dạng dữ liệu TradingView: các mảng t (unix giây), o, h, l, c, v."""
    df = pd.DataFrame({"open": o, "high": h, "low": l, "close": c, "volume": v},
                      index=pd.to_datetime(pd.Series(t, dtype="int64"), unit="s"))
    df = df.astype(float)
    if len(df) and df["close"].median() < 1000:  # nguồn trả giá theo nghìn đồng
        df[["open", "high", "low", "close"]] *= 1000
    return _clean(df)


def price_vndirect(ticker: str, days: int) -> pd.DataFrame:
    now = int(time.time())
    r = requests.get(
        "https://dchart-api.vndirect.com.vn/dchart/history",
        params={"resolution": "D", "symbol": ticker, "from": now - days * 86400, "to": now},
        headers=HEADERS, timeout=20,
    )
    r.raise_for_status()
    j = r.json()
    if j.get("s") != "ok" or not j.get("t"):
        raise ValueError("VNDirect không có dữ liệu")
    return _from_arrays(j["t"], j["o"], j["h"], j["l"], j["c"], j["v"])


def price_vietcap(ticker: str, days: int) -> pd.DataFrame:
    body = {"timeFrame": "ONE_DAY", "symbols": [ticker], "to": int(time.time()), "countBack": days}
    hdr = {**HEADERS, "Content-Type": "application/json",
           "Referer": "https://trading.vietcap.com.vn/", "Origin": "https://trading.vietcap.com.vn"}
    last_err = None
    for path in ("gap-chart", "gap"):
        try:
            r = requests.post(f"https://trading.vietcap.com.vn/api/chart/OHLCChart/{path}",
                              json=body, headers=hdr, timeout=20)
            r.raise_for_status()
            j = r.json()
            item = j[0] if isinstance(j, list) and j else j
            if item and item.get("t"):
                return _from_arrays(item["t"], item["o"], item["h"], item["l"], item["c"], item["v"])
            last_err = ValueError("Vietcap không có dữ liệu")
        except Exception as e:
            last_err = e
    raise last_err


def load_price(ticker: str, days: int = 730) -> pd.DataFrame:
    errors = []
    sources = (("Yahoo", price_yahoo), ("VNDirect", price_vndirect),
               ("Vietcap", price_vietcap), ("TCBS", price_tcbs))
    for name, fn in sources:
        try:
            df = fn(ticker, days)
            if len(df) >= 60:
                df.attrs["source"] = name
                return df
            errors.append(f"{name}: chỉ có {len(df)} phiên")
        except Exception as e:
            errors.append(f"{name}: {e}")
    raise RuntimeError(f"Không tải được giá {ticker}. " + " | ".join(errors))


# ----------------------------------------------------------------- CHỈ SỐ TÀI CHÍNH
def ratio_tcbs(ticker: str) -> pd.DataFrame:
    r = requests.get(
        f"{TCBS}/tcanalysis/v1/finance/{ticker}/financialratio",
        params={"yearly": 1, "isAll": "true"}, headers=HEADERS, timeout=20,
    )
    r.raise_for_status()
    data = r.json()
    if isinstance(data, dict):
        data = data.get("data") or data.get("listFinancialRatio") or []
    df = pd.DataFrame(data)
    if df.empty:
        raise ValueError("TCBS không có chỉ số tài chính")
    if "quarter" in df.columns:  # chỉ giữ số liệu cả năm
        yearly = df[df["quarter"].isin([5, 0]) | df["quarter"].isna()]
        df = yearly if not yearly.empty else df
    return df


def metrics_yahoo(ticker: str) -> dict:
    import yfinance as yf

    info = yf.Ticker(f"{ticker}.VN").info or {}

    def g(k):
        v = info.get(k)
        return float(v) if isinstance(v, (int, float)) else None

    roe, de, growth = g("returnOnEquity"), g("debtToEquity"), g("earningsGrowth")
    m = {
        "roe": roe * 100 if roe is not None else None,
        "pe": g("trailingPE"),
        "pb": g("priceToBook"),
        "de": de / 100 if de is not None else None,  # Yahoo trả theo %
        "growth": growth * 100 if growth is not None else None,
    }
    if all(v is None for v in m.values()):
        raise ValueError("Yahoo không có chỉ số tài chính")
    return m
