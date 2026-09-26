#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
script="$repo_root/agent-notify"

tmp_home="$(mktemp -d)"
trap 'rm -rf "$tmp_home"' EXIT

mkdir -p "$tmp_home/.codex"
cat > "$tmp_home/.codex/config.toml" <<'EOF'
model = "gpt-5.4"

[tui]
status_line = ["model"]
EOF

config_file="$tmp_home/.codex/config.toml"

HOME="$tmp_home" "$script" --setup-codex >/dev/null

python3 - "$config_file" "$script" <<'PY'
import pathlib
import sys
import tomllib

config_path = pathlib.Path(sys.argv[1])
script_path = sys.argv[2]
data = tomllib.loads(config_path.read_text())

assert data["notify"] == [script_path], data
assert data["tui"]["status_line"] == ["model"], data
assert "notify" not in data["tui"], data
PY

HOME="$tmp_home" "$script" --setup-codex >/dev/null

notify_count="$(grep -c '^notify = \[' "$config_file")"
if [[ "$notify_count" != "1" ]]; then
  echo "expected one top-level notify entry, found $notify_count" >&2
  exit 1
fi
