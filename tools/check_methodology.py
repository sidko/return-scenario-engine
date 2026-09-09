#!/usr/bin/env python3
"""Check the public calculation methodology copies and their declared hash."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parents[1]
TS_JSON = ROOT / "methodology" / "return-scenario-v1.json"
PY_JSON = ROOT / "python" / "return_scenario_engine" / "methodology" / "return-scenario-v1.json"
FIXTURE = ROOT / "fixtures" / "golden-v1.json"
PY_SOURCE = ROOT / "python" / "return_scenario_engine" / "__init__.py"


def main() -> int:
    canonical = TS_JSON.read_bytes()
    if PY_JSON.read_bytes() != canonical:
        print("Python methodology JSON differs from canonical TypeScript copy", file=sys.stderr)
        return 1
    payload = json.loads(canonical)
    required = {"schemaVersion", "methodologyVersion", "constants", "dateAlignment", "formulas", "minimumEvidence", "rounding"}
    if set(payload) != required or payload["schemaVersion"] != 1:
        print("invalid public calculation methodology shape", file=sys.stderr)
        return 1
    digest = hashlib.sha256(canonical).hexdigest()
    fixture = json.loads(FIXTURE.read_text())
    if fixture.get("methodologyContractHash") != digest:
        print("golden fixture methodology hash mismatch", file=sys.stderr)
        return 1
    if not re.search(rf'METHODOLOGY_HASH = "{digest}"', PY_SOURCE.read_text()):
        print("Python methodology hash constant mismatch", file=sys.stderr)
        return 1
    print(json.dumps({"methodologyVersion": payload["methodologyVersion"], "sha256": digest}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
