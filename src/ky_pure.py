#!/usr/bin/env python3
"""
src/ky_pure.py  (AUDIT-GRADE)

Purpose
-------
Emit a target-free hypercharge normalization artifact:

- Reads kY ONLY from the trace artifact (module/trace invariant),
  NOT from any MZ/targets-derived solver outputs.

Inputs (canonical):
- artifacts/ult_trace_table.json   (expects K_totals.kY or K_totals.K1/K2)

Output (canonical):
- artifacts/ult_kY_pure.json

Hard rules:
- NO references to kYstar_muon_solver.py or ult_kYstar_muon.json
- Record provenance + sha256 hashes
"""

import json
import os
import hashlib
from typing import Any, Dict

CONFIG_DIR = "config"   # kept for convention symmetry (not used here)
ART_DIR = "artifacts"

TRACE = os.path.join(ART_DIR, "ult_trace_table.json")
OUT = os.path.join(ART_DIR, "ult_kY_pure.json")


def _sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _load_json(path: str) -> Dict[str, Any]:
    with open(path, "r") as f:
        return json.load(f)


def _require_exists(path: str) -> None:
    if not os.path.exists(path):
        raise SystemExit(f"[kY PURE] Missing required file: {path} (run src/trace_emit.py first).")


def _extract_kY(T: Dict[str, Any]) -> float:
    # Preferred: direct kY in trace artifact
    Ktot = T.get("K_totals", {})
    if "kY" in Ktot:
        return float(Ktot["kY"])

    # Fallback: compute from K1/K2 if present
    if "K1" in Ktot and "K2" in Ktot:
        K1 = float(Ktot["K1"])
        K2 = float(Ktot["K2"])
        if K2 == 0.0:
            raise SystemExit("[kY PURE] Trace artifact has K2=0; cannot compute kY=K1/K2.")
        return K1 / K2

    raise SystemExit("[kY PURE] Trace artifact missing K_totals.kY (and missing K1/K2).")


def main() -> None:
    _require_exists(TRACE)
    os.makedirs(ART_DIR, exist_ok=True)

    T = _load_json(TRACE)
    kY = _extract_kY(T)

    out = {
        "kY_star": float(kY),
        "provenance": {
            "source": TRACE,
            "source_sha256": _sha256_file(TRACE),
            "meaning": (
                "kY_star is sourced ONLY from the trace artifact (module/trace invariant), "
                "with no MZ/targets language and no solver dependence."
            ),
        },
    }

    with open(OUT, "w") as f:
        json.dump(out, f, indent=2, sort_keys=True)

    print(f"[kY PURE] kY_star={kY:.15f}")
    print(f"[kY PURE] wrote {OUT}")


if __name__ == "__main__":
    main()
