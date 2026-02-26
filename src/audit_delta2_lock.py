#!/usr/bin/env python3
"""
src/audit_delta2_lock.py  (AUDIT-GRADE)

Purpose
-------
Audit-grade checks that are STRICTLY module-native (no MZ-target inference):

1) Verify config/locks.json matches artifacts/ult_delta2_module.json for:
   - Delta2_add_to_inv_alpha2
   - mu_on_GeV

2) Verify provenance wiring:
   - Ensure the module-derived Δ2 artifact exists and has the expected keys.
   - (Optional) If artifacts/ult_MZ_observables.json exists, confirm the RG pipeline
     reports it sourced d2 from artifacts/ult_delta2_module.json and kY from artifacts/ult_kY_pure.json.

Hard rules enforced
-------------------
- No references to kYstar_muon solver or MZ target files.
- No legacy filename fallback (all paths are canonical repo paths).
"""

import json
import math
import os
import sys
import hashlib
from typing import Any, Dict, Optional

CONFIG_DIR = "config"
ART_DIR = "artifacts"

LOCKS_PATH = os.path.join(CONFIG_DIR, "locks.json")
DELTA2_PATH = os.path.join(ART_DIR, "ult_delta2_module.json")
MZ_OBS_PATH = os.path.join(ART_DIR, "ult_MZ_observables.json")
KY_PURE_PATH = os.path.join(ART_DIR, "ult_kY_pure.json")


def _load_json(path: str) -> Dict[str, Any]:
    with open(path, "r") as f:
        return json.load(f)


def _sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _rel(a: float, b: float) -> float:
    return abs(a - b) / max(1e-30, abs(b))


def _require_exists(path: str, msg: str) -> None:
    if not os.path.exists(path):
        raise SystemExit(msg)


def _get_float(d: Dict[str, Any], key: str, *, where: str) -> float:
    if key not in d:
        raise SystemExit(f"[AUDIT] Missing key {key!r} in {where}")
    try:
        return float(d[key])
    except Exception:
        raise SystemExit(f"[AUDIT] Key {key!r} in {where} is not numeric: {d.get(key)!r}")


def _optional_rg_provenance_checks(notes: list) -> None:
    """
    If RG output exists, confirm it reports correct provenance sources.
    This does NOT rerun RG; it only checks recorded metadata.
    """
    if not os.path.exists(MZ_OBS_PATH):
        notes.append("INFO: artifacts/ult_MZ_observables.json not present; skipping RG provenance check.")
        return

    mz = _load_json(MZ_OBS_PATH)
    note = mz.get("note", {})
    deltas_source = note.get("deltas_source", {})
    kY_source = note.get("kY_source", None)

    # We expect:
    # - d2 sourced from artifacts/ult_delta2_module.json
    # - kY sourced from artifacts/ult_kY_pure.json
    # If the RG script records different strings, we warn (not fail) because
    # this is metadata; the hard fail is the lock match itself.
    expected_d2 = "artifacts/ult_delta2_module.json"
    expected_kY = "artifacts/ult_kY_pure.json"

    d2_src = deltas_source.get("d2")
    if d2_src is None:
        notes.append("WARNING: RG output note.deltas_source.d2 missing (cannot confirm d2 provenance).")
    elif d2_src != expected_d2:
        notes.append(f"WARNING: RG output reports d2 source={d2_src!r} (expected {expected_d2!r}).")

    if kY_source is None:
        notes.append("WARNING: RG output note.kY_source missing (cannot confirm kY provenance).")
    elif kY_source != expected_kY:
        notes.append(f"WARNING: RG output reports kY source={kY_source!r} (expected {expected_kY!r}).")


def main() -> None:
    _require_exists(LOCKS_PATH, f"[AUDIT] Missing {LOCKS_PATH} (expected config/locks.json).")
    _require_exists(
        DELTA2_PATH,
        f"[AUDIT] Missing {DELTA2_PATH} (run src/delta2_from_module.py to generate artifacts/ult_delta2_module.json).",
    )

    L = _load_json(LOCKS_PATH)
    M = _load_json(DELTA2_PATH)

    # Minimal schema sanity for module artifact
    for k in ("sigma_H", "mu_on_GeV", "Lambda_GeV", "Delta2_add_to_inv_alpha2"):
        if k not in M:
            raise SystemExit(f"[AUDIT] artifacts/ult_delta2_module.json missing required key {k!r}")

    notes = []
    ok = True

    dL = _get_float(L, "Delta2_add_to_inv_alpha2", where=LOCKS_PATH)
    dM = _get_float(M, "Delta2_add_to_inv_alpha2", where=DELTA2_PATH)
    if abs(dL - dM) > 1e-9:
        ok = False
        notes.append(f"Delta2 mismatch: locks={dL:.12f} vs module={dM:.12f}")

    muL = _get_float(L, "mu_on_GeV", where=LOCKS_PATH)
    muM = _get_float(M, "mu_on_GeV", where=DELTA2_PATH)
    if _rel(muL, muM) > 1e-12:
        ok = False
        notes.append(f"mu_on mismatch: locks={muL:.6e} vs module={muM:.6e} (rel {_rel(muL, muM):.3e})")

    # Record file hashes for audit traceability (informational)
    locks_sha = _sha256_file(LOCKS_PATH)
    delta2_sha = _sha256_file(DELTA2_PATH)
    notes.append(f"INFO: sha256({LOCKS_PATH})={locks_sha}")
    notes.append(f"INFO: sha256({DELTA2_PATH})={delta2_sha}")

    # Optional RG provenance checks (warn-only)
    _optional_rg_provenance_checks(notes)

    if ok:
        print("[AUDIT] PASS: config/locks.json matches module-derived Δ2 and μ_on exactly.")
        for n in notes:
            print("  " + n)
        return

    print("[AUDIT] FAIL:")
    for n in notes:
        print("  - " + n)
    sys.exit(1)


if __name__ == "__main__":
    main()
