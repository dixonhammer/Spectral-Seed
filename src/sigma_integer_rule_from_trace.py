#!/usr/bin/env python3
"""
src/sigma_integer_rule_from_trace.py  (AUDIT-GRADE, RULE-FIRST)

Purpose
-------
Derive the discrete integer N used for the forced-doublet onset scale via:

  N = round(K_common + 2*SU2_base_sum_Tfund)

Inputs (canonical):
- artifacts/ult_trace_table.json

Output (canonical):
- artifacts/ult_sigma_integer_rule.json

Hard rules:
- NO low-energy target inference
- NO kYstar_muon references
- Record provenance + sha256 hashes
"""

import json
import os
import hashlib
from typing import Any, Dict

CONFIG_DIR = "config"  # kept for convention symmetry (not used here)
ART_DIR = "artifacts"

TRACE = os.path.join(ART_DIR, "ult_trace_table.json")
OUT = os.path.join(ART_DIR, "ult_sigma_integer_rule.json")


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
        raise SystemExit(f"[SIGMA N] Missing required file: {path} (run src/trace_emit.py first).")


def main() -> None:
    _require_exists(TRACE)
    os.makedirs(ART_DIR, exist_ok=True)

    T = _load_json(TRACE)

    # Pull invariants from the canonical trace artifact schema you have
    try:
        K_common = float(T["K_totals"]["K_common"])
    except Exception:
        raise SystemExit("[SIGMA N] Trace artifact missing K_totals.K_common")

    try:
        SU2sum = float(T["base_sums_over_3gens"]["SU2_base_sum_Tfund"])
    except Exception:
        raise SystemExit("[SIGMA N] Trace artifact missing base_sums_over_3gens.SU2_base_sum_Tfund")

    # TOE-grade discrete rule (candidate until proven):
    # N = round(K_common + 2*SU2_base_sum_Tfund)
    N = int(round(K_common + 2.0 * SU2sum))
    if N <= 0:
        raise SystemExit(f"[SIGMA N] Invalid N={N}. Must be positive.")

    rule = {
        "sigma_policy": "from_trace_discrete_rule",
        "inputs": {
            "K_common": K_common,
            "SU2_base_sum_Tfund": SU2sum,
        },
        "rule": "N = round(K_common + 2*SU2_base_sum_Tfund)",
        "N": N,
        "sigma_definition": "sigma_H = 2^{-N}",
        "provenance": {
            "source": TRACE,
            "source_sha256": _sha256_file(TRACE),
            "meaning": (
                "Rule-first artifact: N is computed from trace/module invariants only. "
                "No low-energy targets are used."
            ),
        },
        "note": (
            "This file defines the discrete mapping used by the module-native Δ2 chain. "
            "A paper may later justify why this mapping is forced by the underlying module."
        ),
    }

    with open(OUT, "w") as f:
        json.dump(rule, f, indent=2, sort_keys=True)

    print(f"[SIGMA N] K_common={K_common}  SU2sum={SU2sum}  => N={N}")
    print(f"[SIGMA N] wrote {OUT}")


if __name__ == "__main__":
    main()
