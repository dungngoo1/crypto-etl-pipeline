"""Draw project architecture and technology logos as self-contained SVG assets."""
from pathlib import Path
from html import escape
import re
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "docs/assets"
ICONS = ASSETS / "icons"
NS = "{http://www.w3.org/2000/svg}"


def logo(name, x, y, size=58, suffix=""):
    root = ET.fromstring((ICONS / (name + ".svg")).read_text(encoding="utf-8"))
    vb = [float(v) for v in root.attrib.get("viewBox", "0 0 128 128").split()]
    scale = size / max(vb[2], vb[3])
    prefix = name + suffix + "_"
    for element in root.iter():
        if "id" in element.attrib:
            element.attrib["id"] = prefix + element.attrib["id"]
        for key, value in list(element.attrib.items()):
            value = re.sub(r"url\(#([^)]*)\)", lambda m: "url(#" + prefix + m.group(1) + ")", value)
            if key.endswith("href") and value.startswith("#"):
                value = "#" + prefix + value[1:]
            element.attrib[key] = value
    children = "".join(ET.tostring(e, encoding="unicode") for e in root if e.tag not in (NS + "metadata", NS + "title"))
    color = {"dbt": "#FF694B", "binance": "#E4AE00"}.get(name, "none")
    dx = x + (size - vb[2] * scale) / 2
    dy = y + (size - vb[3] * scale) / 2
    return f'<g fill="{color}" transform="translate({dx:.3f} {dy:.3f}) scale({scale:.5f}) translate({-vb[0]} {-vb[1]})">{children}</g>'


def text(x, y, value, size=20, color="#15324D", weight=400, anchor="start"):
    return f'<text x="{x}" y="{y}" fill="{color}" font-family="Segoe UI,Arial,sans-serif" font-size="{size}" font-weight="{weight}" text-anchor="{anchor}">{escape(value)}</text>'


def rect(x, y, w, h, color="white", stroke="#DCE5EE", radius=18):
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{radius}" fill="{color}" stroke="{stroke}" stroke-width="1.5"/>'


def arrow(x1, y1, x2, y2, dashed=False, color="#71869B"):
    dash = 'stroke-dasharray="7 7"' if dashed else ""
    return f'<path d="M{x1},{y1} L{x2},{y2}" fill="none" stroke="{color}" stroke-width="2.5" {dash} marker-end="url(#arrow)"/>'


def header(width, height, title, description):
    return [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img">',
            f'<title>{escape(title)}</title><desc>{escape(description)}</desc>',
            '<defs><marker id="arrow" markerWidth="9" markerHeight="9" refX="8" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8" fill="none" stroke="#71869B" stroke-width="1.4"/></marker></defs>',
            f'<rect width="{width}" height="{height}" fill="#F4F7FB"/>']


