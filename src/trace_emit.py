#!/usr/bin/env python3
"""
src/trace_emit.py  (AUDIT-GRADE)

Build the gauge-trace table (K1,K2,K3) and verify anomalies from SM content + module normalizations.

Outputs (canonical):
- artifacts/ult_trace_table.json
- artifacts/ult_trace_table.tex

Hard rules:
- No low-energy target inference
- No kYstar_muon references
- No hidden magic numbers: module normalizations are sourced from config/locks.json (trace_summary)
  (fallback constants are allowed only if locks.json is missing, and are clearly labeled)
- Provenance + sha256 hashes recorded
"""

import json
import os
import hashlib
from fractions import Fraction
from typing import Any, Dict, Tuple

CONFIG_DIR = "config"
ART_DIR = "artifacts"

LOCKS_PATH = os.path.join(CONFIG_DIR, "locks.json")

OUT_JSON = os.path.join(ART_DIR, "ult_trace_table.json")
OUT_TEX = os.path.join(ART_DIR, "ult_trace_table.tex")


def _sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _load_json(path: str) -> Dict[str, Any]:
    with open(path, "r") as f:
        return json.load(f)


# --- Standard Model content (3 generations), left-chiral basis for anomaly checks ---
# Notation: (color_dim, isospin_dim, generations, Y)
SM_FIELDS = [
    # Left-handed doublets
    {"name": "Q_L",   "color": 3, "iso": 2, "gens": 3, "Y": Fraction(1, 6),  "rep_SU3": "3",    "rep_SU2": "2"},
    {"name": "L_L",   "color": 1, "iso": 2, "gens": 3, "Y": Fraction(-1, 2), "rep_SU3": "1",    "rep_SU2": "2"},
    # Right-handed singlets, entered as LH conjugates for anomaly sums
    {"name": "u_R^c", "color": 3, "iso": 1, "gens": 3, "Y": Fraction(-2, 3), "rep_SU3": "3bar", "rep_SU2": "1"},
    {"name": "d_R^c", "color": 3, "iso": 1, "gens": 3, "Y": Fraction(1, 3),  "rep_SU3": "3bar", "rep_SU2": "1"},
    {"name": "e_R^c", "color": 1, "iso": 1, "gens": 3, "Y": Fraction(1, 1),  "rep_SU3": "1",    "rep_SU2": "1"},
]

# Group theory data
T2_fund = Fraction(1, 2)   # Dynkin index for SU(2) fundamental
T3_fund = Fraction(1, 2)   # Dynkin index for SU(3) fundamental (3 or 3bar)


def base_sums() -> Tuple[Fraction, Fraction, Fraction]:
    """
    Compute the base (raw) sums before module normalization constants:
      U1_base = sum dim * Y^2
      SU2_base = sum (#doublets) * T2_fund
      SU3_base = sum (#triplets) * T3_fund
    All sums are over 3 generations.
    """
    U1 = Fraction(0, 1)
    SU2 = Fraction(0, 1)
    SU3 = Fraction(0, 1)

    for f in SM_FIELDS:
        mult = f["color"] * f["iso"] * f["gens"]
        Y = f["Y"]
        U1 += mult * (Y * Y)

        if f["rep_SU2"] == "2":
            n_doublets = f["color"] * f["gens"]
            SU2 += n_doublets * T2_fund

        if f["rep_SU3"] in ("3", "3bar"):
            n_triplets = f["iso"] * f["gens"]
            SU3 += n_triplets * T3_fund

    return U1, SU2, SU3


def row_contribs_U1(c1: float):
    rows = []
    for f in SM_FIELDS:
        mult = f["color"] * f["iso"] * f["gens"]
        Y2 = float(f["Y"] * f["Y"])
        raw = mult * Y2
        K1_piece = c1 * raw
        rows.append({
            "name": f["name"],
            "dim": mult,
            "Y": float(f["Y"]),
            "Y2": float(f["Y"] * f["Y"]),
            "U1_raw": float(raw),
            "K1_piece": float(K1_piece),
        })
    return rows


