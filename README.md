# Codex macOS Notifications (VSCode-friendly)

This setup adds macOS notifications for Codex runs, with optional VSCode activation on click, grouping per thread, and a clean config entry.

## What it does
- Shows a notification when a Codex agent turn completes.
- Uses the JSON payload from Codex to build a nicer title/message and group notifications per thread.
- Activates VSCode when you click the notification (if `terminal-notifier` is installed).
- Falls back to `osascript` if `terminal-notifier` is not installed.

## Files created/updated
- `~/bin/codex-notify` (notification helper script)
- `~/.codex/config.toml` (notify hook)

## Install (macOS)
1) Run the installer script in this repo:

```bash
chmod +x ./install-codex-notify.sh
./install-codex-notify.sh
```

2) Wire it into Codex config (use the exact path on your machine or copy the line printed by the installer):

```toml
# ~/.codex/config.toml
# Replace the path with your actual home path (TOML won't expand ~ or $HOME).
notify = ["/Users/yourname/bin/codex-notify"]
```

3) Optional but recommended (for click-to-activate and better control):

```bash
brew install terminal-notifier
```

Restart Codex and run a quick task to verify notifications.

## Requirements
- macOS (Notification Center + `osascript`).
- `python3` for JSON payload parsing.
- `terminal-notifier` is optional but recommended for click-to-activate and better control.

## Usage
Manual invocation (title/message):

```bash
codex-notify "Codex" "Task finished"
```

Manual invocation (JSON payload):

```bash
codex-notify '{"type":"agent-turn-complete","last-assistant-message":"All set","input-messages":["ping"],"cwd":"/tmp","thread-id":"demo"}'
```

## Environment variables (optional)
- `CODEX_NOTIFY_BIN_DIR` sets the install destination (default `~/bin`).
- `CODEX_SILENT=1` disables the sound.
- `CODEX_ACTIVATE_BUNDLE` controls which app is activated on click (default `com.microsoft.VSCode`).
- `CODEX_SENDER_BUNDLE` controls the icon/name shown in notifications (default `com.microsoft.VSCode`).
- `CODEX_SUPPRESS_FRONTMOST=0` disables suppression when the target app is already frontmost (default is to suppress).
- `CODEX_NOTIFY_EVENT_TYPES` controls which event types trigger notifications (comma-separated). Use `*` to notify on all events.
- `CODEX_NOTIFY_EXEC_ONLY=0` uses `-activate`/`-sender` instead of the more reliable `-execute` activation (default is execute-only).
- `CODEX_NOTIFY_APP_ICON` sets a custom icon path or URL for notifications (useful to show the VSCode icon without `-sender`). Local paths are converted to `file://` URLs.

## Notes
- Grouping is based on `thread-id` from the JSON payload, so repeated notifications in the same thread replace each other.
- If `terminal-notifier` is not installed, the script falls back to `osascript` and still shows notifications.
- The script uses `python3` to parse the JSON payload; without it, it falls back to the plain "Codex / Task finished" message.

## Troubleshooting
- No notification: ensure the `notify` line is in `~/.codex/config.toml` and points to the correct path.
- No sound: check `CODEX_SILENT` and confirm `/System/Library/Sounds/Glass.aiff` exists.
- Click doesn’t activate VSCode: install `terminal-notifier` and verify `CODEX_ACTIVATE_BUNDLE`. If Codex runs with a minimal PATH, ensure `terminal-notifier` is in `/opt/homebrew/bin` or `/usr/local/bin`. By default the script uses `-execute` (more reliable than `-activate` on some systems). If you want a VSCode icon while keeping execute-only activation, set `CODEX_NOTIFY_APP_ICON` or rely on the default VSCode icon path if present.

## Changelog
- 0.1.0 - Initial release.

## License
MIT. See `LICENSE`.

## Uninstall
- Remove the notify line from `~/.codex/config.toml`.
- Delete the script: `rm ~/bin/codex-notify`.
- (Optional) uninstall `terminal-notifier`: `brew uninstall terminal-notifier`.
