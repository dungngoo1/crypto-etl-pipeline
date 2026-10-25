"""Rebuild the portable Power BI project using documented PBIP/PBIR JSON."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "powerbi"
BASE = "https://developer.microsoft.com/json-schemas/fabric/item/"
REPORT = ROOT / "CryptoMarket.Report"
MODEL = ROOT / "CryptoMarket.SemanticModel"


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def literal(value):
    if isinstance(value, bool):
        text = "true" if value else "false"
    elif isinstance(value, (int, float)):
        text = str(value)
    else:
        text = "'" + value.replace("'", "''") + "'"
    return {"expr": {"Literal": {"Value": text}}}


def field(table, column, measure=False):
    return {("Measure" if measure else "Column"): {
        "Expression": {"SourceRef": {"Entity": table}}, "Property": column}}


def projection(table, column, measure=False):
    return {"field": field(table, column, measure), "queryRef": f"{table}.{column}"}


def categorical(table, column, values, name):
    column_expr = {"Column": {"Expression": {"SourceRef": {"Source": "s"}}, "Property": column}}
    return {
        "name": name, "field": field(table, column), "type": "Categorical",
        "filter": {"Version": 2, "From": [{"Name": "s", "Entity": table, "Type": 0}],
                   "Where": [{"Condition": {"In": {
                       "Expressions": [column_expr],
                       "Values": [[{"Literal": {"Value": ("'" + v + "'") if isinstance(v, str) else str(v) + "L"}}] for v in values]
                   }}}]},
    }


def visual(page, name, kind, x, y, w, h, title, roles=None, filters=None, objects=None, sort=None):
    chart = {
        "visualType": kind,
        "visualContainerObjects": {
            "title": [{"properties": {"show": literal(bool(title)), "text": literal(title),
                       "fontSize": literal(12), "fontColor": literal("#102A43")}}],
            "background": [{"properties": {"show": literal(True), "color": {"solid": {"color": literal("#FFFFFF")}},
                                           "transparency": literal(0)}}],
            "border": [{"properties": {"show": literal(False)}}],
        },
    }
    if roles:
        chart["query"] = {"queryState": {role: {"projections": ps} for role, ps in roles.items()}}
        if sort:
            chart["query"]["sortDefinition"] = {"sort": [{"field": sort[0], "direction": sort[1]}]}
    if objects:
        chart["objects"] = objects
    if kind == "slicer" and filters:
        # A visual filter limits available choices; general.filter stores the selection.
        chart.setdefault("objects", {})["general"] = [{"properties": {
            "filter": {"filter": filters[0]["filter"]}
        }}]
    result = {"$schema": BASE + "report/definition/visualContainer/2.3.0/schema.json",
              "name": name, "position": {"x": x, "y": y, "z": y + x, "height": h, "width": w, "tabOrder": y + x},
              "visual": chart}
    if filters and kind != "slicer":
        result["filterConfig"] = {"filters": filters}
    save(REPORT / "definition/pages" / page / "visuals" / name / "visual.json", result)


def textbox(page, name, text, x, y, w, h, size=14, color="#102A43"):
    visual(page, name, "textbox", x, y, w, h, "",
           objects={"general": [{"properties": {"paragraphs": [{"textRuns": [{
               "value": text, "textStyle": {"fontSize": f"{size}pt", "fontFamily": "Segoe UI", "color": color}
           }]}]}}]})


def make_table(name, source, columns, measures=None):
    time_transforms = ", ".join(
        '{"' + col + '", each if _ = null then null else '
        'DateTimeZone.RemoveZone(DateTimeZone.ToUtc(DateTimeZone.From(_))), type nullable datetime}'
        for col, dtype in columns.items() if dtype == "dateTime"
    )
    result = {"name": name, "columns": [], "partitions": [{
        "name": name, "mode": "import", "source": {"type": "m", "expression": [
            "let",
            "    Source = PostgreSQL.Database(Server, Database, [CreateNavigationProperties=false]),",
            f'    Data = Source{{[Schema="ga", Item="{source}"]}}[Data],',
            "    UTC = Table.TransformColumns(Data, {" + time_transforms + "})",
            "in UTC",
        ]}},
    ]}
    for col, dtype in columns.items():
        c = {"name": col, "dataType": dtype, "sourceColumn": col, "summarizeBy": "none"}
        if dtype == "dateTime":
            c["formatString"] = "yyyy-MM-dd HH:mm"
        result["columns"].append(c)
    if measures:
        result["measures"] = [{"name": n, "expression": expr, "formatString": fmt} for n, expr, fmt in measures]
    return result


def sync_native_partitions(tables):
    """Preserve Desktop's TMDL objects while updating the four generated M sources."""
    for table in tables:
        path = MODEL / "definition/tables" / (table["name"] + ".tmdl")
        lines = path.read_text(encoding="utf-8").splitlines()
        partition = next(i for i, line in enumerate(lines)
                         if line.strip() == "partition " + table["name"] + " = m")
        start = next(i for i in range(partition + 1, len(lines)) if lines[i].strip() == "source =")
        end = start + 1
        while end < len(lines) and (not lines[end].strip() or lines[end].startswith("\t\t\t")):
            end += 1
        expression = table["partitions"][0]["source"]["expression"]
        lines[start + 1:end] = ["\t\t\t\t" + line for line in expression] + [""]
        path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def main():
    native_tmdl = (MODEL / "definition").is_dir()
    save(ROOT / "CryptoMarket.pbip", {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/pbip/pbipProperties/1.0.0/schema.json",
        "version": "1.0", "artifacts": [{"report": {"path": "CryptoMarket.Report"}}],
        "settings": {"enableAutoRecovery": True},
    })
    if not native_tmdl:
        save(MODEL / "definition.pbism", {
            "$schema": BASE + "semanticModel/definitionProperties/1.0.0/schema.json",
            "version": "1.0", "settings": {"qnaEnabled": False},
        })
    latest_columns = {
        "metric_key": "string", "batch_id": "string", "batch_timestamp": "dateTime", "ingested_at": "dateTime",
        "symbol": "string", "base_asset": "string", "quote_asset": "string", "trading_status": "string",
        "current_price": "double", "price_change_percent_24h": "double", "high_price_24h": "double",
        "low_price_24h": "double", "volume_quote_24h": "double", "trade_count_24h": "int64",
        "snapshot_timestamp": "dateTime", "gain_rank": "int64", "loss_rank": "int64", "volume_rank": "int64",
    }
    history_columns = {k: latest_columns[k] for k in [
        "metric_key", "batch_id", "batch_timestamp", "ingested_at", "symbol", "base_asset", "quote_asset",
        "current_price", "price_change_percent_24h", "volume_quote_24h", "snapshot_timestamp",
    ]}
    overview_columns = {
        "batch_id": "string", "batch_timestamp": "dateTime", "captured_at": "dateTime",
        "quote_asset": "string", "returned_pairs": "int64", "active_pairs": "int64", "excluded_pairs": "int64",
        "advancing_pairs": "int64", "declining_pairs": "int64", "avg_change_percent_24h": "double",
        "volume_quote_24h": "double", "trade_count_24h": "int64",
    }
    tables = [
        make_table("Latest", "latest_tickers", latest_columns, [
            ("Active pairs", "COUNTROWS(Latest)", "#,0"),
            ("Volume 24h", "IF(HASONEVALUE(Latest[quote_asset]), SUM(Latest[volume_quote_24h]))", "#,0.00"),
            ("Average change 24h", "IF(HASONEVALUE(Latest[quote_asset]), AVERAGE(Latest[price_change_percent_24h]) / 100)", "0.00%"),
            ("Change 24h", "AVERAGE(Latest[price_change_percent_24h]) / 100", "0.00%"),
            ("Last snapshot UTC", 'FORMAT(MAX(Latest[ingested_at]), "yyyy-MM-dd HH:mm")', ""),
        ]),
        make_table("History", "symbol_history", history_columns, [
            ("Pair price", "IF(HASONEVALUE(History[symbol]), MAX(History[current_price]))", "#,0.########"),
        ]),
        make_table("Overview", "market_overview", overview_columns, [
            ("Rolling quote volume", "IF(HASONEVALUE(Overview[quote_asset]) && HASONEVALUE(Overview[batch_id]), MAX(Overview[volume_quote_24h]))", "#,0"),
            ("Pair breadth", "IF(HASONEVALUE(Overview[quote_asset]) && HASONEVALUE(Overview[batch_id]), MAX(Overview[active_pairs]))", "#,0"),
        ]),
        make_table("Publication", "publication_status", {
            "singleton": "boolean", "batch_id": "string", "captured_at": "dateTime", "published_at": "dateTime",
        }, [("Age minutes", "DATEDIFF(MAX(Publication[captured_at]), UTCNOW(), MINUTE)", "#,0")]),
    ]
    if native_tmdl:
        sync_native_partitions(tables)
    else:
        save(MODEL / "model.bim", {"name": "CryptoMarket", "compatibilityLevel": 1567,
            "model": {"culture": "en-US", "defaultPowerBIDataSourceVersion": "powerBI_V3",
                      "sourceQueryCulture": "en-US",
                      "annotations": [{"name": "PBI_QueryOrder", "value": '["Server","Database","Latest","History","Overview","Publication"]'}],
                      "expressions": [
                          {"name": "Server", "kind": "m", "expression": '"localhost:5433" meta [IsParameterQuery=true, Type="Text", IsParameterQueryRequired=true]'},
                          {"name": "Database", "kind": "m", "expression": '"crypto_dw" meta [IsParameterQuery=true, Type="Text", IsParameterQueryRequired=true]'},
                      ], "tables": tables}})
    save(REPORT / "definition.pbir", {
        "$schema": BASE + "report/definitionProperties/2.0.0/schema.json", "version": "4.0",
        "datasetReference": {"byPath": {"path": "../CryptoMarket.SemanticModel"}},
    })
    save(REPORT / "definition/version.json", {
        "$schema": BASE + "report/definition/versionMetadata/1.0.0/schema.json", "version": "2.0.0"})
    save(REPORT / "definition/report.json", {
        "$schema": BASE + "report/definition/report/2.0.0/schema.json", "themeCollection": {},
        "settings": {"useStylableVisualContainerHeader": True, "exportDataMode": "AllowSummarized"},
    })
    pages = [("market", "01 | Market snapshot"), ("history", "02 | History & coverage")]
    save(REPORT / "definition/pages/pages.json", {
        "$schema": BASE + "report/definition/pagesMetadata/1.0.0/schema.json",
        "pageOrder": [p[0] for p in pages], "activePageName": "market"})
    for name, title in pages:
        save(REPORT / "definition/pages" / name / "page.json", {
            "$schema": BASE + "report/definition/page/2.0.0/schema.json", "name": name,
            "displayName": title, "displayOption": "FitToPage", "width": 1440, "height": 900,
            "objects": {"background": [{"properties": {"color": {"solid": {"color": literal("#F3F6FA")}}, "transparency": literal(0)}}]},
        })
    textbox("market", "heading", "CRYPTO / MARKET SNAPSHOT", 24, 16, 980, 50, 25)
    textbox("market", "subtitle", "All returned tickers captured · analysis: active spot pairs · choose ONE quote asset", 24, 65, 1030, 34, 11, "#52667A")
    slicer_settings = {
        "selection": [{"properties": {"singleSelect": literal(True), "selectAllCheckboxEnabled": literal(False)}}],
        "data": [{"properties": {"mode": literal("Dropdown")}}],
    }
    visual("market", "quote", "slicer", 1080, 16, 336, 90, "Quote asset",
           {"Values": [projection("Latest", "quote_asset")]},
           [categorical("Latest", "quote_asset", ["USDT"], "selected_quote")], slicer_settings)
    for i, (table, measure, title) in enumerate([
        ("Latest", "Active pairs", "Active trading pairs"),
        ("Latest", "Volume 24h", "Rolling volume 24h · selected quote"),
        ("Latest", "Average change 24h", "Average pair change · 24h"),
        ("Publication", "Age minutes", "Snapshot age · minutes"),
    ]):
        visual("market", f"kpi{i}", "card", 24 + i * 352, 120, 336, 125, title,
               {"Values": [projection(table, measure, True)]})
    for name, rank, title, x, direction in [
        ("gainers", "gain_rank", "Top gainers · 24h change", 24, "Descending"),
        ("losers", "loss_rank", "Top losers · 24h change", 732, "Ascending"),
    ]:
        visual("market", name, "clusteredBarChart", x, 269, 684, 330, title,
               {"Category": [projection("Latest", "symbol")], "Y": [projection("Latest", "Change 24h", True)]},
               [categorical("Latest", rank, list(range(1, 11)), name + "_top10")],
               objects={"dataPoint": [{"properties": {"defaultColor": {"solid": {
                   "color": literal("#0D9488" if name == "gainers" else "#EF4444")}}}}],
                        "labels": [{"properties": {"show": literal(True)}}]},
               sort=(field("Latest", "Change 24h", True), direction))
    visual("market", "liquidity", "tableEx", 24, 623, 1392, 210, "Most liquid pairs · selected quote",
           {"Values": [projection("Latest", n, n == "Change 24h") for n in [
               "symbol", "quote_asset", "current_price", "Change 24h", "volume_quote_24h", "trade_count_24h", "snapshot_timestamp"]]},
           [categorical("Latest", "volume_rank", list(range(1, 11)), "liquidity_top10")],
           sort=(field("Latest", "volume_quote_24h"), "Descending"))
    textbox("market", "footnote", "24h = rolling window, not calendar day. Prices/volume use the selected quote. Refresh imports the last tested GA release.", 24, 850, 1392, 30, 10, "#52667A")
    textbox("history", "heading_history", "CRYPTO / HISTORY & COVERAGE", 24, 16, 1000, 50, 25)
    textbox("history", "history_note", "Hourly observations begin when ingestion starts. No fabricated backfill; rolling 24h volumes must not be added across time.", 24, 70, 1392, 40, 11, "#52667A")
    visual("history", "pair", "slicer", 24, 130, 400, 100, "Trading pair · price chart",
           {"Values": [projection("History", "symbol")]},
           [categorical("History", "symbol", ["BTCUSDT"], "selected_pair")], slicer_settings)
    visual("history", "history_quote", "slicer", 448, 130, 400, 100, "Quote asset · volume chart",
           {"Values": [projection("Overview", "quote_asset")]},
           [categorical("Overview", "quote_asset", ["USDT"], "selected_history_quote")], slicer_settings)
    visual("history", "price", "lineChart", 24, 254, 684, 340, "Observed pair price · hourly",
           {"Category": [projection("History", "ingested_at")], "Y": [projection("History", "Pair price", True)]},
           sort=(field("History", "ingested_at"), "Ascending"))
    visual("history", "volume_trend", "lineChart", 732, 254, 684, 340, "Rolling 24h quote volume · each snapshot",
           {"Category": [projection("Overview", "captured_at")], "Y": [projection("Overview", "Rolling quote volume", True)]},
           sort=(field("Overview", "captured_at"), "Ascending"))
    visual("history", "coverage", "tableEx", 24, 618, 1392, 215, "Coverage by batch and quote · includes excluded pairs",
           {"Values": [projection("Overview", n) for n in [
               "captured_at", "quote_asset", "returned_pairs", "active_pairs", "excluded_pairs", "advancing_pairs", "declining_pairs"]]},
           sort=(field("Overview", "captured_at"), "Descending"))
    save(ROOT / "theme.json", {
        "name": "Crypto Clear", "dataColors": ["#0D9488", "#EF4444", "#2563EB", "#F59E0B"],
        "background": "#F3F6FA", "foreground": "#102A43", "tableAccent": "#0D9488",
    })
    print("Built Power BI project:", ROOT / "CryptoMarket.pbip")


if __name__ == "__main__":
    main()
