"""Dựng biểu đồ (Altair) cho dashboard. Không phụ thuộc Streamlit nên dễ test/render.

Quy ước màu: màu chỉ mang MỘT nghĩa duy nhất trong cả trang là hướng thay đổi 24h
(tăng / giảm / đi ngang). Màu không bao giờ là dấu hiệu duy nhất: luôn kèm ▲/▼, dấu +/-
và vị trí thanh so với đường 0. Cặp màu đã chạy validate_palette (xem README dashboard).
"""
import altair as alt
import numpy as np
import pandas as pd

UP, DOWN, FLAT = "Tăng", "Giảm", "Đi ngang"
NEUTRAL = "#898781"

# (tăng, giảm) cho từng chế độ sáng/tối. Mỗi cặp đã validate trên nền #ffffff / #0e1117.
SCHEMES = {
    "Xanh lá – Đỏ": {"light": ("#008300", "#e34948"), "dark": ("#0ca30c", "#e66767")},
    "Xanh dương – Đỏ (an toàn mù màu)": {
        "light": ("#2a78d6", "#e34948"),
        "dark": ("#3987e5", "#e66767"),
    },
}
INK = {
    "light": {"primary": "#0b0b0b", "secondary": "#52514e", "base": "#c3c2b7"},
    "dark": {"primary": "#f0efec", "secondary": "#c3c2b7", "base": "#383835"},
}


def palette(scheme: str, mode: str) -> dict:
    up, down = SCHEMES[scheme][mode]
    return {"up": up, "down": down, "flat": NEUTRAL, **INK[mode]}


def color_scale(p: dict) -> alt.Scale:
    return alt.Scale(domain=[UP, DOWN, FLAT], range=[p["up"], p["down"], p["flat"]])


def direction(s: pd.Series) -> np.ndarray:
    return np.select([s > 0, s < 0], [UP, DOWN], default=FLAT)


def arrow_pct(v: float) -> str:
    if pd.isna(v):
        return ""
    if v > 0:
        return f"▲ {v:+.2f}%"
    if v < 0:
        return f"▼ {v:+.2f}%"
    return "– 0.00%"


def compact(v: float) -> str:
    if pd.isna(v):
        return ""
    for div, suffix in ((1e12, "T"), (1e9, "B"), (1e6, "M"), (1e3, "K")):
        if abs(v) >= div:
            return f"{v / div:.2f}{suffix}"
    return f"{v:.0f}"


def price_txt(v: float) -> str:
    return "" if pd.isna(v) else f"{v:,.8g}"


def _tooltip_cols(df: pd.DataFrame) -> pd.DataFrame:
    """Chuẩn bị chuỗi hiển thị sẵn cho tooltip (tránh phụ thuộc định dạng d3)."""
    return df.assign(
        dir=direction(df["chg"]),
        label=df["chg"].map(arrow_pct),
        price=df["current_price"].map(price_txt),
        vol=df["volume_quote_24h"].map(compact),
    )


_TIP = [
    alt.Tooltip("symbol:N", title="Cặp"),
    alt.Tooltip("label:N", title="Thay đổi 24h"),
    alt.Tooltip("price:N", title="Giá"),
    alt.Tooltip("vol:N", title="Quote volume 24h"),
]


def histogram(df: pd.DataFrame, p: dict) -> alt.Chart:
    """Phân bố thay đổi 24h: mỗi cột 1%, gộp đuôi ở ±10%. Cột 0 (±0,5%) màu trung tính."""
    k = np.floor(df["chg"].clip(-10, 10) + 0.5).astype(int)
    counts = k.value_counts().reindex(range(-10, 11), fill_value=0)
    out = pd.DataFrame({"k": counts.index, "n": counts.values})
    out["dir"] = np.select([out.k > 0, out.k < 0], [UP, DOWN], default=FLAT)

    def rng(v: int) -> str:
        if v == 10:
            return "≥ +9.5%"
        if v == -10:
            return "≤ -9.5%"
        return f"{v - 0.5:+.1f}% → {v + 0.5:+.1f}%"

    out["range"] = out["k"].map(rng)
    out["tick"] = out["k"].map(lambda v: "≥10" if v == 10 else "≤-10" if v == -10 else str(v))
    return (
        alt.Chart(out)
        .mark_bar(cornerRadiusTopLeft=3, cornerRadiusTopRight=3)
        .encode(
            x=alt.X(
                "tick:N",
                sort=out["tick"].tolist(),
                title="Thay đổi 24h (%), mỗi cột 1%",
                axis=alt.Axis(labelAngle=0, labelOverlap=True),
            ),
            y=alt.Y("n:Q", title="Số cặp"),
            color=alt.Color("dir:N", scale=color_scale(p), legend=None),
            tooltip=[alt.Tooltip("range:N", title="Khoảng"), alt.Tooltip("n:Q", title="Số cặp")],
        )
        .properties(height=280)
    )


