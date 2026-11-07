"""
Chấm điểm CƠ BẢN (FA) - thang 50 điểm.

| Tiêu chí              | Tối đa | Ý nghĩa                                   |
|-----------------------|--------|-------------------------------------------|
| ROE                   | 15     | Hiệu quả sinh lời trên vốn chủ            |
| Tăng trưởng LNST      | 10     | Lợi nhuận năm gần nhất so với năm trước   |
| P/E                   | 10     | Đắt / rẻ so với lợi nhuận                 |
| Nợ / Vốn chủ          | 10     | Mức độ an toàn tài chính                  |
| P/B                   | 5      | Đắt / rẻ so với giá trị sổ sách           |

Chỉ tiêu nào không lấy được dữ liệu -> cho điểm trung tính (một nửa) và ghi chú "thiếu dữ liệu".
"""
from __future__ import annotations

import re

import numpy as np
import pandas as pd

# Từ khóa nhận diện cột trong bảng chỉ số (vnstock trả về tên cột khác nhau tùy nguồn / phiên bản)
KEYS = {
    "roe": [r"^roe", r"\broe\b"],
    "pe": [r"^p/e$", r"p/e\b", r"priceto?earning", r"^pe$"],
    "pb": [r"^p/b$", r"p/b\b", r"priceto?book", r"^pb$"],
    "de": [r"^nợ/vcsh", r"nợ.*/.*vcsh", r"debt.?(on|to).?equity", r"\(vay.*\)/vcsh", r"^d/e"],
    "growth": [r"tăng trưởng lợi nhuận", r"lnst.*yoy", r"net.?profit.?growth", r"profit.?growth",
               r"earning.?growth", r"epschange"],
    "year": [r"yearreport", r"^năm$", r"^year$"],
    "eps": [r"^eps", r"earningpershare"],
}


