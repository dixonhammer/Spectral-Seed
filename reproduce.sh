#!/usr/bin/env bash
set -euo pipefail

if [[ -z "${VIRTUAL_ENV:-}" ]]; then
  echo "ERROR: activate your venv first: source .venv/bin/activate"
  exit 1
fi

PYTHON="${VIRTUAL_ENV}/bin/python"
if [[ ! -x "$PYTHON" ]]; then
  echo "ERROR: venv python not found/executable at: $PYTHON"
  exit 1
fi

# Optional: show exact interpreter for audit logs
"$PYTHON" -V

"$PYTHON" src/trace_emit.py
"$PYTHON" src/ky_pure.py
"$PYTHON" src/sigma_integer_rule_from_trace.py
"$PYTHON" src/df_build_forced_doublet.py
"$PYTHON" src/delta2_from_module.py
"$PYTHON" src/audit_delta2_lock.py
"$PYTHON" src/platinum_check.py
"$PYTHON" src/rg_2loop_pipeline.py
"$PYTHON" src/platinum_check.py

# Assert expected artifacts exist (fail fast if anything silently skipped)
test -f artifacts/ult_trace_table.json
test -f artifacts/ult_kY_pure.json
test -f artifacts/ult_sigma_integer_rule.json
test -f artifacts/ult_delta2_module.json
test -f artifacts/ult_MZ_observables.json

# Print provenance pointers from the final output
"$PYTHON" -c "import json; print(json.load(open('artifacts/ult_MZ_observables.json'))['note']['kY_source'])"
"$PYTHON" -c "import json; print(json.load(open('artifacts/ult_MZ_observables.json'))['note']['deltas_source'])"

echo "REPRODUCE: OK"