def movers(df: pd.DataFrame, p: dict, n: int = 10) -> alt.LayerChart:
    """Top n tăng + top n giảm: thanh phân kỳ quanh đường 0, nhãn trực tiếp ở đầu thanh."""
    top = pd.concat([df.nlargest(n, "chg"), df.nsmallest(n, "chg")]).drop_duplicates("symbol")
    top = _tooltip_cols(top).sort_values("chg", ascending=False)
    lo, hi = min(float(top["chg"].min()), 0.0), max(float(top["chg"].max()), 0.0)
    pad = 0.24 * max(hi - lo, 1e-9)  # chừa chỗ cho nhãn ở hai đầu
    domain = [lo - pad if lo < 0 else 0.0, hi + pad if hi > 0 else 0.0]
    x = alt.X(
        "chg:Q",
        title="Thay đổi 24h (%)",
        scale=alt.Scale(domain=domain, nice=False),
        axis=alt.Axis(labelExpr="datum.value > 0 ? '+' + datum.value : datum.value"),
    )
    y = alt.Y("symbol:N", title=None, sort=top["symbol"].tolist())
    bars = (
        alt.Chart(top)
        .mark_bar(cornerRadiusEnd=4, size=14)
        .encode(
            x=x,
            y=y,
            color=alt.Color("dir:N", scale=color_scale(p), legend=None),
            tooltip=_TIP,
        )
    )
    text_kw = dict(fontSize=11, color=p["primary"])
    pos = (
        alt.Chart(top)
        .mark_text(align="left", dx=5, **text_kw)
        .encode(x="chg:Q", y=y, text="label:N")
        .transform_filter("datum.chg >= 0")
    )
    neg = (
        alt.Chart(top)
        .mark_text(align="right", dx=-5, **text_kw)
        .encode(x="chg:Q", y=y, text="label:N")
        .transform_filter("datum.chg < 0")
    )
    zero = (
        alt.Chart(pd.DataFrame({"z": [0]})).mark_rule(color=p["base"]).encode(x="z:Q")
    )
    return alt.layer(bars, pos, neg, zero).properties(height=22 * len(top) + 36)


def top_volume(df: pd.DataFrame, p: dict, n: int = 10) -> alt.LayerChart:
    """Top n theo quote volume. Độ dài = volume, màu = hướng thay đổi 24h."""
    top = df.sort_values("volume_rank").head(n)
    top = _tooltip_cols(top)
    top["bar_label"] = top["vol"] + "  " + top["label"]
    x = alt.X(
        "volume_quote_24h:Q",
        title="Quote volume 24h",
        scale=alt.Scale(domain=[0, float(top["volume_quote_24h"].max()) * 1.45]),
        axis=alt.Axis(format="~s"),
    )
    y = alt.Y("symbol:N", title=None, sort=top["symbol"].tolist())
    bars = (
        alt.Chart(top)
        .mark_bar(cornerRadiusEnd=4, size=14)
        .encode(
            x=x,
            y=y,
            color=alt.Color("dir:N", scale=color_scale(p), legend=None),
            tooltip=_TIP,
        )
    )
    text = (
        alt.Chart(top)
        .mark_text(align="left", dx=5, fontSize=11, color=p["primary"])
        .encode(x="volume_quote_24h:Q", y=y, text="bar_label:N")
    )
    return alt.layer(bars, text).properties(height=24 * len(top) + 36)
