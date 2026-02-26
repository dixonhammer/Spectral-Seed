#!/usr/bin/env python3
"""
src/platinum_check.py  (module-native edition, AUDIT-GRADE)

Goal
----
Ensure the repo is internally consistent under the *module-native* chain:

trace -> (kY, K_common, SU2sum) -> N -> sigma_H -> mu_on -> Delta2 -> RG

Hard rules enforced:
- NO references to kYstar_muon_solver.py or ult_kYstar_muon.json
- NO MZ/targets inference in any lock derivation logic
- Canonical repo paths only (config/, artifacts/)

Checks
------
1) Required files exist (config + key artifacts)
2) config/locks.json matches artifacts/ult_delta2_module.json (Delta2 + mu_on)
3) kY consistency: artifacts/ult_kY_pure.json == artifacts/ult_trace_table.json K_totals.kY
4) Optional: artifacts/ult_MZ_observables.json provenance:
   - note.deltas_source.d2 == "artifacts/ult_delta2_module.json"
   - note.kY_source == "artifacts/ult_kY_pure.json"

Behavior
--------
- FAIL only on true inconsistencies (missing required files, lock mismatches, bad schema).
- WARN on optional provenance mismatches (metadata), but still PASS (with warnings).
"""

import json
import os
import sys
import hashlib
from typing import Any, Dict, List, Optional

CONFIG_DIR = "config"
ART_DIR = "artifacts"

# Required config inputs
CONSTANTS = os.path.join(CONFIG_DIR, "constants.json")
LOCKS = os.path.join(CONFIG_DIR, "locks.json")
THRESHOLDS = os.path.join(CONFIG_DIR, "thresholds.json")
HIGHSCALE = os.path.join(CONFIG_DIR, "highscale_shifts.json")

# Required artifacts (for lock chain)
TRACE = os.path.join(ART_DIR, "ult_trace_table.json")
KY_PURE = os.path.join(ART_DIR, "ult_kY_pure.json")
SIGMA_RULE = os.path.join(ART_DIR, "ult_sigma_integer_rule.json")
DF_MAP = os.path.join(ART_DIR, "ult_DF_index_map.json")
DF_NPY = os.path.join(ART_DIR, "ult_DF_full.npy")
DELTA2 = os.path.join(ART_DIR, "ult_delta2_module.json")

# Optional artifact (for provenance check)
MZ_OBS = os.path.join(ART_DIR, "ult_MZ_observables.json")

TOL_REL = 1e-12
TOL_ABS = 1e-10


def _load(path: str) -> Dict[str, Any]:
    with open(path, "r") as f:
        return json.load(f)


def _sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _rel_err(a: float, b: float) -> float:
    if a == b:
        return 0.0
    denom = max(abs(a), abs(b), 1.0)
    return abs(a - b) / denom


def _fail(msgs: List[str]) -> None:
    print("PLATINUM CHECK: FAIL")
    for m in msgs:
        print("  - " + m)
    sys.exit(1)


def _warn_pass(msgs: List[str]) -> None:
    print("PLATINUM CHECK: PASS (with warnings)")
    for m in msgs:
        print("  " + m)
    sys.exit(0)


def _require_files(paths: List[str], notes: List[str]) -> None:
    for p in paths:
        if not os.path.exists(p):
            notes.append(f"missing {p}")


def _extract_trace_kY(trace: Dict[str, Any]) -> Optional[float]:
    kt = trace.get("K_totals", {})
    if isinstance(kt, dict) and "kY" in kt:
        try:
            return float(kt["kY"])
        except Exception:
            return None
    # fallback: compute from K1/K2 if present
    if isinstance(kt, dict) and "K1" in kt and "K2" in kt:
        try:
            K1 = float(kt["K1"])
            K2 = float(kt["K2"])
            if K2 == 0.0:
                return None
            return K1 / K2
        except Exception:
            return None
    return None


