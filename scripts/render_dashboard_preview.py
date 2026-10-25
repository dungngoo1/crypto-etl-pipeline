"""Render a clearly labeled layout preview from the captured GA CSV evidence, not Power BI."""
import csv
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "docs/evidence"


def main():
    rows = list(csv.DictReader((EVIDENCE / "latest_tickers.csv").open(encoding="utf-8-sig")))
    rows = [r for r in rows if r["quote_asset"] == "USDT"]
    summary = json.loads((EVIDENCE / "summary.json").read_text())
    plt.rcParams.update({"font.family": "Segoe UI", "font.size": 10, "axes.unicode_minus": False})
    fig = plt.figure(figsize=(16, 10), dpi=120, facecolor="#F3F6FA")
    navy, muted, teal, red = "#102A43", "#62788A", "#0D9488", "#E35460"

    def text(x, y, value, size=11, color=navy, weight="normal", **kwargs):
        fig.text(x, y, value, fontsize=size, color=color, fontweight=weight, **kwargs)

    def panel(x, y, w, h):
        fig.add_artist(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.004,rounding_size=0.009",
                                     facecolor="white", edgecolor="#E2E8F0", linewidth=0.8,
                                     transform=fig.transFigure, zorder=0))

    text(.035, .94, "CRYPTO / MARKET SNAPSHOT", 25, weight="bold")
    text(.035, .905, "All returned tickers captured  /  active spot pairs for analysis", 11, muted)
    panel(.81, .905, .155, .063)
    text(.825, .943, "QUOTE ASSET", 9, muted)
    text(.825, .917, "USDT", 16, weight="bold")
    vol = sum(float(r["volume_quote_24h"]) for r in rows)
    avg = sum(float(r["price_change_percent_24h"]) for r in rows) / len(rows)
    cards = [
        ("ACTIVE USDT PAIRS", f"{len(rows):,}", navy),
        ("ROLLING VOLUME / USDT", f"{vol / 1e9:,.2f} B", navy),
        ("AVERAGE PAIR CHANGE / 24H", f"{avg:+.2f}%", teal if avg >= 0 else red),
        ("ALL RETURNED TICKERS", f"{summary['raw_tickers']:,}", navy),
    ]
    for i, (label, value, color) in enumerate(cards):
        x = .035 + i * .236
        panel(x, .762, .219, .112)
        text(x + .014, .842, label, 9, muted)
        text(x + .014, .786, value, 26, color, "bold")

    gain = sorted(rows, key=lambda r: float(r["price_change_percent_24h"]), reverse=True)[:10]
    loss = sorted(rows, key=lambda r: float(r["price_change_percent_24h"]))[:10]
    for items, x, title, color in [(gain, .035, "Top gainers", teal), (loss, .51, "Top losers", red)]:
        panel(x, .386, .455, .347)
        text(x + .014, .701, title, 15, weight="bold")
        text(x + .014, .676, "Rolling 24h price change (%)", 9, muted)
        ax = fig.add_axes([x + .088, .424, .336, .23], facecolor="white", zorder=1)
        values = [float(r["price_change_percent_24h"]) for r in items]
        labels = [r["symbol"] for r in items]
        ax.barh(labels, values, color=color, height=.58)
        ax.invert_yaxis()
        ax.tick_params(axis="both", length=0, labelsize=9, colors=muted)
        for spine in ax.spines.values():
            spine.set_visible(False)
        ax.grid(axis="x", color="#EAF0F5", linewidth=.7)
        ax.set_axisbelow(True)
        lo, hi = min(0, min(values)), max(0, max(values))
        span = max(hi - lo, 1)
        ax.set_xlim(lo - span * .18, hi + span * .2)
        for y, value in enumerate(values):
            ax.text(value + (span * .025 if value >= 0 else -span * .025), y, f"{value:+.2f}%",
                    va="center", ha="left" if value >= 0 else "right", fontsize=8, color=navy)

    panel(.035, .095, .93, .26)
    text(.05, .322, "Most liquid pairs", 15, weight="bold")
    text(.05, .296, "Selected quote: USDT  /  rolling 24h volume, not hourly traded volume", 9, muted)
    ax = fig.add_axes([.047, .116, .906, .159], zorder=1)
    ax.axis("off")
    liquid = sorted(rows, key=lambda r: float(r["volume_quote_24h"]), reverse=True)[:6]
    values = [[r["symbol"], f"{float(r['current_price']):,.6g}",
               f"{float(r['price_change_percent_24h']):+.2f}%",
               f"{float(r['volume_quote_24h']):,.0f}", f"{int(r['trade_count_24h']):,}"] for r in liquid]
    table = ax.table(cellText=values, colLabels=["PAIR", "LAST PRICE", "CHANGE 24H", "QUOTE VOLUME", "TRADES 24H"],
                     loc="center", cellLoc="left", colLoc="left", colWidths=[.19, .2, .18, .25, .18])
    table.auto_set_font_size(False)
    table.set_fontsize(10)
    table.scale(1, 1.45)
    for (r, c), cell in table.get_celld().items():
        cell.set_edgecolor("white")
        cell.set_facecolor("#EEF4F8" if r == 0 else ("#F8FAFC" if r % 2 else "white"))
        cell.get_text().set_color(muted if r == 0 else navy)
        if r == 0:
            cell.get_text().set_fontsize(9)
            cell.get_text().set_weight("bold")
        elif c == 2:
            cell.get_text().set_color(teal if float(liquid[r - 1]["price_change_percent_24h"]) >= 0 else red)
    stamp = summary["captured_at_utc"][:19].replace("T", " ") + " UTC"
    text(.035, .055, f"REAL GA QUERY DATA  /  captured {stamp}  /  source: Binance Spot", 9, muted)
    text(.035, .029, "LAYOUT PREVIEW — rendered separately; not a Power BI Desktop screenshot. Native report also includes a history & coverage page.", 9, muted)
    out = ROOT / "docs/dashboard-preview.png"
    fig.savefig(out, facecolor=fig.get_facecolor(), dpi=120)
    plt.close(fig)
    print(out)


if __name__ == "__main__":
    main()