def anomalies_per_gen():
    # Divide multiplicities by 3 to get per generation
    def per_gen(f):
        return {
            "color": f["color"], "iso": f["iso"], "gens": 1, "Y": f["Y"],
            "rep_SU3": f["rep_SU3"], "rep_SU2": f["rep_SU2"], "name": f["name"]
        }

    fields = [per_gen(f) for f in SM_FIELDS]

    def mult(f): return f["color"] * f["iso"] * f["gens"]

    A_U1_cub = sum(mult(f) * (f["Y"] ** 3) for f in fields)
    A_grav = sum(mult(f) * f["Y"] for f in fields)
    A_SU2sqU1 = sum((f["color"] * f["gens"]) * T2_fund * f["Y"] for f in fields if f["rep_SU2"] == "2")
    A_SU3sqU1 = sum((f["iso"] * f["gens"]) * T3_fund * f["Y"] for f in fields if f["rep_SU3"] in ("3", "3bar"))

    return (A_U1_cub, A_grav, A_SU2sqU1, A_SU3sqU1)


def witten_su2_doublets_per_gen() -> int:
    """
    Witten SU(2) anomaly: # of LEFT-HANDED SU(2) doublets must be even.
    Per generation (including color):
      Q_L contributes 3 doublets (one per color)
      L_L contributes 1 doublet
    Total per generation = 4 (even) -> OK.
    """
    count = 0
    for f in SM_FIELDS:
        if f["rep_SU2"] == "2":
            count += int(f["color"])  # per generation
    return count


def _get_module_norms_from_locks() -> Dict[str, Any]:
    """
    Source module-normalization invariants from config/locks.json trace_summary:

      - K_common (e.g., 20)
      - K1_from_spectral (e.g., 26.3969...)

    These are treated as module-native invariants (NOT low-energy targets).
    We do NOT take kY as an input; we compute kY = K1/K2.
    """
    if not os.path.exists(LOCKS_PATH):
        return {"source": None, "K_common": None, "K1_from_spectral": None}

    L = _load_json(LOCKS_PATH)
    ts = L.get("trace_summary", {})
    K_common = None
    K1_from_spectral = None

    if isinstance(ts, dict):
        if "K_common" in ts:
            try:
                K_common = float(ts["K_common"])
            except Exception:
                K_common = None
        if "K1_from_spectral" in ts:
            try:
                K1_from_spectral = float(ts["K1_from_spectral"])
            except Exception:
                K1_from_spectral = None

    return {
        "source": LOCKS_PATH,
        "K_common": K_common,
        "K1_from_spectral": K1_from_spectral,
    }