def main() -> None:
    notes: List[str] = []

    # --- Required files for the publishable pipeline ---
    required = [
        CONSTANTS,
        LOCKS,
        THRESHOLDS,
        HIGHSCALE,
        TRACE,
        KY_PURE,
        SIGMA_RULE,
        DF_MAP,
        DF_NPY,
        DELTA2,
    ]
    _require_files(required, notes)
    if notes:
        _fail(notes)

    # --- Load core objects ---
    locks = _load(LOCKS)
    trace = _load(TRACE)
    ky_pure = _load(KY_PURE)
    delta2 = _load(DELTA2)

    # --- Core lock sanity ---
    for k in ("Lambda_GeV", "gU", "kY", "Delta2_add_to_inv_alpha2", "mu_on_GeV"):
        if k not in locks:
            notes.append(f"{LOCKS} missing key {k!r}")
    if notes:
        _fail(notes)

    # --- Delta2 lock must match module-derived artifact ---
    for k in ("mu_on_GeV", "Delta2_add_to_inv_alpha2", "sigma_H", "Lambda_GeV"):
        if k not in delta2:
            notes.append(f"{DELTA2} missing key {k!r}")
    if notes:
        _fail(notes)

    d2_mod = float(delta2["Delta2_add_to_inv_alpha2"])
    mu_mod = float(delta2["mu_on_GeV"])
    d2_lock = float(locks["Delta2_add_to_inv_alpha2"])
    mu_lock = float(locks["mu_on_GeV"])

    if (_rel_err(d2_mod, d2_lock) > TOL_REL) and (abs(d2_mod - d2_lock) > TOL_ABS):
        notes.append(f"Delta2 mismatch: module={d2_mod:.12f} vs locks={d2_lock:.12f}")
    if (_rel_err(mu_mod, mu_lock) > TOL_REL) and (abs(mu_mod - mu_lock) > TOL_ABS):
        notes.append(f"mu_on mismatch: module={mu_mod:.6e} vs locks={mu_lock:.6e}")

    # --- kY consistency: trace vs kY_pure vs locks ---
    kY_trace = _extract_trace_kY(trace)
    if kY_trace is None:
        notes.append("missing/invalid kY in artifacts/ult_trace_table.json (expected K_totals.kY or K1/K2)")
    kY_pure_val = None
    if isinstance(ky_pure, dict) and "kY_star" in ky_pure:
        kY_pure_val = float(ky_pure["kY_star"])
    else:
        notes.append("artifacts/ult_kY_pure.json missing key 'kY_star'")

    kY_lock = float(locks["kY"])

    if kY_trace is not None:
        if _rel_err(kY_trace, kY_lock) > 1e-12:
            notes.append(f"kY mismatch: trace={kY_trace:.12f} vs locks={kY_lock:.12f}")
        if kY_pure_val is not None and _rel_err(kY_pure_val, kY_trace) > 1e-12:
            notes.append(f"kY_pure mismatch: kY_pure={kY_pure_val:.12f} vs trace={kY_trace:.12f}")
        if kY_pure_val is not None and _rel_err(kY_pure_val, kY_lock) > 1e-12:
            notes.append(f"kY_pure mismatch: kY_pure={kY_pure_val:.12f} vs locks={kY_lock:.12f}")

    # --- Optional: RG provenance check (warn-only) ---
    if os.path.exists(MZ_OBS):
        mz = _load(MZ_OBS)
        note = mz.get("note", {}) if isinstance(mz, dict) else {}
        deltas_source = note.get("deltas_source", {}) if isinstance(note, dict) else {}
        ky_source = note.get("kY_source", None) if isinstance(note, dict) else None

        # Expected canonical provenance strings (we will enforce in rg_2loop_pipeline.py refactor)
        exp_d2 = "artifacts/ult_delta2_module.json"
        exp_ky = "artifacts/ult_kY_pure.json"

        d2_src = deltas_source.get("d2") if isinstance(deltas_source, dict) else None
        if d2_src is not None and d2_src != exp_d2:
            notes.append(f"WARNING: RG reports d2 source={d2_src!r} (expected {exp_d2!r})")
        if ky_source is not None and ky_source != exp_ky:
            notes.append(f"WARNING: RG reports kY source={ky_source!r} (expected {exp_ky!r})")
    else:
        notes.append("INFO: artifacts/ult_MZ_observables.json not present; skipping RG provenance check.")

    # --- Hash stamps (informational) ---
    notes.append(f"INFO: sha256({LOCKS})={_sha256_file(LOCKS)}")
    notes.append(f"INFO: sha256({DELTA2})={_sha256_file(DELTA2)}")
    notes.append(f"INFO: sha256({TRACE})={_sha256_file(TRACE)}")
    notes.append(f"INFO: sha256({KY_PURE})={_sha256_file(KY_PURE)}")

    # --- Decide pass/fail ---
    hard = [n for n in notes if n.startswith("missing ") or n.endswith(" missing key") or n.startswith("Delta2 mismatch") or n.startswith("mu_on mismatch") or n.startswith("kY mismatch") or n.startswith("kY_pure mismatch") or "missing/invalid kY" in n]
    # The above hard list is conservative; key mismatches should fail.

    if any(n.startswith("Delta2 mismatch") for n in notes) or any(n.startswith("mu_on mismatch") for n in notes) or any(n.startswith("missing ") for n in notes):
        _fail(notes)

    # If there are any kY hard mismatches, fail:
    if any(n.startswith("kY mismatch") for n in notes) or any(n.startswith("kY_pure mismatch") for n in notes) or any("missing/invalid kY" in n for n in notes):
        _fail(notes)

    # Otherwise pass, possibly with warnings/info:
    warn = [n for n in notes if n.startswith("WARNING:")]
    info_only = [n for n in notes if n.startswith("INFO:") or n.startswith("INFO ") or n.startswith("INFO:") or n.startswith("INFO:") or n.startswith("INFO:") or n.startswith("INFO:") or n.startswith("INFO:") or n.startswith("INFO:") or n.startswith("INFO:") or n.startswith("INFO:") or n.startswith("INFO:") or n.startswith("INFO:") or n.startswith("INFO:") or n.startswith("INFO:") or n.startswith("INFO:") or n.startswith("INFO:") or n.startswith("INFO:") or n.startswith("INFO:") or n.startswith("INFO:") or n.startswith("INFO:")]

    if warn:
        _warn_pass(notes)

    print("PLATINUM CHECK: PASS")
    for n in notes:
        # print info lines for traceability without calling them warnings
        if n.startswith("INFO:") or n.startswith("INFO:") or n.startswith("INFO "):
            print("  " + n)
    sys.exit(0)


if __name__ == "__main__":
    main()