def main():
    ASSETS.mkdir(parents=True, exist_ok=True)
    s = header(1920, 1020, "Crypto Market ELT architecture", "All Binance Spot tickers to immutable Bronze, typed Silver, Gold star schema, tested GA and Power BI.")
    s += [text(60, 82, "CRYPTO MARKET / DATA PLATFORM", 38, weight=700),
          text(60, 125, "All Binance Spot tickers · Immutable batches · Tested analytics · Power BI", 22, "#60778D")]
    s += [rect(310, 170, 1240, 108, "#FFFFFF"),
          logo("airflow", 334, 191, 60),
          text(414, 215, "Apache Airflow", 25, weight=700),
          text(414, 249, "Hourly schedule · retries · one active run", 19, "#60778D"),
          logo("dbt", 1117, 195, 50),
          text(1185, 215, "dbt", 25, weight=700),
          text(1185, 249, "Build + quality checks", 19, "#60778D"),
          arrow(415, 278, 415, 386, True),
          arrow(1170, 278, 1170, 345, True)]
    s += [rect(565, 317, 985, 397, "#EAF0F7", "#D4DFEA"),
          logo("postgresql", 589, 335, 38),
          text(640, 364, "POSTGRESQL WAREHOUSE", 20, weight=700),
          text(1523, 364, "Medallion + GA", 18, "#60778D", anchor="end")]
    s += [rect(60, 386, 210, 268), logo("binance", 133, 411, 62),
          text(165, 512, "BINANCE SPOT", 22, weight=700, anchor="middle"),
          text(165, 550, "24h ticker / all", 18, "#60778D", anchor="middle"),
          text(165, 582, "exchangeInfo", 18, "#60778D", anchor="middle"),
          text(165, 619, "Public REST API", 16, "#60778D", anchor="middle"),
          rect(310, 386, 210, 268), logo("python", 383, 411, 62),
          text(415, 512, "INGESTION", 22, weight=700, anchor="middle"),
          text(415, 550, "Capture all rows", 18, "#60778D", anchor="middle"),
          text(415, 582, "Batch transaction", 18, "#60778D", anchor="middle"),
          text(415, 619, "requests + psycopg2", 16, "#60778D", anchor="middle"),
          arrow(270, 520, 305, 520), arrow(520, 520, 590, 520)]
    stages = [
        (590, 190, "01", "BRONZE", "#B67437", "#FFF8EF", ["Raw ticker JSON", "Exchange metadata", "Batch manifest"]),
        (820, 190, "02", "SILVER", "#76899B", "#F8FAFC", ["Typed all-ticker rows", "Eligibility + reasons", "Millisecond time"]),
        (1050, 190, "03", "GOLD", "#B88C13", "#FFFBEB", ["Pair dimension", "Snapshot fact", "Stable batch keys"]),
        (1280, 245, "04", "GA / ANALYTICS", "#0D9488", "#EDFCF8", ["Market overview", "Latest tickers", "Symbol history"]),
    ]
    for x, w, number, title, color, bg, lines in stages:
        s += [rect(x, 386, w, 268, bg, "#D6E1EA"),
              text(x + 20, 426, number, 19, color, 700),
              text(x + 20, 468, title, 20 if w == 190 else 22, color, 700)]
        for i, line in enumerate(lines):
            s.append(text(x + 20, 515 + i * 34, line, 16, "#526B80"))
    for start, end in [(780, 815), (1010, 1045), (1240, 1275)]:
        s.append(arrow(start, 520, end, 520))
    s += [text(604, 689, "GA candidate → tests pass → atomic publish; failed runs preserve the last successful GA release.", 17, "#526B80")]
    s += [rect(1600, 386, 260, 268), logo("powerbi", 1697, 409, 68),
          text(1730, 512, "POWER BI", 25, weight=700, anchor="middle"),
          text(1730, 550, "Market snapshot", 19, "#60778D", anchor="middle"),
          text(1730, 582, "History + coverage", 19, "#60778D", anchor="middle"),
          text(1730, 619, "One quote per volume KPI", 16, "#60778D", anchor="middle"),
          arrow(1550, 520, 1595, 520)]
    s += [rect(60, 768, 1800, 160),
          logo("docker", 87, 802, 69), text(178, 818, "Docker Compose", 23, weight=700),
          text(178, 857, "Airflow services + PostgreSQL", 19, "#60778D"),
          logo("githubactions", 690, 808, 58),
          text(770, 818, "GitHub Actions", 23, weight=700),
          text(770, 857, "Lint + unit tests + PostgreSQL integration", 19, "#60778D"),
          rect(1325, 798, 505, 100, "#F0FAF7", "#CFEDE2"),
          text(1350, 830, "QUALITY CONTRACT", 17, "#0D9488", 700),
          text(1350, 864, "Coverage · grain · ranges · freshness", 18, "#526B80"),
          text(60, 977, "24h metrics are rolling windows. Do not sum them across time or mix quote currencies.", 19, "#60778D"),
          "</svg>"]
    (ASSETS / "architecture.svg").write_text("\n".join(s), encoding="utf-8")

    s = header(1920, 560, "Crypto ELT technology stack", "Logos and roles of Binance, Python, Airflow, PostgreSQL, dbt, Docker, GitHub Actions and Power BI.")
    s += [text(60, 72, "TECHNOLOGY STACK", 32, weight=700),
          text(60, 110, "One clear responsibility for each component", 20, "#60778D")]
    cards = [("binance", "Binance Spot", "Market data source"), ("python", "Python", "Capture + publish"),
             ("airflow", "Apache Airflow", "Orchestration"), ("postgresql", "PostgreSQL", "Medallion warehouse"),
             ("dbt", "dbt", "Transform + test"), ("docker", "Docker Compose", "Local infrastructure"),
             ("githubactions", "GitHub Actions", "Continuous integration"), ("powerbi", "Power BI", "Analytics + reporting")]
    for i, (name, title, desc) in enumerate(cards):
        x = 60 + (i % 4) * 455
        y = 156 + (i // 4) * 180
        s += [rect(x, y, 430, 152), logo(name, x + 24, y + 40, 65, str(i)),
              text(x + 112, y + 66, title, 24, weight=700),
              text(x + 112, y + 102, desc, 18, "#60778D")]
    s.append("</svg>")
    (ASSETS / "tech-stack.svg").write_text("\n".join(s), encoding="utf-8")
    print("Wrote architecture.svg and tech-stack.svg")


if __name__ == "__main__":
    main()
