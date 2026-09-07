#!/usr/bin/env bash
# Build without Glyphs. The first run installs pinned tools into build/venv.
set -euo pipefail
script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
repo_dir="$(cd -- "$script_dir/.." && pwd)"
venv_dir="$repo_dir/build/venv"
requirements="$script_dir/font-requirements.txt"
if [[ ! -x "$venv_dir/bin/python" ]]; then
  "${PYTHON:-python3}" -m venv "$venv_dir"
fi
if [[ ! -f "$venv_dir/requirements.txt" ]] || ! cmp -s "$requirements" "$venv_dir/requirements.txt"; then
  "$venv_dir/bin/python" -m pip install -r "$requirements"
  cp "$requirements" "$venv_dir/requirements.txt"
fi
exec "$venv_dir/bin/python" "$script_dir/build-fonts.py" "$@"
