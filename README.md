<div align="center">

# Agent Notify

**Desktop notifications for AI coding agents — never miss a completion, approval, or error again.**

[![shellcheck](https://github.com/paultendo/agent-notify/actions/workflows/shellcheck.yml/badge.svg)](https://github.com/paultendo/agent-notify/actions/workflows/shellcheck.yml)
[![release](https://img.shields.io/github/v/release/paultendo/agent-notify?style=flat-square)](https://github.com/paultendo/agent-notify/releases/latest)
[![license](https://img.shields.io/github/license/paultendo/agent-notify?style=flat-square)](LICENSE)
[![platform](https://img.shields.io/badge/platform-macOS%20%7C%20Linux%20%7C%20WSL-blue?style=flat-square)](#compatibility)
[![deps](https://img.shields.io/badge/dependencies-zero-brightgreen?style=flat-square)](#features)
[![agents](https://img.shields.io/badge/agents-Codex%20CLI%20%7C%20Claude%20Code%20%7C%20Gemini%20CLI-orange?style=flat-square)](#agents)

[Quick Start](#quick-start) &bull; [Features](#features) &bull; [Why agent-notify?](#why-agent-notify) &bull; [Compatibility](#compatibility) &bull; [Usage](#usage) &bull; [Configuration](#configuration) &bull; [FAQ](#faq)

</div>

![Agent Notify](./assets/screenshot.png)

## Quick Start

### Homebrew (macOS)

```bash
brew tap paultendo/agent-notify https://github.com/paultendo/agent-notify
brew install agent-notify
agent-notify --setup
```

### Manual install (macOS / Linux / Windows WSL)

```bash
chmod +x ./install-agent-notify.sh
./install-agent-notify.sh
agent-notify --setup           # configure all detected agents
```

<details>
<summary><strong>Platform recommendations & individual agent setup</strong></summary>

Configure agents individually:

```bash
agent-notify --setup-codex     # Codex CLI → ~/.codex/config.toml
agent-notify --setup-claude    # Claude Code → ~/.claude/settings.json
agent-notify --setup-gemini    # Gemini CLI → ~/.gemini/settings.json
```

Platform-specific packages:

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

</details>

> [!TIP]
> Restart your agent after setup and run a task to verify notifications are working.

> [!NOTE]
> **macOS click-to-focus** requires `terminal-notifier` (`brew install terminal-notifier`). For per-window focus (focusing the correct VS Code window, not just VS Code), grant accessibility access to **terminal-notifier.app** in System Settings → Privacy & Security → Accessibility.

## Features

### Core

- **Multi-agent** — Codex CLI, Claude Code, and Gemini CLI out of the box.
- **Cross-platform** — macOS, Linux, and Windows (WSL / Git Bash).
- **Zero dependencies** — pure Bash + Python 3 (already on your system).
- **One-command setup** — `agent-notify --setup` configures all detected agents.
- **Homebrew installable** — `brew install agent-notify`.
- **Self-update** — `agent-notify --update` pulls the latest release.

### Smart Notifications

- **Event categories** — completion, approval, question, error, and auth events with distinct sounds.
- **Git branch display** — shows current branch in notification subtitle.
- **Duration display** — shows how long the task took.
- **Long-run threshold** — only notify if the task exceeded N seconds (`CODEX_NOTIFY_MIN_DURATION`).
- Rich titles/messages extracted from agent JSON payloads.
- Clean, grouped notifications per session/thread.

### Terminal Integration

- **Click-to-focus** — auto-detects your terminal and focuses the right window on click. Supports 10 terminals: VS Code, iTerm2, Ghostty, Warp, kitty, WezTerm, Alacritty, Hyper, Terminal.app, and the Codex macOS app.
- **Multiplexer support** — tmux, zellij, kitty, and WezTerm pane/window focus on notification click.
- **Terminal bell** — automatic fallback for headless/SSH sessions.
- Terminal echo: prints a summary line to stderr for logging/visibility.
- **Stdout safety** — never writes to stdout during hook execution, safe for Claude Code and Gemini CLI.

### Webhooks & Remote

- **Slack** — rich attachments with color-coded event categories.
- **Discord** — embeds with color and emoji.
- **Telegram** — bot messages with chat ID.
- **ntfy** — priority-based push notifications.
- **Generic JSON** — works with any webhook endpoint.
- All free, all auto-detected from the URL.

### Power User

- **Do Not Disturb / Focus awareness** — skip notifications when Focus mode is active.
- **Schedule window** — only notify during configured hours.
- **Rate limiting** — throttle rapid-fire notifications.
- **Per-project config** — `.agent-notify.env` overrides per repo.
- **TTS (text-to-speech)** — via macOS `say`, Linux `espeak`/`spd-say`, or Windows SAPI.
- **Notification log** — append history to `~/.codex/notify.log`.
- **Custom hooks** — run any command on notification events.
- macOS: fallback to `osascript` if `terminal-notifier` is missing.
- Linux: fallback chain `notify-send` → `zenity` → terminal echo.
- Windows: PowerShell toast notifications via WSL/Git Bash.

## Why agent-notify?

| | **agent-notify** | heyagent | claude-code-notification | cfngc4594/codex-notify |
|---|---|---|---|---|
| **Agents supported** | Codex CLI, Claude Code, Gemini CLI | Claude Code only | Claude Code only | Codex CLI only |
| **Platforms** | macOS, Linux, WSL | macOS only | macOS, Linux | macOS, Linux |
| **Zero dependencies** | Yes | No (Node.js) | No (Node.js) | Yes |
| **Smart event categories** | 5 (completion, approval, question, error, auth) | — | — | — |
| **Terminal click-to-focus** | 10 terminals + 4 multiplexers | — | — | — |
| **Webhook integrations** | 5 services (all free) | — | — | — |
| **Per-project config** | Yes | — | — | — |
| **One-command setup** | `--setup` for all agents | Manual | Manual | Manual |
| **Self-update** | `--update` | npm | npm | — |

## Compatibility

### Agents

| Agent | Hook type | Config file | Events |
|-------|-----------|-------------|--------|
| **Codex CLI** | argv JSON | `~/.codex/config.toml` | `agent-turn-complete`, `approval-required` |
| **Claude Code** | stdin JSON | `~/.claude/settings.json` | `Stop`, `Notification` (permission, idle, auth) |
| **Gemini CLI** | stdin JSON | `~/.gemini/settings.json` | `AfterAgent`, `Notification` (tool permission) |

<details>
<summary><strong>Event categories</strong></summary>

| Category | Trigger | Sound | Examples |
|----------|---------|-------|----------|
| **completion** | Task finished | Glass / complete | `Stop`, `AfterAgent`, `agent-turn-complete` |
| **approval** | Permission needed | Sosumi / dialog-warning | `permission_prompt`, `ToolPermission` |
| **question** | User input needed | Sosumi / dialog-warning | `idle_prompt`, `elicitation_dialog` |
| **error** | Session/API error | Sosumi / dialog-warning | Session limit, 401, API overload |
| **auth** | Auth event | Glass / complete | `auth_success` |

</details>

<details>
<summary><strong>Platforms</strong></summary>

| Platform | Notification | Sound | TTS |
|----------|-------------|-------|-----|
| **macOS** | terminal-notifier / osascript | afplay | say |
| **Linux** | notify-send / zenity | paplay / aplay / ffplay | espeak / spd-say |
| **Windows** (WSL) | PowerShell toast | PowerShell SoundPlayer | PowerShell SAPI |

</details>

<details>
<summary><strong>Terminal click-to-focus (macOS)</strong></summary>

| Terminal | Detection | Focus method |
|----------|-----------|-------------|
| **VS Code** | `TERM_PROGRAM` / default | AppleScript window match |
| **iTerm2** | `TERM_PROGRAM` / `ITERM_SESSION_ID` | AppleScript window match |
| **Ghostty** | `GHOSTTY_RESOURCES_DIR` | AppleScript window match |
| **Warp** | `__CFBundleIdentifier` / `TERM_PROGRAM` | AppleScript window match |
| **kitty** | `KITTY_WINDOW_ID` + `KITTY_LISTEN_ON` | `kitty @ focus-window` / AppleScript fallback |
| **WezTerm** | `WEZTERM_PANE` | `wezterm cli activate-pane` / AppleScript fallback |
| **Alacritty** | `TERM_PROGRAM` | AppleScript window match |
| **Terminal.app** | `TERM_PROGRAM` | AppleScript window match |

</details>

<details>
<summary><strong>Multiplexer support (macOS)</strong></summary>

| Multiplexer | Detection | Click action |
|-------------|-----------|-------------|
| **tmux** | `$TMUX` | `tmux select-window + select-pane` (with socket path) |
| **zellij** | `$ZELLIJ` | `zellij action go-to-tab-name` (via layout dump) |
| **kitty** | `$KITTY_WINDOW_ID` | `kitty @ focus-window --match id:N` |
| **WezTerm** | `$WEZTERM_PANE` | `wezterm cli activate-pane --pane-id N` |

</details>

## Requirements

- `bash` 4.0+ (macOS, Linux, WSL, or Git Bash).
- `python3` for JSON payload parsing and agent setup.
- **macOS**: `terminal-notifier` required for click-to-focus (`brew install terminal-notifier`).
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

<details>
<summary><strong>Environment variables</strong></summary>

| Variable | Default | Description |
|----------|---------|-------------|
| `CODEX_NOTIFY_SOUND` | `Glass` / `complete` | Completion sound (path or system name) |
| `CODEX_NOTIFY_APPROVAL_SOUND` | `Sosumi` / `dialog-warning` | Approval sound |
| `CODEX_SILENT=1` | — | Disable all sounds |
| `CODEX_NOTIFY_QUIET=1` | — | Suppress terminal echo |
| `CODEX_ACTIVATE_BUNDLE` | auto-detected | macOS: app to activate on click |
| `CODEX_SENDER_BUNDLE` | `com.microsoft.VSCode` | macOS: sender icon for `-activate` mode |
| `CODEX_SUPPRESS_FRONTMOST=0` | `1` | Disable suppression when target app is frontmost |
| `CODEX_NOTIFY_EVENT_TYPES` | `*` | Codex event types to handle (comma-separated) |
| `CODEX_NOTIFY_EXEC_ONLY=0` | `1` | macOS: use `-activate` instead of `-execute` |
| `CODEX_NOTIFY_APP_ICON` | — | Custom icon path or URL |
| `CODEX_NOTIFY_SAY=1` | — | Enable text-to-speech |
| `CODEX_NOTIFY_SAY_VOICE` | system | TTS voice name |
| `CODEX_NOTIFY_SAY_RATE` | system | TTS speech rate (wpm, macOS only) |
| `CODEX_NOTIFY_WEBHOOK` | — | Webhook URL (auto-detects service) |
| `CODEX_NOTIFY_WEBHOOK_PRESET` | auto | Webhook format: `slack`, `discord`, `telegram`, `ntfy`, `generic` |
| `CODEX_NOTIFY_TELEGRAM_CHAT_ID` | — | Telegram chat ID (required for telegram preset) |
| `CODEX_NOTIFY_NTFY_TOPIC` | — | ntfy topic (can also be in URL) |
| `CODEX_NOTIFY_EXEC_CMD` | auto-detected | Override the click-execute command |
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
| `CODEX_NOTIFY_GIT_BRANCH` | `1` | Show git branch in notification subtitle |

</details>

### Webhook examples

```bash
# Slack — auto-detected from URL, sends rich attachment with color
export CODEX_NOTIFY_WEBHOOK="https://hooks.slack.com/services/T.../B.../xxx"

# Discord — auto-detected from URL, sends embed with color + emoji
export CODEX_NOTIFY_WEBHOOK="https://discord.com/api/webhooks/123/abc"

# Telegram — set chat ID, URL auto-detected
export CODEX_NOTIFY_WEBHOOK="https://api.telegram.org/bot<TOKEN>/sendMessage"
export CODEX_NOTIFY_TELEGRAM_CHAT_ID="-1001234567890"

# ntfy — topic extracted from URL, priority based on event category
export CODEX_NOTIFY_WEBHOOK="https://ntfy.sh/my-agent-notifications"

# Generic JSON — works with any webhook endpoint
export CODEX_NOTIFY_WEBHOOK="https://example.com/webhook"
```

### Per-project configuration

Create a `.agent-notify.env` file in your project root to override settings per repo:

```bash
# .agent-notify.env
CODEX_NOTIFY_SOUND=Funk
CODEX_NOTIFY_SAY=1
CODEX_NOTIFY_MIN_DURATION=30
```

Any `CODEX_NOTIFY_*` or `CODEX_SILENT` variable can be set. The file is sourced when the notification fires (the agent passes the project's `cwd` in the payload). The legacy `.codex-notify.env` filename is also supported.

## FAQ

- **How does terminal detection work?** Agent-notify reads `TERM_PROGRAM`, `__CFBundleIdentifier`, and multiplexer env vars (`TMUX`, `ZELLIJ`, `KITTY_WINDOW_ID`, `WEZTERM_PANE`) to auto-detect your terminal and build the right focus command. Override with `CODEX_ACTIVATE_BUNDLE`.
- **Does it work with tmux?** Yes. Clicking the notification will select the correct tmux window and pane. It uses the tmux socket path for reliable targeting across sessions.
- **Does it work with the Codex macOS app?** Yes. If the Codex macOS app (`com.openai.codex`) is frontmost when the notification fires, clicking it will activate the Codex app instead of VS Code. This is automatic — no configuration needed.
- **Does it work over SSH?** Yes. Terminal bell (`CODEX_NOTIFY_BELL=auto`) fires automatically when no display server is detected. Many terminal emulators convert the bell to a native notification.
- **Can I use different settings per project?** Yes. Drop a `.agent-notify.env` file in any project root. See [Per-project configuration](#per-project-configuration) above.
- **Which webhook services are supported?** Slack, Discord, Telegram, and ntfy have first-class formatters with rich messages, colors, and emoji. Any other URL receives a generic JSON payload. The service is auto-detected from the URL.

<details>
<summary><strong>Troubleshooting</strong></summary>

- **No notification**: check agent config files and OS notification permissions.
- **No sound**: check `CODEX_SILENT` and `CODEX_NOTIFY_SOUND` (path or system sound name).
- **macOS: click does not activate editor**: install `terminal-notifier` and verify `CODEX_ACTIVATE_BUNDLE`.
- **macOS: icon looks like Terminal**: this is expected with execute-only activation. Cosmetic only.
- **Linux: no notification**: install `libnotify-bin` (Debian/Ubuntu) or `libnotify` (Fedora).
- **Seeing a `terminal-notifier` usage banner**: make sure your `notify` hook points to `agent-notify` and set `CODEX_NOTIFY_DEBUG=1` to inspect args.
- **Clicking "Show" opens Script Editor**: set `CODEX_NOTIFY_EXEC_CMD="/usr/bin/open -b com.microsoft.VSCode"`.
- **Wrong terminal focused on click**: set `CODEX_ACTIVATE_BUNDLE` to your terminal's bundle ID, or check that `TERM_PROGRAM` is set correctly in your shell.

</details>

## Notes

- **Terminal auto-detection**: on macOS, agent-notify detects your terminal from `TERM_PROGRAM`, `__CFBundleIdentifier`, and multiplexer environment variables. It builds the right click-to-focus command automatically — no configuration needed.
- **tmux support**: when running inside tmux, clicking the notification focuses the correct tmux window and pane, using the socket path for reliable targeting.
- **Git branch**: shown in the notification subtitle by default. Disable with `CODEX_NOTIFY_GIT_BRANCH=0`.
- Some macOS versions ignore `-appIcon` and use the sender app icon instead.
- If `terminal-notifier` is missing on macOS, the script falls back to `osascript`.
- Without `python3`, JSON payloads produce a clear error; manual title/message mode still works.

> [!NOTE]
> The script never writes to stdout during hook execution, so it's safe for Claude Code and Gemini CLI which parse hook stdout.

## Security

- All data stays local by default. Webhook support (`CODEX_NOTIFY_WEBHOOK`) is opt-in and sends notification title/message to the configured URL.
- Payload is read from stdin/args and used only to build notification text.
- Per-project `.agent-notify.env` only processes lines matching `CODEX_NOTIFY_*` or `CODEX_SILENT` for safety.

<details>
<summary><strong>Changelog</strong></summary>

- **1.1.0** — Smart event categories (completion, approval, question, error, auth). Git branch display. Terminal auto-detection (iTerm2, Ghostty, Warp, kitty, WezTerm, Alacritty). Multiplexer support (tmux, zellij). Rich webhook formatters (Slack, Discord, Telegram, ntfy). Session limit and API error detection.
- **1.0.0** — Cross-platform (macOS, Linux, Windows WSL). Multi-agent (Codex CLI, Claude Code, Gemini CLI). Terminal bell, long-run threshold, duration display, per-project config. Renamed from codex-notify to agent-notify.
- **0.6.0** — DND/Focus awareness, schedule window, rate limiting, notification log, custom hooks, `--update`, Homebrew formula.
- **0.4.0** — TTS support (`say`), webhook notifications, `--test-say`.
- **0.3.0** — Differentiated completion/approval sounds, `--setup`, `--test-approval`, default to all event types.
- **0.2.0** — Terminal echo, `--version`/`--help`/`--test` flags, async sound, python3 guard.
- **0.1.x** — Initial releases, sound customization, screenshots.

</details>

## License

MIT. See `LICENSE`.

## Uninstall

- Remove hooks from your agent config files:
  - Codex CLI: remove `notify` line from `~/.codex/config.toml`
  - Claude Code: remove hooks from `~/.claude/settings.json`
  - Gemini CLI: remove hooks from `~/.gemini/settings.json`
- Delete the script: `rm ~/bin/agent-notify`
- Optional: `brew uninstall terminal-notifier`
