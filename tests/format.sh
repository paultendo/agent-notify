#!/usr/bin/env bash
# shellcheck disable=SC2016  # the backticks in the test messages are literal markdown
# The Codex event parser, run straight from the script: notification text without markdown, clipped at a word
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
parser="$(mktemp)"
trap 'rm -f "$parser"' EXIT
sed -n "/python3 - \"\$payload\" <<'PY'/,/^PY\$/p" "$repo_root/agent-notify" | sed '1d;$d' > "$parser"

title() { python3 "$parser" "$1" | head -1; }

got="$(title '{"type":"agent-turn-complete","last-assistant-message":"**Done.** Fixed the `setup` step in __init__.py.","input-messages":["x"]}')"
[[ "$got" == "Codex: Done. Fixed the setup step in __init__.py." ]] || { echo "markdown: got '$got'" >&2; exit 1; }

got="$(title '{"type":"agent-turn-complete","last-assistant-message":"The migration renamed every column in the accounts table and rebuilt the indexes that depended on them","input-messages":["x"]}')"
[[ "$got" == *"…" && "$got" != *" …" && ${#got} -le 97 ]] || { echo "clip: got '$got'" >&2; exit 1; }
[[ "$got" == "Codex: The migration renamed every column in the accounts table and rebuilt the indexes that…" ]] || { echo "clip at a word: got '$got'" >&2; exit 1; }

echo "format: all cases pass"
