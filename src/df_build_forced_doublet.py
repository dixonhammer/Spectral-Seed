#!/usr/bin/env python3
"""
src/df_build_forced_doublet.py  (AUDIT-GRADE, RULE-FIRST, PY3.9 SAFE)

Build the minimal honest finite D_F artifact required for a module-native Δ2 lock.

This builder is intentionally minimal:
- It only builds the forced neutral SU(2) Dirac doublet block (4 states).
- It does NOT claim to be the full SM D_F.
- That is sufficient for the module-native Δ2 chain because σ_H is defined on this forced block.

Priority for σ_H:
  1) artifacts/ult_sigma_integer_rule.json  (preferred: derived discrete rule, contains N)
  2) (fallback only) config/module_spec.json (legacy; declared N or direct sigma)  [optional]

Outputs (canonical):
- artifacts/ult_DF_full.npy
- artifacts/ult_DF_index_map.json

Hard rules:
- NO low-energy target inference
- Record provenance + sha256 hashes
"""

import argparse
import hashlib
import json
import os
import numpy as np
from typing import Any, Dict, Optional, Tuple

CONFIG_DIR = "config"
ART_DIR = "artifacts"

OUT_NPY = os.path.join(ART_DIR, "ult_DF_full.npy")
OUT_MAP = os.path.join(ART_DIR, "ult_DF_index_map.json")

RULE_FILE = os.path.join(ART_DIR, "ult_sigma_integer_rule.json")  # preferred

# Optional legacy fallback. You can omit this file entirely in the new repo.
MODULE_SPEC = os.path.join(CONFIG_DIR, "module_spec.json")  # fallback-only


def _sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _load_json(path: str) -> Dict[str, Any]:
    with open(path, "r") as f:
        return json.load(f)


def _require_exists(path: str, msg: str) -> None:
    if not os.path.exists(path):
        raise SystemExit(msg)


def _try_load_sigma_rule() -> Optional[Dict[str, Any]]:
    if not os.path.exists(RULE_FILE):
        return None
    rule = _load_json(RULE_FILE)
    if not isinstance(rule, dict):
        raise SystemExit(f"[DF BUILD] {RULE_FILE} must be a JSON object/dict.")
    return rule


def _require_module_spec() -> Dict[str, Any]:
    """
    Legacy fallback only. In the new repo, prefer providing RULE_FILE and omit this.
    """
    _require_exists(
        MODULE_SPEC,
        f"[DF BUILD] Missing {MODULE_SPEC}.\n"
        "Preferred path is artifacts/ult_sigma_integer_rule.json (derived rule).\n"
        "If you must use fallback, create config/module_spec.json with e.g.\n"
        '{ "version":1, "doublet_forced":true, "sigma_policy":"from_module_integer", '
        '"sigma_integer_N":32, "sigma_definition":"sigma_H = 2^{-N}" }\n',
    )
    spec = _load_json(MODULE_SPEC)
    if not isinstance(spec, dict) or spec.get("version") is None:
        raise SystemExit("[DF BUILD] config/module_spec.json must be a dict with at least {version:...}.")
    if spec.get("doublet_forced") is not True:
        raise SystemExit("[DF BUILD] module_spec says doublet_forced != true. Then Δ2-from-doublet is not allowed.")
    return spec