def main() -> None:
    os.makedirs(ART_DIR, exist_ok=True)

    # Raw (SM) base sums over 3 generations:
    U1_base, SU2_base, SU3_base = base_sums()

    # Module invariants (sourced from locks.json if available)
    mod = _get_module_norms_from_locks()

    # Defaults ONLY if locks.json is missing or incomplete.
    DEFAULT_K_COMMON = 20.0
    DEFAULT_K1_FROM_SPECTRAL = 26.39695192027321

    K_common = mod["K_common"] if mod["K_common"] is not None else DEFAULT_K_COMMON
    K1_from_spectral = mod["K1_from_spectral"] if mod["K1_from_spectral"] is not None else DEFAULT_K1_FROM_SPECTRAL

    # c2=c3 set so that K2=K3=K_common for the SM base sums (SU2_base=SU3_base=6 in this model)
    c2 = float(K_common) / float(SU2_base)  # 20/6 -> 10/3
    c3 = float(K_common) / float(SU3_base)

    # c1 set so that K1 matches the module-native K1_from_spectral (NOT a kY target)
    c1 = float(K1_from_spectral) / float(U1_base)  # U1_base=10

    # Assemble totals
    K1 = c1 * float(U1_base)
    K2 = c2 * float(SU2_base)
    K3 = c3 * float(SU3_base)
    kY = K1 / K2

    # Local anomaly checks (per generation; LH basis):
    A_U1_cub, A_grav, A_SU2sqU1, A_SU3sqU1 = anomalies_per_gen()

    # Global SU(2) Witten parity check
    witten_doublets = witten_su2_doublets_per_gen()
    witten_ok = (witten_doublets % 2 == 0)

    out = {
        "base_sums_over_3gens": {
            "U1_base_sum_dimY2": float(U1_base),
            "SU2_base_sum_Tfund": float(SU2_base),
            "SU3_base_sum_Tfund": float(SU3_base),
        },
        "module_normalizations": {
            "c1_U1": float(c1),
            "c2_SU2": float(c2),
            "c3_SU3": float(c3),
            "K_common_target": float(K_common),
            "K1_from_spectral_target": float(K1_from_spectral),
            "meaning": "Normalization targets sourced from trace_summary invariants (not low-energy targets).",
        },
        "K_totals": {
            "K1": float(K1),
            "K2": float(K2),
            "K3": float(K3),
            "K_common": float(K2),
            "kY": float(kY),
        },
        "U1_row_breakdown": row_contribs_U1(c1),
        "anomalies_per_generation_LH": {
            "U1_cubed": float(A_U1_cub),
            "grav2_U1": float(A_grav),
            "SU2sq_U1": float(A_SU2sqU1),
            "SU3sq_U1": float(A_SU3sqU1),
        },
        "witten_SU2": {
            "doublets_per_generation": int(witten_doublets),
            "ok": bool(witten_ok),
            "meaning": "Witten SU(2) global anomaly absent iff number of LH SU(2) doublets is even."
        },
        # --- #1: Explicit note about the forced neutral doublet used for Δ2 ---
        "forced_doublet_note": {
            "sector": "H_doublet",
            "assumed_hypercharge": 0.0,
            "anomaly_impact": (
                "Because Y=0, adding the forced doublet contributes 0 to U(1)^3, grav^2-U(1), "
                "SU(2)^2-U(1), and SU(3)^2-U(1) local anomaly sums."
            )
        },
        "provenance": {
            "inputs": {
                "locks": (mod["source"] if mod["source"] is not None else None),
            },
            "inputs_sha256": {
                "locks": (_sha256_file(LOCKS_PATH) if os.path.exists(LOCKS_PATH) else None),
            },
            "meaning": (
                "Trace table computed from explicit SM representation content. "
                "Module normalization targets (K_common, K1_from_spectral) are sourced from config/locks.json trace_summary "
                "to avoid hidden constants. kY is computed as kY = K1/K2 (derived, not targeted)."
            ),
            "fallback_used": {
                "K_common": (mod["K_common"] is None),
                "K1_from_spectral": (mod["K1_from_spectral"] is None),
            },
        },
    }

    with open(OUT_JSON, "w") as f:
        json.dump(out, f, indent=2, sort_keys=True)

    # Also emit a compact LaTeX table for the paper (Appendix A)
    with open(OUT_TEX, "w") as f:
        f.write(
            r"""\begin{table}[h!]
\centering
\caption{Gauge-trace summary from spectral internal module (3 generations).
Base SM sums: $U(1)_Y:\sum \dim Y^2 = 10$, $SU(2):\sum T(\mathbf{2}) = 6$, $SU(3):\sum T(\mathbf{3}) = 6$.
Module normalizations: $c_1=%.9f$, $c_2=%.9f$, $c_3=%.9f$. Totals: $K_1=%.9f$, $K_2=%.9f$, $K_3=%.9f$, hence $k_Y=%.9f$.}
\label{tab:ULT-traces}
\begin{tabular}{lcccc}
\hline\hline
Multiplet $\chi$ & $\dim$ & $Y^2$ & raw $\dim Y^2$ & contrib.\ to $K_1$ \\
\hline
"""
            % (c1, c2, c3, K1, K2, K3, kY)
        )
        for row in row_contribs_U1(c1):
            f.write(
                f"{row['name']} & {row['dim']} & {row['Y2']:.6f} & {row['U1_raw']:.6f} & {row['K1_piece']:.6f} \\\\\n"
            )
        f.write(
            r"""\hline
\multicolumn{3}{r}{Totals} & 10.000000 & %.6f \\
\hline\hline
\end{tabular}
\end{table}
"""
            % (K1)
        )

    print(f"Wrote {OUT_JSON} and {OUT_TEX}")


if __name__ == "__main__":
    main()
