# Spectral-Seed (Module-Native Spectral Locks + Δ2)

This repo accompanies the paper in `paper/` and provides an **audit-grade, reproducible pipeline** for:

- emitting trace/module invariants,
- deriving a **discrete integer rule** `N` from trace invariants,
- constructing a **minimal forced SU(2) Dirac doublet** finite-`D_F` artifact,
- deriving **σ_H → μ_on → Δ2** in a **module-native** way (no MZ-target inference),
- running a deterministic 2-loop SM RG pipeline wired to those locked inputs,
- verifying provenance and consistency with audits.

---

## Repo layout

```
src/        # scripts (canonical, refactored)
config/     # input config JSONs (source of truth inputs)
artifacts/  # generated outputs (not committed by default)
paper/      # LaTeX manuscript + bibliography
reproduce.sh
requirements.txt
README.md
```

### Canonical config files (`config/`)
- `config/constants.json` — contains `Lambda` and `gU`
- `config/thresholds.json` — threshold masses used by RG
- `config/highscale_shifts.json` — optional high-scale shifts (`d1,d3`, typically 0)
- `config/locks.json` — lock summary used by audits (Λ, gU, kY, μ_on, Δ2, etc.)

### Canonical generated artifacts (`artifacts/`)
- `artifacts/ult_trace_table.json` (+ `.tex`) — trace totals + anomaly checks
- `artifacts/ult_kY_pure.json` — target-free kY artifact
- `artifacts/ult_sigma_integer_rule.json` — derived integer rule `N`
- `artifacts/ult_DF_full.npy` — minimal forced-sector D_F block
- `artifacts/ult_DF_index_map.json` — basis map + provenance hashes
- `artifacts/ult_delta2_module.json` — σ_H, μ_on, Δ2 + provenance
- `artifacts/ult_MZ_observables.json` — RG outputs + provenance

> Note: artifacts are **outputs**. By default, you generate them locally via `./reproduce.sh`.

---

## Quickstart

### 1) Create and activate a virtual environment

```bash
python3 -m venv .venv --without-pip
./.venv/bin/python3 -m ensurepip --upgrade
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 2) Run the full reproducible pipeline

```bash
chmod +x reproduce.sh
./reproduce.sh
```

If successful, you should see:
- `[AUDIT] PASS ...`
- `PLATINUM CHECK: PASS`
- `REPRODUCE: OK`

---

## What `reproduce.sh` does (pipeline order)

1. `src/trace_emit.py`  
   Generates `artifacts/ult_trace_table.json` (trace invariants + anomaly checks)

2. `src/ky_pure.py`  
   Writes `artifacts/ult_kY_pure.json` (kY with no low-energy target language)

3. `src/sigma_integer_rule_from_trace.py`  
   Derives `N` from trace invariants → `artifacts/ult_sigma_integer_rule.json`

4. `src/df_build_forced_doublet.py`  
   Builds the minimal forced doublet `D_F` artifact + index map

5. `src/delta2_from_module.py`  
   Computes `σ_H → μ_on → Δ2` → `artifacts/ult_delta2_module.json`

6. `src/audit_delta2_lock.py`  
   Confirms `config/locks.json` matches the module-derived Δ2 and μ_on

7. `src/platinum_check.py`  
   Top-level integrity check (locks + provenance sanity)

8. `src/rg_2loop_pipeline.py`  
   Runs deterministic 2-loop RG with thresholds:
   - sources `d2` from `artifacts/ult_delta2_module.json`
   - sources `kY` from `artifacts/ult_kY_pure.json`
   - writes `artifacts/ult_MZ_observables.json` with provenance

---

## Non-negotiable audit rules

- No MZ-target inference is allowed to derive `σ_H`, `μ_on`, or `Δ2`.
- Production code does not read or reference:
  - `ULT_kYstar_muon_solver.py`
  - `ult_kYstar_muon.json`
- `Δ2` is sourced from: `artifacts/ult_delta2_module.json`
- `kY` is sourced from: `artifacts/ult_kY_pure.json`

---

## Notes on version control (why artifacts are usually not committed)

Artifacts in `artifacts/` are generated outputs. Keeping them uncommitted avoids:
- stale output confusion,
- giant diffs / binary noise (`.npy`),
- merge conflicts.

If you want a paper snapshot, commit only the lightweight JSON artifacts and ignore `.npy`.

Suggested `.gitignore`:

```gitignore
.venv/
__pycache__/
*.pyc
.DS_Store
artifacts/
```

---

## Paper

The manuscript is in `paper/paper.tex` with citations in `paper/refs.bib`.

Compile (example):

```bash
cd paper
pdflatex paper.tex
bibtex paper
pdflatex paper.tex
pdflatex paper.tex
```

---

## License

MIT License — see `LICENSE`.
