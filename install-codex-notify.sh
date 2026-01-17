#!/usr/bin/env bash
set -euo pipefail

dest_dir="${CODEX_NOTIFY_BIN_DIR:-$HOME/bin}"
dest="$dest_dir/codex-notify"
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
src="$script_dir/codex-notify"

if [[ ! -f "$src" ]]; then
  echo "Error: missing helper script at $src" >&2
  exit 1
fi

mkdir -p "$dest_dir"
cp "$src" "$dest"
chmod +x "$dest"

echo "Installed: $dest"
echo "Add to ~/.codex/config.toml:"
echo "notify = [\"$dest\"]"
echo "Optional: brew install terminal-notifier"
