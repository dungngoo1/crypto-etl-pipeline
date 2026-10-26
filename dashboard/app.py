"""Dashboard: số liệu + biểu đồ từ schema `ga` (release publish gần nhất).

Chạy:  streamlit run dashboard/app.py
Kết nối lấy từ biến môi trường (giống .env của project):
    WAREHOUSE_HOST (mặc định localhost), WAREHOUSE_PORT (mặc định 5433),
    WAREHOUSE_DB, WAREHOUSE_USER, WAREHOUSE_PASSWORD
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pandas as pd  # noqa: E402
import psycopg2  # noqa: E402
import streamlit as st  # noqa: E402

import charts as C  # noqa: E402

st.set_page_config(page_title="Crypto Market Snapshot", layout="wide")

DB = {
    "host": os.getenv("WAREHOUSE_HOST", "localhost"),
    "port": int(os.getenv("WAREHOUSE_PORT", "5433")),
    "dbname": os.getenv("WAREHOUSE_DB", "crypto_dw"),
    "user": os.getenv("WAREHOUSE_USER", "dw_user"),
    "password": os.getenv("WAREHOUSE_PASSWORD", ""),
}
STALE_AFTER_MINUTES = 120  # khớp ngưỡng lỗi của source freshness
TOP_VOLUME_POOL = 100  # top tăng/giảm chỉ xét N cặp có volume cao nhất


@st.cache_data(ttl=60)
def query(sql: str) -> pd.DataFrame:
    conn = psycopg2.connect(**DB)
    cur = conn.cursor()
    try:
        cur.execute(sql)
        cols = [d[0] for d in cur.description]
        return pd.DataFrame(cur.fetchall(), columns=cols)
    finally:
        cur.close()
        conn.close()


def to_num(df: pd.DataFrame, cols) -> pd.DataFrame:
    df = df.copy()
    for c in cols:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


def theme_mode() -> str:
    try:
        return "dark" if st.context.theme.type == "dark" else "light"
    except Exception:
        return "light"


def tint(hex_color: str, alpha: float = 0.20) -> str:
    r, g, b = (int(hex_color[i : i + 2], 16) for i in (1, 3, 5))
    return f"background-color: rgba({r},{g},{b},{alpha})"


def show_table(df: pd.DataFrame, p: dict) -> None:
    """Bảng số liệu: chữ giữ màu thường, ô 'Thay đổi' tô nền nhạt + có ▲/▼ và dấu +/-."""
    disp = pd.DataFrame(
        {
            "Cặp": df["symbol"],
            "Giá": df["current_price"].map(C.price_txt),
            "Thay đổi 24h": df["chg"].map(C.arrow_pct),
            "Quote volume 24h": df["volume_quote_24h"].map(
                lambda v: "" if pd.isna(v) else f"{v:,.0f}"
            ),
        }
    )
    disp.index = range(1, len(disp) + 1)
    chg = df["chg"].tolist()

    def paint(_col):
        return [tint(p["up"]) if v > 0 else tint(p["down"]) if v < 0 else "" for v in chg]

    st.dataframe(disp.style.apply(paint, subset=["Thay đổi 24h"]), width="stretch")


# ---------- Tiêu đề & trạng thái release ----------
head_l, head_r = st.columns([5, 1])
head_l.title("Crypto Market Snapshot")
if head_r.button("Làm mới"):
    st.cache_data.clear()
    st.rerun()

try:
    status = query("SELECT * FROM ga.publication_status")
except psycopg2.Error as exc:
    st.error(
        "Không đọc được schema `ga`. Kiểm tra Docker đang chạy, biến môi trường "
        "WAREHOUSE_* và DAG đã publish ít nhất một lần.\n\n"
        f"Chi tiết: {str(exc).strip()}"
    )
    st.stop()

if status.empty:
    st.info("Chưa có batch nào được publish. Hãy trigger DAG trong Airflow rồi tải lại trang.")
    st.stop()

row = status.iloc[0]
batch_id = row["batch_id"]
captured_at = pd.to_datetime(row.get("captured_at"), utc=True, errors="coerce")
published_at = pd.to_datetime(row.get("published_at"), utc=True, errors="coerce")

parts = [f"Batch: `{batch_id}`"]
if pd.notna(captured_at):
    parts.append(f"thu thập lúc {captured_at:%Y-%m-%d %H:%M} UTC")
if pd.notna(published_at):
    parts.append(f"publish lúc {published_at:%Y-%m-%d %H:%M} UTC")
st.caption(" · ".join(parts))

if pd.notna(captured_at):
    age_min = int((pd.Timestamp.now(tz="UTC") - captured_at).total_seconds() // 60)
    if age_min > STALE_AFTER_MINUTES:
        st.warning(f"Dữ liệu đã cũ: snapshot cách đây {age_min} phút (ngưỡng {STALE_AFTER_MINUTES} phút).")
else:
    age_min = None

# ---------- KPI toàn thị trường ----------
overview = query(
    "SELECT * FROM ga.market_overview "
    "WHERE batch_id = (SELECT batch_id FROM ga.publication_status)"
)
overview = to_num(overview, ["returned_pairs", "active_pairs", "excluded_pairs"])

k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Cặp Binance trả về", f"{int(overview['returned_pairs'].sum()):,}")
k2.metric("Cặp đủ điều kiện phân tích", f"{int(overview['active_pairs'].sum()):,}")
k3.metric("Cặp bị loại", f"{int(overview['excluded_pairs'].sum()):,}")
k4.metric("Số quote asset", f"{overview['quote_asset'].nunique():,}")
k5.metric("Tuổi snapshot", "n/a" if age_min is None else f"{age_min} phút")

# ---------- Dữ liệu ticker ----------
tickers = query(
    "SELECT symbol, quote_asset, current_price, price_change_percent_24h, "
    "volume_quote_24h, volume_rank FROM ga.latest_tickers"
)
tickers = to_num(
    tickers, ["current_price", "price_change_percent_24h", "volume_quote_24h", "volume_rank"]
).rename(columns={"price_change_percent_24h": "chg"})
tickers = tickers.dropna(subset=["chg"])

if tickers.empty:
    st.info("Bảng `ga.latest_tickers` đang trống.")
    st.stop()

# ---------- Bộ lọc (một hàng phía trên biểu đồ) ----------
quotes = tickers["quote_asset"].value_counts().index.tolist()
default = quotes.index("USDT") if "USDT" in quotes else 0
f1, f2 = st.columns([1, 2])
quote = f1.selectbox("Quote asset", quotes, index=default)
scheme = f2.radio("Bảng màu tăng/giảm", list(C.SCHEMES), horizontal=True)
p = C.palette(scheme, theme_mode())

sel = tickers[tickers["quote_asset"] == quote]
pool = sel.sort_values("volume_rank").head(TOP_VOLUME_POOL)

# ---------- Độ rộng thị trường của quote đã chọn ----------
n = len(sel)
n_up = int((sel["chg"] > 0).sum())
n_down = int((sel["chg"] < 0).sum())
n_flat = n - n_up - n_down
b1, b2, b3, b4 = st.columns(4)
b1.metric(f"Cặp tăng ▲ ({quote})", f"{n_up:,} ({n_up / n:.0%})")
b2.metric(f"Cặp giảm ▼ ({quote})", f"{n_down:,} ({n_down / n:.0%})")
b3.metric("Đi ngang (0%)", f"{n_flat:,} ({n_flat / n:.0%})")
b4.metric("Trung vị thay đổi 24h", f"{sel['chg'].median():+.2f}%")

st.markdown(
    f'<span style="color:{p["up"]}">■</span> Tăng ▲ &nbsp;&nbsp; '
    f'<span style="color:{p["down"]}">■</span> Giảm ▼ &nbsp;&nbsp; '
    f'<span style="color:{p["flat"]}">■</span> Đi ngang (0%)',
    unsafe_allow_html=True,
)

# ---------- Biểu đồ ----------
c1, c2 = st.columns(2)
with c1:
    st.subheader("Phân bố thay đổi 24h")
    st.caption(f"Số cặp {quote} theo mức thay đổi; ≥10% và ≤-10% được gộp ở hai đầu.")
    st.altair_chart(C.histogram(sel, p), width="stretch")
with c2:
    st.subheader("Top tăng / giảm mạnh nhất")
    st.caption(f"Chỉ xét {TOP_VOLUME_POOL} cặp {quote} có volume cao nhất.")
    st.altair_chart(C.movers(pool, p), width="stretch")

st.subheader("Top 10 theo quote volume")
st.caption("Độ dài thanh là volume, màu là hướng thay đổi 24h.")
st.altair_chart(C.top_volume(sel, p), width="stretch")

# ---------- Bảng số liệu ----------
with st.expander("Xem bảng số liệu"):
    st.markdown("**Coverage theo quote asset**")
    st.dataframe(
        overview.sort_values("active_pairs", ascending=False).drop(columns=["batch_id"]),
        hide_index=True,
        width="stretch",
    )
    st.markdown(f"**Top 10 theo quote volume ({quote})**")
    show_table(sel.sort_values("volume_rank").head(10), p)
    t1, t2 = st.columns(2)
    with t1:
        st.markdown("**Top 10 tăng mạnh nhất**")
        show_table(pool.nlargest(10, "chg"), p)
    with t2:
        st.markdown("**Top 10 giảm mạnh nhất**")
        show_table(pool.nsmallest(10, "chg"), p)

st.caption(
    "Các số đo 24h là rolling window, không phải ngày lịch. "
    "Chỉ so sánh volume trong cùng một quote asset."
)
