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

# A config an older agent-notify broke: its hook was appended under the last table, where Codex never read it
cat > "$config_file" <<'TOML'
model = "gpt-5.4"

[tui]
status_line = ["model"]

notify = ["/old/place/agent-notify"]
TOML

HOME="$tmp_home" "$script" --setup-codex >/dev/null

python3 - "$config_file" "$script" <<'PY'
import pathlib
import sys
import tomllib

data = tomllib.loads(pathlib.Path(sys.argv[1]).read_text())
assert data["notify"] == [sys.argv[2]], data
assert data["tui"] == {"status_line": ["model"]}, data
assert data["model"] == "gpt-5.4", data
PY

# No config yet: the hook is the whole file
rm "$config_file"
HOME="$tmp_home" "$script" --setup-codex >/dev/null
expected="notify = [\"$script\"]"
if [[ "$(cat "$config_file")" != "$expected" ]]; then
  echo "expected a new config holding only the hook, got: $(cat "$config_file")" >&2
  exit 1
fi

echo "setup-codex: all cases pass"
