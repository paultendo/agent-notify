#!/usr/bin/env bash
set -euo pipefail

dest_dir="${CODEX_NOTIFY_BIN_DIR:-$HOME/bin}"
dest="$dest_dir/agent-notify"
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
src="$script_dir/agent-notify"

if [[ ! -f "$src" ]]; then
  echo "Error: missing helper script at $src" >&2
  exit 1
fi

mkdir -p "$dest_dir"
cp "$src" "$dest"
chmod +x "$dest"

if [[ -f "$script_dir/VERSION" ]]; then
  ver="$(cat "$script_dir/VERSION")"
  # Cross-platform sed -i (macOS needs '' arg, Linux does not)
  if sed --version >/dev/null 2>&1; then
    # GNU sed (Linux)
    sed -i "s/^VERSION=.*/VERSION=\"$ver\"/" "$dest"
  else
    # BSD sed (macOS)
    sed -i '' "s/^VERSION=.*/VERSION=\"$ver\"/" "$dest"
  fi
fi

echo "Installed: $dest"

echo ""
echo "Quick setup (auto-configures all detected agents):"
echo "  $dest --setup"
echo ""
echo "Or configure individually:"
echo "  $dest --setup-codex     # Codex CLI"
echo "  $dest --setup-claude    # Claude Code"
echo "  $dest --setup-gemini    # Gemini CLI"
echo ""
echo "macOS recommended: brew install terminal-notifier"
echo "Linux recommended: sudo apt install libnotify-bin (or notify-send)"