def _flatten(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [str(c[-1]) for c in df.columns]
    df.columns = [str(c).strip() for c in df.columns]
    return df


def _find(df: pd.DataFrame, key: str) -> str | None:
    for pat in KEYS[key]:
        for c in df.columns:
            if re.search(pat, c.lower().replace(" ", "")) or re.search(pat, c.lower()):
                return c
    return None


def _sorted(df: pd.DataFrame) -> pd.DataFrame:
    """Sắp xếp năm tăng dần (dòng cuối = năm mới nhất)."""
    ycol = _find(df, "year")
    if ycol is not None:
        return df.sort_values(ycol)
    # nguồn TCBS thường sắp năm mới nhất ở dòng đầu
    return df.iloc[::-1]


def _num(x) -> float | None:
    try:
        v = float(x)
        return None if np.isnan(v) else v
    except (TypeError, ValueError):
        return None


def _pct(v: float | None) -> float | None:
    """Đưa về đơn vị %, nguồn có thể trả 0.18 hoặc 18."""
    if v is None:
        return None
    return v * 100 if abs(v) <= 2 else v


def extract_metrics(ratio: pd.DataFrame) -> dict:
    df = _sorted(_flatten(ratio))
    row = df.iloc[-1]
    out = {}
    for k in ("roe", "pe", "pb", "de", "growth"):
        c = _find(df, k)
        out[k] = _num(row[c]) if c is not None else None
    out["roe"] = _pct(out["roe"])
    out["growth"] = _pct(out["growth"])
    # Không có cột tăng trưởng -> tự tính từ EPS 2 năm gần nhất
    eps_col = _find(df, "eps")
    if out["growth"] is None and eps_col is not None and len(df) >= 2:
        now, prev = _num(df[eps_col].iloc[-1]), _num(df[eps_col].iloc[-2])
        if now is not None and prev and prev > 0:
            out["growth"] = (now / prev - 1) * 100
    return out


def load_fundamentals(ticker: str) -> dict:
    """Lấy chỉ số tài chính năm gần nhất từ vnstock."""
    errors = []
    try:
        from vnstock import Vnstock  # type: ignore

        for source in ("VCI", "TCBS"):
            try:
                fin = Vnstock().stock(symbol=ticker, source=source).finance
                try:
                    ratio = fin.ratio(period="year", lang="vi", dropna=True)
                except TypeError:
                    ratio = fin.ratio(period="year")
                if ratio is not None and not ratio.empty:
                    m = extract_metrics(ratio)
                    if any(v is not None for v in m.values()):
                        m["source"] = source
                        return m
            except Exception as e:
                errors.append(f"{source}: {e}")
    except ImportError as e:
        errors.append(str(e))
    raise RuntimeError("Không lấy được chỉ số tài chính: " + " | ".join(errors))


def demo_fundamentals(ticker: str) -> dict:
    rng = np.random.default_rng(sum(ord(c) for c in ticker) + 7)
    return {
        "roe": round(float(rng.uniform(4, 28)), 1),
        "pe": round(float(rng.uniform(5, 25)), 1),
        "pb": round(float(rng.uniform(0.7, 3.5)), 2),
        "de": round(float(rng.uniform(0.2, 2.2)), 2),
        "growth": round(float(rng.uniform(-30, 60)), 1),
        "source": "Dữ liệu mẫu",
    }


def score_fundamentals(m: dict) -> dict:
    rows = []  # (tiêu chí, giá trị hiển thị, điểm, tối đa, nhận xét)

    def add(name, val_txt, pts, mx, note):
        rows.append({"Tiêu chí": name, "Giá trị": val_txt, "Điểm": pts, "Tối đa": mx, "Nhận xét": note})

    roe = m.get("roe")
    if roe is None:
        add("ROE", "—", 7.5, 15, "Thiếu dữ liệu")
    else:
        pts = 15 if roe >= 20 else 11 if roe >= 15 else 7 if roe >= 10 else 3 if roe > 0 else 0
        add("ROE", f"{roe:.1f}%", pts, 15,
            "Rất tốt" if roe >= 20 else "Tốt" if roe >= 15 else "Trung bình" if roe >= 10 else "Yếu")

    g = m.get("growth")
    if g is None:
        add("Tăng trưởng LNST", "—", 5, 10, "Thiếu dữ liệu")
    else:
        pts = 10 if g >= 20 else 7 if g >= 10 else 4 if g >= 0 else 0
        add("Tăng trưởng LNST", f"{g:+.1f}%", pts, 10,
            "Tăng mạnh" if g >= 20 else "Tăng" if g >= 0 else "Suy giảm")

    pe = m.get("pe")
    if pe is None:
        add("P/E", "—", 5, 10, "Thiếu dữ liệu")
    elif pe <= 0:
        add("P/E", f"{pe:.1f}", 0, 10, "Đang lỗ")
    else:
        pts = 10 if pe <= 10 else 7 if pe <= 15 else 4 if pe <= 20 else 1
        add("P/E", f"{pe:.1f}", pts, 10,
            "Rẻ" if pe <= 10 else "Hợp lý" if pe <= 15 else "Hơi đắt" if pe <= 20 else "Đắt")

    de = m.get("de")
    if de is None:
        add("Nợ / Vốn chủ", "—", 5, 10, "Thiếu dữ liệu")
    elif de > 5:
        # Ngân hàng / chứng khoán có đòn bẩy đặc thù -> không chấm tiêu chí này
        add("Nợ / Vốn chủ", f"{de:.2f}", 5, 10, "Đòn bẩy đặc thù (ngân hàng?) - trung tính")
    else:
        pts = 10 if de <= 0.5 else 7 if de <= 1 else 4 if de <= 2 else 1
        add("Nợ / Vốn chủ", f"{de:.2f}", pts, 10,
            "An toàn" if de <= 0.5 else "Ổn" if de <= 1 else "Cao" if de <= 2 else "Rủi ro")

    pb = m.get("pb")
    if pb is None:
        add("P/B", "—", 2.5, 5, "Thiếu dữ liệu")
    else:
        pts = 5 if pb <= 1.5 else 3 if pb <= 2.5 else 1
        add("P/B", f"{pb:.2f}", pts, 5, "Rẻ" if pb <= 1.5 else "Hợp lý" if pb <= 2.5 else "Đắt")

    table = pd.DataFrame(rows)
    total = float(table["Điểm"].sum())
    missing = int((table["Nhận xét"] == "Thiếu dữ liệu").sum())
    if total >= 38:
        grade = "A - Doanh nghiệp tốt, giá hợp lý"
    elif total >= 30:
        grade = "B - Khá"
    elif total >= 22:
        grade = "C - Trung bình"
    else:
        grade = "D - Yếu / đắt"
    return {"score": total, "grade": grade, "table": table, "missing": missing,
            "source": m.get("source", "")}


def overall(fa_score: float, ta_buy_score: float) -> dict:
    """Tổng điểm 100 = FA (50) + TA (điểm MUA 0-100 quy về 50)."""
    total = round(fa_score + ta_buy_score / 2, 1)
    if total >= 75:
        verdict = "🟢 Ưu tiên giải ngân"
    elif total >= 60:
        verdict = "🔵 Theo dõi sát, chờ điểm mua"
    elif total >= 45:
        verdict = "🟡 Trung tính"
    else:
        verdict = "🔴 Tránh / hạ tỷ trọng"
    return {"total": total, "verdict": verdict}
