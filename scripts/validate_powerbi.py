"""Validate PBIP/PBIR definitions against Microsoft's published JSON schemas."""
import json
from pathlib import Path
import warnings

import jsonschema
import requests

warnings.filterwarnings("ignore", category=DeprecationWarning)
ROOT = Path(__file__).resolve().parents[1] / "powerbi"
CACHE = {}


def fetch(uri):
    if uri not in CACHE:
        response = requests.get(uri, timeout=30)
        # Some Microsoft embedded schemas publish a dotted $id but a hyphenated filename.
        if response.status_code == 404 and "schema.embedded.json" in uri:
            response = requests.get(uri.replace("schema.embedded.json", "schema-embedded.json"), timeout=30)
        response.raise_for_status()
        CACHE[uri] = response.json()
    return CACHE[uri]


def main():
    count = 0
    for path in ROOT.rglob("*"):
        if path.suffix not in (".json", ".pbip", ".pbir", ".pbism"):
            continue
        document = json.loads(path.read_text(encoding="utf-8"))
        if "$schema" not in document:
            continue
        uri = document["$schema"]
        schema = fetch(uri)
        resolver = jsonschema.RefResolver(base_uri=uri, referrer=schema, handlers={"https": fetch})
        jsonschema.Draft7Validator(schema, resolver=resolver).validate(document)
        count += 1
    print(f"PASS: {count} Power BI project/report definitions validated")
    print("JSON schema validation does not verify native rendering, DAX or Power Query execution.")


if __name__ == "__main__":
    main()
