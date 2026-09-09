#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
scratch_dir="$(mktemp -d)"
python_bin="${PYTHON_BIN:-python3}"
trap 'rm -rf "$scratch_dir"' EXIT

"$python_bin" -m build --no-isolation --wheel --outdir "$scratch_dir/wheel" "$project_root/python"
"$python_bin" -m pip install --no-deps --target "$scratch_dir/python" "$scratch_dir"/wheel/*.whl
RETURN_SCENARIO_ENGINE_PYTHONPATH="$scratch_dir/python" PYTHON="$python_bin" node --test "$project_root/test/conformance.test.mjs"
