# Codex Notify

macOS notifications for Codex with reliable VSCode activation. (macOS-only.)

[![shellcheck](https://github.com/paultendo/codex-notify/actions/workflows/shellcheck.yml/badge.svg)](https://github.com/paultendo/codex-notify/actions/workflows/shellcheck.yml)
[![release](https://img.shields.io/github/v/release/paultendo/codex-notify)](https://github.com/paultendo/codex-notify/releases/latest)

## Quick start

### Option A: Homebrew

```bash
brew tap paultendo/codex-notify https://github.com/paultendo/codex-notify
brew install codex-notify
```

### Option B: Manual install
1) Run the installer:

```bash
chmod +x ./install-codex-notify.sh
./install-codex-notify.sh
```

2) Configure the notify hook (automatic):

```bash
codex-notify --setup
```

Or add manually to `~/.codex/config.toml`:

```toml
notify = ["/Users/yourname/bin/codex-notify"]
```

3) Optional but recommended:

```bash
brew install terminal-notifier
```

Restart Codex and run a quick task to verify notifications.

## Features
- Different sounds for completion vs. approval/input-needed events.
- Clean, grouped notifications per Codex thread.
- Rich titles/messages from Codex JSON payloads.
- Terminal echo: prints a summary line to stderr for logging/visibility.
- Click to activate VSCode (execute-only by default for reliability).
- `--setup` flag for zero-friction config.toml setup.
- TTS (text-to-speech) via macOS `say` for audible status when away from desk.
- Webhook support for remote notifications (Discord, Slack, etc.).
- Do Not Disturb / Focus awareness — skip notifications when Focus mode is active.
- Schedule window — only notify during configured hours.
- Rate limiting — throttle rapid-fire notifications.
- Notification log — append history to `~/.codex/notify.log`.
- Custom hooks — run any command on notification events.
- Self-update via `--update`.
- Homebrew installable.
- Fallback to `osascript` if `terminal-notifier` is missing.

## Requirements
- macOS (Notification Center + `osascript`).
- `python3` for JSON payload parsing.
- `terminal-notifier` optional but recommended for activation and grouping.

## Usage
Manual invocation (title/message):

```bash
codex-notify "Codex" "Task finished"
```

Manual invocation (JSON payload):

```bash
codex-notify '{"type":"agent-turn-complete","last-assistant-message":"All set","input-messages":["ping"],"cwd":"/tmp","thread-id":"demo"}'
```

Test your setup:

```bash
codex-notify --test              # completion sound (Glass)
codex-notify --test-approval     # approval sound (Sosumi)
codex-notify --test-say          # completion with TTS
codex-notify --update            # update to latest release
```

## Configuration
Environment variables:
- `CODEX_NOTIFY_BIN_DIR` sets the install destination (default `~/bin`).
- `CODEX_SILENT=1` disables all sounds.
- `CODEX_NOTIFY_QUIET=1` suppresses the terminal echo line (on by default).
- `CODEX_NOTIFY_SOUND` sets the completion sound (path or system sound name, default `Glass`).
- `CODEX_NOTIFY_APPROVAL_SOUND` sets the approval/input-needed sound (default `Sosumi`).
- `CODEX_ACTIVATE_BUNDLE` sets which app is activated on click (default `com.microsoft.VSCode`).
- `CODEX_SENDER_BUNDLE` sets the sender icon/name when using `-activate` (default `com.microsoft.VSCode`).
- `CODEX_SUPPRESS_FRONTMOST=0` disables suppression when the target app is already frontmost.
- `CODEX_NOTIFY_EVENT_TYPES` limits which event types notify (comma-separated, default `*` = all events).
- `CODEX_NOTIFY_EXEC_ONLY=0` uses `-activate`/`-sender` instead of execute-only activation.
- `CODEX_NOTIFY_APP_ICON` sets a custom icon path or URL. Local paths are converted to `file://` URLs.
- `CODEX_NOTIFY_DEBUG=1` keeps `terminal-notifier` output and error details for troubleshooting.
- `CODEX_NOTIFY_SAY=1` enables text-to-speech via macOS `say`. Respects `CODEX_SILENT`.
- `CODEX_NOTIFY_SAY_VOICE` sets the TTS voice (e.g. `Daniel`). Default: system voice.
- `CODEX_NOTIFY_SAY_RATE` sets the TTS speech rate in words per minute. Default: system rate.
- `CODEX_NOTIFY_WEBHOOK` sets a webhook URL for remote notifications (Discord, Slack, etc.).
- `CODEX_NOTIFY_EXEC_CMD` overrides the execute command (default is `open -b <bundle_id>`).
- `CODEX_NOTIFY_DND=1` skips notifications when macOS Focus/DND is active.
- `CODEX_NOTIFY_SCHEDULE="09:00-18:00"` only notifies during the given window (24h format, supports overnight ranges).
- `CODEX_NOTIFY_THROTTLE=5` suppresses notifications within N seconds of the last one (default `0` = disabled).
- `CODEX_NOTIFY_LOG=1` appends each notification to `~/.codex/notify.log`.
- `CODEX_NOTIFY_LOG_FILE` overrides the log file path.
- `CODEX_NOTIFY_HOOK` runs a command on each notification: `$HOOK "title" "message" "category"`.

Example (louder sound):

```bash
export CODEX_NOTIFY_SOUND="Funk"
```

If your sound path or name contains spaces, quote it in your shell.

## Notes
- Some macOS versions ignore `-appIcon` and use the sender app icon instead.
- Execute-only activation is the most reliable path; it may show the Terminal icon.
- If `terminal-notifier` is missing, the script falls back to `osascript`.
- Without `python3`, JSON payloads produce a clear error; manual title/message mode still works.

## FAQ
- **Why does the icon show Terminal?** Execute-only activation is the most reliable way to bring your editor to front on click, but macOS shows the Terminal icon for `terminal-notifier`. This is cosmetic only.
- **How do I change the activated app?** Set `CODEX_ACTIVATE_BUNDLE` to your editor's bundle ID (e.g. `com.microsoft.VSCodeInsiders`).

## Security
- All data stays local by default. Webhook support (`CODEX_NOTIFY_WEBHOOK`) is opt-in and sends notification title/message to the configured URL.
- Payload is read from stdin/args and used only to build notification text.

## Screenshot
![Codex Notify](./assets/screenshot.png)

## Troubleshooting
- No notification: check `~/.codex/config.toml` and macOS notification permissions.
- No sound: check `CODEX_SILENT` and `CODEX_NOTIFY_SOUND` (path or system sound name).
- Click does not activate VSCode: install `terminal-notifier` and verify `CODEX_ACTIVATE_BUNDLE`.
- Icon looks like Terminal: this is expected with execute-only activation. It's cosmetic only.
- Seeing a `terminal-notifier` usage banner: make sure your `notify` hook points to `codex-notify` and set `CODEX_NOTIFY_DEBUG=1` to inspect args.
- Clicking “Show” opens Script Editor: set `CODEX_NOTIFY_EXEC_CMD="/usr/bin/open -b com.microsoft.VSCode"` to force `open` instead of AppleScript.

## Changelog
- 0.6.0 - DND/Focus awareness, schedule window, rate limiting, notification log, custom hooks, `--update`, Homebrew formula.
- 0.4.0 - TTS support (`say`), webhook notifications, `--test-say`.
- 0.3.0 - Differentiated completion/approval sounds, `--setup`, `--test-approval`, default to all event types.
- 0.2.0 - Terminal echo, `--version`/`--help`/`--test` flags, async sound, python3 guard.
- 0.1.8 - Use open(1) for execute activation by default.
- 0.1.7 - Silence terminal-notifier output by default.
- 0.1.6 - Clarify quoting for sound paths.
- 0.1.5 - Add loud-sound example.
- 0.1.4 - Add real screenshot.
- 0.1.3 - Custom sound support and README tweaks.
- 0.1.2 - README polish, FAQ, security note, screenshot placeholder.
- 0.1.1 - README polish and clarified defaults.
- 0.1.0 - Initial release.

## License
MIT. See `LICENSE`.

## Uninstall
- Remove the notify line from `~/.codex/config.toml`.
- Delete the script: `rm ~/bin/codex-notify`.
- Optional: `brew uninstall terminal-notifier`.