def sigma_from_rule_or_module_spec() -> Tuple[float, Dict[str, Any]]:
    """
    Priority:
      1) artifacts/ult_sigma_integer_rule.json (TOE-grade derived rule)
      2) config/module_spec.json fallback (legacy)
    """
    rule = _try_load_sigma_rule()
    if rule is not None:
        pol = rule.get("sigma_policy")
        if pol != "from_trace_discrete_rule":
            raise SystemExit(
                f"[DF BUILD] {RULE_FILE} exists but sigma_policy != 'from_trace_discrete_rule'. Got {pol!r}."
            )
        N = rule.get("N")
        if not isinstance(N, int) or N <= 0:
            raise SystemExit(f"[DF BUILD] {RULE_FILE}: N must be a positive integer. Got {N!r}.")
        sigma = 2.0 ** (-N)
        provenance = {
            "sigma_policy": "from_trace_discrete_rule",
            "N": N,
            "sigma_definition": rule.get("sigma_definition", "sigma_H = 2^{-N}"),
            "source_file": RULE_FILE,
            "source_sha256": _sha256_file(RULE_FILE),
            "meaning": "Preferred path: N derived from trace/module invariants; no MZ targets.",
        }
        return float(sigma), provenance

    # fallback
    spec = _require_module_spec()
    policy = spec.get("sigma_policy")

    if policy == "from_module_integer":
        N = spec.get("sigma_integer_N")
        if not isinstance(N, int) or N <= 0:
            raise SystemExit("[DF BUILD] sigma_integer_N must be a positive integer in module_spec.")
        sigma = 2.0 ** (-N)
        provenance = {
            "sigma_policy": "from_module_integer",
            "N": N,
            "sigma_definition": spec.get("sigma_definition", "sigma_H = 2^{-N}"),
            "source_file": MODULE_SPEC,
            "source_sha256": _sha256_file(MODULE_SPEC),
            "meaning": "Fallback path: sigma_H derived ONLY from config/module_spec.json.",
        }
        return float(sigma), provenance

    if policy == "direct_sigma":
        sigma = spec.get("sigma_direct")
        if not isinstance(sigma, (int, float)):
            raise SystemExit("[DF BUILD] sigma_direct must be numeric if sigma_policy=direct_sigma.")
        sigma = float(sigma)
        provenance = {
            "sigma_policy": "direct_sigma",
            "sigma_definition": spec.get("sigma_definition", "sigma_H = sigma_direct"),
            "source_file": MODULE_SPEC,
            "source_sha256": _sha256_file(MODULE_SPEC),
            "meaning": "Fallback path: module claims it produces sigma directly.",
        }
        return sigma, provenance

    raise SystemExit(
        "[DF BUILD] Unknown sigma_policy.\n"
        "Preferred: artifacts/ult_sigma_integer_rule.json with sigma_policy=from_trace_discrete_rule.\n"
        "Fallback: config/module_spec.json with sigma_policy in {from_module_integer,direct_sigma}.\n"
    )


def build_forced_doublet_block(sigma_H: float):
    """
    4x4 forced neutral SU(2) Dirac doublet sector.

    Basis:
      0: H_L1
      1: H_L2
      2: H_R1
      3: H_R2

    D_F couples L<->R with m = sigma_H (dimensionless), self-adjoint:
      DF[2,0]=m, DF[3,1]=m, DF[0,2]=m, DF[1,3]=m
    """
    m = float(sigma_H)
    DF = np.zeros((4, 4), dtype=float)
    DF[2, 0] = m
    DF[3, 1] = m
    DF[0, 2] = m
    DF[1, 3] = m

    index_map = {
        "basis_order": ["H_L1", "H_L2", "H_R1", "H_R2"],
        "tags": {
            "H_doublet": {
                "L": [0, 1],
                "R": [2, 3],
                "all": [0, 1, 2, 3],
                "Y": 0.0,
                "SU2_rep": "doublet",
                "SU3_rep": "singlet",
                "note": "Forced neutral Dirac SU(2) doublet sector.",
            }
        },
    }
    return DF, index_map


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out_npy", default=OUT_NPY)
    ap.add_argument("--out_map", default=OUT_MAP)
    args = ap.parse_args()

    os.makedirs(ART_DIR, exist_ok=True)

    sigma_H, sigma_prov = sigma_from_rule_or_module_spec()

    if not (0.0 < sigma_H < 1.0):
        raise SystemExit(f"[DF BUILD] sigma_H must be in (0,1). Got {sigma_H}")

    DF, index_map = build_forced_doublet_block(sigma_H)

    np.save(args.out_npy, DF)

    payload: Dict[str, Any] = {
        **index_map,
        "sigma_H": float(sigma_H),
        "sigma_provenance": sigma_prov,
        "provenance": {
            "inputs_present": {
                RULE_FILE: os.path.exists(RULE_FILE),
                MODULE_SPEC: os.path.exists(MODULE_SPEC),
            },
            "meaning": "sigma_H derived from module-native discrete rule file (preferred) or legacy module_spec (fallback).",
        },
    }

    # include module_spec content (fallback only) if it exists
    if os.path.exists(MODULE_SPEC):
        try:
            payload["module_spec"] = _load_json(MODULE_SPEC)
            payload["module_spec_sha256"] = _sha256_file(MODULE_SPEC)
        except Exception:
            pass

    with open(args.out_map, "w") as f:
        json.dump(payload, f, indent=2, sort_keys=True)

    src = sigma_prov.get("source_file", "UNKNOWN")
    pol = sigma_prov.get("sigma_policy", "UNKNOWN")
    print(f"[DF BUILD] wrote {args.out_npy} (shape {DF.shape})")
    print(f"[DF BUILD] wrote {args.out_map}")
    print(f"[DF BUILD] sigma_H = {sigma_H:.12e} (from {src} policy={pol})")


if __name__ == "__main__":
    main()
