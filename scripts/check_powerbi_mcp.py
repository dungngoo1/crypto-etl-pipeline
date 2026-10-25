"""Read-only preflight for the Microsoft local Power BI Authoring MCP server."""
import argparse
import json
from pathlib import Path
import queue
import subprocess
import sys
import threading
import time

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--server", type=Path, required=True)
    parser.add_argument("--accept-eula", action="store_true", help="Confirm you have reviewed and accepted Microsoft's Power BI Authoring MCP EULA")
    parser.add_argument("--desktop", action="store_true", help="Inspect exactly one running Desktop instance instead of the offline BIM")
    parser.add_argument("--output", type=Path, default=ROOT / "docs/evidence/mcp-validation.json")
    args = parser.parse_args()
    if not args.accept_eula:
        parser.error("Review Microsoft's Power BI Authoring MCP EULA and pass --accept-eula only if you agree")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    audit = ROOT / ".local/mcp-audit"
    audit.mkdir(parents=True, exist_ok=True)
    flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    p = subprocess.Popen(
        [str(args.server.resolve()), "--start", "--accepteula", "--readonly", "--audit-log-path=" + str(audit)],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, encoding="utf-8", creationflags=flags,
    )
    replies = queue.Queue()
    errors = []

    def read_stdout():
        for line in p.stdout:
            try:
                replies.put(json.loads(line))
            except json.JSONDecodeError:
                pass

    def read_stderr():
        for line in p.stderr:
            errors.append(line.rstrip())

    threading.Thread(target=read_stdout, daemon=True).start()
    threading.Thread(target=read_stderr, daemon=True).start()
    counter = 0

    def request(method, params):
        nonlocal counter
        counter += 1
        p.stdin.write(json.dumps({"jsonrpc": "2.0", "id": counter, "method": method, "params": params}) + "\n")
        p.stdin.flush()
        deadline = time.monotonic() + 40
        while time.monotonic() < deadline:
            message = replies.get(timeout=max(.1, deadline - time.monotonic()))
            if message.get("id") == counter:
                return message
        raise TimeoutError(method)

    evidence = {}
    try:
        evidence["initialize"] = request("initialize", {
            "protocolVersion": "2024-11-05", "capabilities": {},
            "clientInfo": {"name": "crypto-etl-validation", "version": "1.0"},
        })
        p.stdin.write('{"jsonrpc":"2.0","method":"notifications/initialized"}\n')
        p.stdin.flush()
        tools = request("tools/list", {})
        evidence["tool_names"] = [t["name"] for t in tools.get("result", {}).get("tools", [])]
        evidence["desktop_instances"] = request("tools/call", {"name": "connection_operations",
            "arguments": {"request": {"operation": "ListLocalInstances"}}})
        if args.desktop:
            result = evidence["desktop_instances"].get("result", {})
            payload = json.loads(next(c["text"] for c in result.get("content", []) if c.get("type") == "text"))
            instances = payload.get("data", [])
            if len(instances) != 1:
                raise RuntimeError("Expected exactly one Desktop instance; open only the intended report")
            connect_label = "connect_desktop"
            connect_request = {"operation": "Connect", "connectionString": instances[0]["connectionString"]}
        elif (ROOT / "powerbi/CryptoMarket.SemanticModel/definition").is_dir():
            connect_label = "connect_folder"
            connect_request = {"operation": "ConnectFolder",
                "folderPath": str(ROOT / "powerbi/CryptoMarket.SemanticModel/definition")}
        else:
            connect_label = "connect_bim"
            connect_request = {"operation": "ConnectBimFile",
                "bimFilePath": str(ROOT / "powerbi/CryptoMarket.SemanticModel/model.bim")}
        calls = [
            (connect_label, "connection_operations", connect_request),
            ("model_stats", "model_operations", {"operation": "GetStats"}),
            ("measures", "measure_operations", {"operation": "List"}),
        ]
        for label, name, body in calls:
            evidence[label] = request("tools/call", {"name": name, "arguments": {"request": body}})
            result = evidence[label].get("result", {})
            print(label + ": " + json.dumps(result, ensure_ascii=True)[:2200], flush=True)
            if "error" in evidence[label] or result.get("isError"):
                break
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(evidence, indent=2), encoding="utf-8")
        connected = evidence[connect_label].get("result", {})
        if connected.get("isError") or "error" in evidence[connect_label]:
            raise RuntimeError("MCP could not connect; inspect evidence")
        print("Read-only MCP preflight complete; refresh/render are separate checks.")
    except Exception:
        print("\n".join(errors[-8:]), file=sys.stderr)
        raise
    finally:
        args.output.with_suffix(".stderr.log").write_text("\n".join(errors), encoding="utf-8")
        p.terminate()
        try:
            p.wait(timeout=5)
        except subprocess.TimeoutExpired:
            p.kill()


if __name__ == "__main__":
    main()
