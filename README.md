# Agent Notify

Cross-platform desktop notifications for AI coding agents — Codex CLI, Claude Code, and Gemini CLI.

[![shellcheck](https://github.com/paultendo/agent-notify/actions/workflows/shellcheck.yml/badge.svg)](https://github.com/paultendo/agent-notify/actions/workflows/shellcheck.yml)
[![release](https://img.shields.io/github/v/release/paultendo/agent-notify)](https://github.com/paultendo/agent-notify/releases/latest)

## Quick start

### Option A: Homebrew (macOS)

```bash
brew tap paultendo/agent-notify https://github.com/paultendo/agent-notify
brew install agent-notify
agent-notify --setup
```

### Option B: Manual install (macOS / Linux / Windows WSL)

1) Clone or download the repo, then run the installer:

```bash
chmod +x ./install-agent-notify.sh
./install-agent-notify.sh
```

2) Configure your agents (automatic):

```bash
agent-notify --setup           # configure all detected agents
```

Or configure individually:

```bash
agent-notify --setup-codex     # Codex CLI → ~/.codex/config.toml
agent-notify --setup-claude    # Claude Code → ~/.claude/settings.json
agent-notify --setup-gemini    # Gemini CLI → ~/.gemini/settings.json
```

3) Platform recommendations:

```bash
# macOS
brew install terminal-notifier

# Linux (Debian/Ubuntu)
sudo apt install libnotify-bin   # notify-send
sudo apt install espeak          # optional TTS

# Linux (Fedora)
sudo dnf install libnotify       # notify-send
sudo dnf install espeak-ng       # optional TTS
```

Restart your agent and run a task to verify notifications.

## Features
- **Multi-agent** — Codex CLI, Claude Code, and Gemini CLI out of the box.
- **Cross-platform** — macOS, Linux, and Windows (WSL / Git Bash).
- Different sounds for completion vs. approval/input-needed events.
- Clean, grouped notifications per session/thread.
- Rich titles/messages extracted from agent JSON payloads.
- Terminal echo: prints a summary line to stderr for logging/visibility.
- **Terminal bell** — automatic fallback for headless/SSH sessions.
- **Duration display** — shows how long the task took.
- **Long-run threshold** — only notify if task exceeded N seconds.
- **Per-project config** — `.agent-notify.env` overrides per repo.
- Click to activate your editor (macOS: execute-only by default). Auto-detects the Codex macOS app.
- `--setup` flag for zero-friction config across all agents.
- TTS (text-to-speech) via macOS `say`, Linux `espeak`/`spd-say`, or Windows SAPI.
- Webhook support for remote notifications (Discord, Slack, etc.).
- Do Not Disturb / Focus awareness — skip notifications when Focus mode is active.
- Schedule window — only notify during configured hours.
- Rate limiting — throttle rapid-fire notifications.
- Notification log — append history to `~/.codex/notify.log`.
- Custom hooks — run any command on notification events.
- Self-update via `--update`.
- Homebrew installable.
- macOS: fallback to `osascript` if `terminal-notifier` is missing.
- Linux: fallback chain `notify-send` → `zenity` → terminal echo.
- Windows: PowerShell toast notifications via WSL/Git Bash.

## Compatibility

### Agents
| Agent | Hook type | Config file | Events |
|-------|-----------|-------------|--------|
| **Codex CLI** | argv JSON | `~/.codex/config.toml` | `agent-turn-complete`, `approval-required` |
| **Claude Code** | stdin JSON | `~/.claude/settings.json` | `Stop`, `Notification` (permission, idle, auth) |
| **Gemini CLI** | stdin JSON | `~/.gemini/settings.json` | `AfterAgent`, `Notification` (tool permission) |

### Platforms
| Platform | Notification | Sound | TTS |
|----------|-------------|-------|-----|
| **macOS** | terminal-notifier / osascript | afplay | say |
| **Linux** | notify-send / zenity | paplay / aplay / ffplay | espeak / spd-say |
| **Windows** (WSL) | PowerShell toast | PowerShell SoundPlayer | PowerShell SAPI |

## Requirements
- `bash` 4.0+ (macOS, Linux, WSL, or Git Bash).
- `python3` for JSON payload parsing and agent setup.
- **macOS**: `terminal-notifier` optional but recommended.
- **Linux**: `libnotify` (`notify-send`) recommended.

## Usage

Manual invocation (title/message):

```bash
agent-notify "Codex" "Task finished"
```

Manual invocation (Codex JSON payload):

```bash
agent-notify '{"type":"agent-turn-complete","last-assistant-message":"All set","input-messages":["ping"],"cwd":"/tmp","thread-id":"demo"}'
```

Test notifications:

```bash
agent-notify --test                  # Codex completion
agent-notify --test-approval         # Codex approval (Sosumi)
agent-notify --test-claude           # Claude Code completion
agent-notify --test-claude-approval  # Claude Code permission prompt
agent-notify --test-gemini           # Gemini CLI completion
agent-notify --test-say              # completion with TTS
agent-notify --test-bell             # terminal bell
agent-notify --update                # update to latest release
```

## Configuration

### Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `CODEX_NOTIFY_SOUND` | `Glass` / `complete` | Completion sound (path or system name) |
| `CODEX_NOTIFY_APPROVAL_SOUND` | `Sosumi` / `dialog-warning` | Approval sound |
| `CODEX_SILENT=1` | — | Disable all sounds |
| `CODEX_NOTIFY_QUIET=1` | — | Suppress terminal echo |
| `CODEX_ACTIVATE_BUNDLE` | `com.microsoft.VSCode` | macOS: app to activate on click |
| `CODEX_SENDER_BUNDLE` | `com.microsoft.VSCode` | macOS: sender icon for `-activate` mode |
| `CODEX_SUPPRESS_FRONTMOST=0` | `1` | Disable suppression when target app is frontmost |
| `CODEX_NOTIFY_EVENT_TYPES` | `*` | Codex event types to handle (comma-separated) |
| `CODEX_NOTIFY_EXEC_ONLY=0` | `1` | macOS: use `-activate` instead of `-execute` |
| `CODEX_NOTIFY_APP_ICON` | — | Custom icon path or URL |
| `CODEX_NOTIFY_SAY=1` | — | Enable text-to-speech |
| `CODEX_NOTIFY_SAY_VOICE` | system | TTS voice name |
| `CODEX_NOTIFY_SAY_RATE` | system | TTS speech rate (wpm, macOS only) |
| `CODEX_NOTIFY_WEBHOOK` | — | Webhook URL for remote notifications |
| `CODEX_NOTIFY_EXEC_CMD` | `open -b <bundle>` | Override click-execute command |
| `CODEX_NOTIFY_DND=1` | — | Skip notifications during Focus/DND |
| `CODEX_NOTIFY_SCHEDULE` | — | Notify only during `HH:MM-HH:MM` window |
| `CODEX_NOTIFY_THROTTLE` | `0` | Suppress notifications within N seconds |
| `CODEX_NOTIFY_LOG=1` | — | Append to `~/.codex/notify.log` |
| `CODEX_NOTIFY_LOG_FILE` | `~/.codex/notify.log` | Override log file path |
| `CODEX_NOTIFY_HOOK` | — | Command to run on each event |
| `CODEX_NOTIFY_DEBUG=1` | — | Show debug output |
| `CODEX_NOTIFY_BELL` | `auto` | Terminal bell: `0`/`1`/`auto` |
| `CODEX_NOTIFY_MIN_DURATION` | `0` | Only notify if N+ seconds elapsed |
| `CODEX_NOTIFY_ACTIVATE_CMD` | — | Linux/Windows: command to focus editor |

### Per-project configuration

Create a `.agent-notify.env` file in your project root to override settings per repo:

```bash
# .agent-notify.env
CODEX_NOTIFY_SOUND=Funk
CODEX_NOTIFY_SAY=1
CODEX_NOTIFY_MIN_DURATION=30
```

Any `CODEX_NOTIFY_*` or `CODEX_SILENT` variable can be set. The file is sourced when the notification fires (the agent passes the project's `cwd` in the payload). The legacy `.codex-notify.env` filename is also supported.

## Notes
- Some macOS versions ignore `-appIcon` and use the sender app icon instead.
- Execute-only activation is the most reliable path on macOS; it may show the Terminal icon.
- If `terminal-notifier` is missing on macOS, the script falls back to `osascript`.
- Without `python3`, JSON payloads produce a clear error; manual title/message mode still works.
- **Stdout safety**: the script never writes to stdout during hook execution, so it's safe for Claude Code and Gemini CLI which parse hook stdout.

## FAQ
- **Why does the icon show Terminal?** Execute-only activation is the most reliable way to bring your editor to front on click, but macOS shows the Terminal icon for `terminal-notifier`. This is cosmetic only.
- **How do I change the activated app?** Set `CODEX_ACTIVATE_BUNDLE` to your editor's bundle ID (e.g. `com.microsoft.VSCodeInsiders`).
- **Does it work with the Codex macOS app?** Yes. If the Codex macOS app (`com.openai.codex`) is frontmost when the notification fires, clicking it will activate the Codex app instead of VS Code. This is automatic — no configuration needed.
- **Does it work over SSH?** Yes. Terminal bell (`CODEX_NOTIFY_BELL=auto`) fires automatically when no display server is detected. Many terminal emulators convert the bell to a native notification.
- **Can I use different settings per project?** Yes. Drop a `.agent-notify.env` file in any project root. See "Per-project configuration" above.

## Security
- All data stays local by default. Webhook support (`CODEX_NOTIFY_WEBHOOK`) is opt-in and sends notification title/message to the configured URL.
- Payload is read from stdin/args and used only to build notification text.
- Per-project `.agent-notify.env` only processes lines matching `CODEX_NOTIFY_*` or `CODEX_SILENT` for safety.

## Screenshot
![Agent Notify](./assets/screenshot.png)

## Troubleshooting
- **No notification**: check agent config files and OS notification permissions.
- **No sound**: check `CODEX_SILENT` and `CODEX_NOTIFY_SOUND` (path or system sound name).
- **macOS: click does not activate editor**: install `terminal-notifier` and verify `CODEX_ACTIVATE_BUNDLE`.
- **macOS: icon looks like Terminal**: this is expected with execute-only activation. Cosmetic only.
- **Linux: no notification**: install `libnotify-bin` (Debian/Ubuntu) or `libnotify` (Fedora).
- **Seeing a `terminal-notifier` usage banner**: make sure your `notify` hook points to `agent-notify` and set `CODEX_NOTIFY_DEBUG=1` to inspect args.
- **Clicking "Show" opens Script Editor**: set `CODEX_NOTIFY_EXEC_CMD="/usr/bin/open -b com.microsoft.VSCode"`.

## Changelog
- 1.0.0 - Cross-platform (macOS, Linux, Windows WSL). Multi-agent (Codex CLI, Claude Code, Gemini CLI). Terminal bell, long-run threshold, duration display, per-project config. Renamed from codex-notify to agent-notify.
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
- Remove hooks from your agent config files:
  - Codex CLI: remove `notify` line from `~/.codex/config.toml`
  - Claude Code: remove hooks from `~/.claude/settings.json`
  - Gemini CLI: remove hooks from `~/.gemini/settings.json`
- Delete the script: `rm ~/bin/agent-notify`
- Optional: `brew uninstall terminal-notifier`
