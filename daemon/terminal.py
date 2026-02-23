"""Keystroke injection and pane management for agent terminals.

Sends text to agent terminal panes via multiplexer CLIs.
Spawns new terminal panes and launches agent sessions.
This is the foundation for two-way control (Phase 2) and agent mesh (Phase 3).
The terminal is the API — we never talk to Anthropic/OpenAI/Google directly.
"""

import asyncio
import json
import os
import shutil


async def send_text(terminal: dict | str, text: str) -> dict:
    """Send text to an agent's terminal pane.

    Returns {"ok": True} on success, {"ok": False, "error": "..."} on failure.
    """
    if isinstance(terminal, str):
        try:
            terminal = json.loads(terminal)
        except (json.JSONDecodeError, TypeError):
            return {"ok": False, "error": "invalid terminal data"}

    if not terminal or not isinstance(terminal, dict):
        return {"ok": False, "error": "no terminal data"}

    mux = terminal.get("multiplexer", "")

    if mux == "tmux":
        return await _send_tmux(terminal, text)
    elif mux == "kitty":
        return await _send_kitty(terminal, text)
    elif mux == "wezterm":
        return await _send_wezterm(terminal, text)
    elif mux == "zellij":
        return await _send_zellij(terminal, text)
    else:
        return {"ok": False, "error": f"unsupported multiplexer: {mux or 'none'}"}


async def send_approve(terminal: dict | str) -> dict:
    """Send approval keystroke (y + Enter) to agent terminal."""
    return await send_text(terminal, "y\n")


async def send_reject(terminal: dict | str) -> dict:
    """Send rejection keystroke (n + Enter) to agent terminal."""
    return await send_text(terminal, "n\n")


async def send_interrupt(terminal: dict | str) -> dict:
    """Send Ctrl-C to agent terminal."""
    if isinstance(terminal, str):
        try:
            terminal = json.loads(terminal)
        except (json.JSONDecodeError, TypeError):
            return {"ok": False, "error": "invalid terminal data"}

    mux = terminal.get("multiplexer", "")

    if mux == "tmux":
        return await _send_tmux_keys(terminal, "C-c")
    elif mux == "kitty":
        return await _send_kitty(terminal, "\x03")
    elif mux == "wezterm":
        return await _send_wezterm(terminal, "\x03")
    elif mux == "zellij":
        return await _send_zellij_action(terminal, "write", "3")
    else:
        return {"ok": False, "error": f"unsupported multiplexer: {mux or 'none'}"}


async def _run(cmd: list[str]) -> dict:
    """Run a subprocess and return result."""
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=5)
        if proc.returncode == 0:
            return {"ok": True}
        err = stderr.decode().strip() or f"exit code {proc.returncode}"
        return {"ok": False, "error": err}
    except FileNotFoundError:
        return {"ok": False, "error": f"command not found: {cmd[0]}"}
    except asyncio.TimeoutError:
        return {"ok": False, "error": "command timed out"}


# --- tmux ---

async def _send_tmux(terminal: dict, text: str) -> dict:
    socket = terminal.get("tmux_socket", "")
    pane = terminal.get("tmux_pane", "")
    if not pane:
        return {"ok": False, "error": "no tmux pane"}

    tmux = shutil.which("tmux")
    if not tmux:
        return {"ok": False, "error": "tmux not found"}

    # Use send-keys with literal flag for exact text
    cmd = [tmux]
    if socket:
        cmd.extend(["-S", socket])
    cmd.extend(["send-keys", "-t", pane, "-l", text])
    return await _run(cmd)


async def _send_tmux_keys(terminal: dict, keys: str) -> dict:
    socket = terminal.get("tmux_socket", "")
    pane = terminal.get("tmux_pane", "")
    if not pane:
        return {"ok": False, "error": "no tmux pane"}

    tmux = shutil.which("tmux")
    if not tmux:
        return {"ok": False, "error": "tmux not found"}

    cmd = [tmux]
    if socket:
        cmd.extend(["-S", socket])
    cmd.extend(["send-keys", "-t", pane, keys])
    return await _run(cmd)


# --- kitty ---

async def _send_kitty(terminal: dict, text: str) -> dict:
    window_id = terminal.get("kitty_window_id", "")
    socket = terminal.get("kitty_socket", "")
    if not window_id:
        return {"ok": False, "error": "no kitty window id"}

    kitty = shutil.which("kitty")
    if not kitty:
        return {"ok": False, "error": "kitty not found"}

    cmd = [kitty, "@"]
    if socket:
        cmd.extend(["--to", socket])
    cmd.extend(["send-text", "--match", f"id:{window_id}", text])
    return await _run(cmd)


# --- wezterm ---

async def _send_wezterm(terminal: dict, text: str) -> dict:
    pane_id = terminal.get("wezterm_pane", "")
    if not pane_id:
        return {"ok": False, "error": "no wezterm pane"}

    wezterm = shutil.which("wezterm")
    if not wezterm:
        return {"ok": False, "error": "wezterm not found"}

    cmd = [wezterm, "cli", "send-text", "--pane-id", pane_id, "--no-paste", text]
    return await _run(cmd)


# --- zellij ---

async def _send_zellij(terminal: dict, text: str) -> dict:
    session = terminal.get("zellij_session", "")
    if not session:
        return {"ok": False, "error": "no zellij session"}

    zellij = shutil.which("zellij")
    if not zellij:
        return {"ok": False, "error": "zellij not found"}

    cmd = [zellij, "-s", session, "action", "write-chars", text]
    return await _run(cmd)


async def _send_zellij_action(terminal: dict, action: str, *args: str) -> dict:
    session = terminal.get("zellij_session", "")
    if not session:
        return {"ok": False, "error": "no zellij session"}

    zellij = shutil.which("zellij")
    if not zellij:
        return {"ok": False, "error": "zellij not found"}

    cmd = [zellij, "-s", session, "action", action, *args]
    return await _run(cmd)


# ---------------------------------------------------------------------------
# Pane spawning — launch new agent sessions in terminal panes
# ---------------------------------------------------------------------------

# Known agent commands and their binary names
_AGENT_COMMANDS = {
    "claude": "claude",
    "codex": "codex",
    "gemini": "gemini",
}


def _detect_multiplexer() -> dict:
    """Detect the current multiplexer from environment variables."""
    if os.environ.get("TMUX"):
        parts = os.environ["TMUX"].split(",")
        return {
            "multiplexer": "tmux",
            "tmux_socket": parts[0] if parts else "",
        }
    if os.environ.get("ZELLIJ_SESSION_NAME"):
        return {
            "multiplexer": "zellij",
            "zellij_session": os.environ["ZELLIJ_SESSION_NAME"],
        }
    if os.environ.get("KITTY_WINDOW_ID"):
        return {
            "multiplexer": "kitty",
            "kitty_socket": os.environ.get("KITTY_LISTEN_ON", ""),
        }
    if os.environ.get("WEZTERM_PANE"):
        return {
            "multiplexer": "wezterm",
            "wezterm_socket": os.environ.get("WEZTERM_UNIX_SOCKET", ""),
        }
    return {}


def _build_agent_command(agent: str, prompt: str, cwd: str) -> str:
    """Build the shell command to launch an agent session."""
    binary = _AGENT_COMMANDS.get(agent, agent)

    # Build command with optional prompt and working directory
    parts = []
    if cwd:
        parts.append(f"cd {_shell_quote(cwd)} &&")

    parts.append(binary)

    if prompt and agent == "claude":
        parts.extend(["--print", "--prompt", _shell_quote(prompt)])
    elif prompt and agent == "codex":
        parts.extend(["--prompt", _shell_quote(prompt)])
    elif prompt:
        # Generic: just echo the prompt as instruction
        parts.extend(["--prompt", _shell_quote(prompt)])

    return " ".join(parts)


def _shell_quote(s: str) -> str:
    """Quote a string for shell use."""
    return "'" + s.replace("'", "'\\''") + "'"


async def spawn_pane(
    agent: str = "claude",
    prompt: str = "",
    cwd: str = "",
    multiplexer: dict | None = None,
) -> dict:
    """Spawn a new terminal pane and launch an agent session in it.

    Args:
        agent: Agent command name (claude, codex, gemini)
        prompt: Optional prompt/task to start with
        cwd: Working directory for the new session
        multiplexer: Override multiplexer detection (for testing or remote)

    Returns:
        {"ok": True, "terminal": {...}, "pane_id": "..."} or
        {"ok": False, "error": "..."}
    """
    mux = multiplexer or _detect_multiplexer()
    if not mux:
        return {"ok": False, "error": "no multiplexer detected (need tmux, kitty, wezterm, or zellij)"}

    shell_cmd = _build_agent_command(agent, prompt, cwd)
    mux_type = mux.get("multiplexer", "")

    if mux_type == "tmux":
        return await _spawn_tmux(mux, shell_cmd, cwd)
    elif mux_type == "kitty":
        return await _spawn_kitty(mux, shell_cmd, cwd)
    elif mux_type == "wezterm":
        return await _spawn_wezterm(mux, shell_cmd, cwd)
    elif mux_type == "zellij":
        return await _spawn_zellij(mux, shell_cmd, cwd)
    else:
        return {"ok": False, "error": f"unsupported multiplexer: {mux_type}"}


async def stop_session(terminal: dict | str) -> dict:
    """Gracefully stop an agent session.

    Sends Ctrl-C, waits briefly, then sends 'exit' + Enter.
    """
    result = await send_interrupt(terminal)
    if not result.get("ok"):
        return result

    # Brief pause for the agent to handle the interrupt
    await asyncio.sleep(0.5)

    # Send exit command
    return await send_text(terminal, "exit\n")


async def _run_capture(cmd: list[str]) -> dict:
    """Run a subprocess and capture stdout."""
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=5)
        if proc.returncode == 0:
            return {"ok": True, "stdout": stdout.decode().strip()}
        err = stderr.decode().strip() or f"exit code {proc.returncode}"
        return {"ok": False, "error": err}
    except FileNotFoundError:
        return {"ok": False, "error": f"command not found: {cmd[0]}"}
    except asyncio.TimeoutError:
        return {"ok": False, "error": "command timed out"}


async def _spawn_tmux(mux: dict, shell_cmd: str, cwd: str) -> dict:
    """Spawn a new tmux pane with the given command."""
    tmux = shutil.which("tmux")
    if not tmux:
        return {"ok": False, "error": "tmux not found"}

    socket = mux.get("tmux_socket", "")
    cmd = [tmux]
    if socket:
        cmd.extend(["-S", socket])
    cmd.extend(["split-window", "-h"])
    if cwd:
        cmd.extend(["-c", cwd])
    cmd.append(shell_cmd)
    # -P prints pane info, -F gives us the pane ID
    cmd.extend(["-P", "-F", "#{pane_id}"])

    result = await _run_capture(cmd)
    if not result.get("ok"):
        return result

    pane_id = result["stdout"].strip()
    terminal = {
        "multiplexer": "tmux",
        "tmux_socket": socket,
        "tmux_pane": pane_id,
    }
    return {"ok": True, "terminal": terminal, "pane_id": pane_id}


async def _spawn_kitty(mux: dict, shell_cmd: str, cwd: str) -> dict:
    """Spawn a new kitty window with the given command."""
    kitty = shutil.which("kitty")
    if not kitty:
        return {"ok": False, "error": "kitty not found"}

    socket = mux.get("kitty_socket", "")
    cmd = [kitty, "@"]
    if socket:
        cmd.extend(["--to", socket])
    cmd.extend(["launch", "--type=window", "--keep-focus"])
    if cwd:
        cmd.extend(["--cwd", cwd])
    cmd.extend(["sh", "-c", shell_cmd])

    result = await _run_capture(cmd)
    if not result.get("ok"):
        return result

    window_id = result["stdout"].strip()
    terminal = {
        "multiplexer": "kitty",
        "kitty_window_id": window_id,
        "kitty_socket": socket,
    }
    return {"ok": True, "terminal": terminal, "pane_id": window_id}


async def _spawn_wezterm(mux: dict, shell_cmd: str, cwd: str) -> dict:
    """Spawn a new wezterm pane with the given command."""
    wezterm = shutil.which("wezterm")
    if not wezterm:
        return {"ok": False, "error": "wezterm not found"}

    cmd = [wezterm, "cli", "split-pane", "--right"]
    if cwd:
        cmd.extend(["--cwd", cwd])
    cmd.extend(["--", "sh", "-c", shell_cmd])

    result = await _run_capture(cmd)
    if not result.get("ok"):
        return result

    pane_id = result["stdout"].strip()
    terminal = {
        "multiplexer": "wezterm",
        "wezterm_pane": pane_id,
        "wezterm_socket": mux.get("wezterm_socket", ""),
    }
    return {"ok": True, "terminal": terminal, "pane_id": pane_id}


async def _spawn_zellij(mux: dict, shell_cmd: str, cwd: str) -> dict:
    """Spawn a new zellij pane with the given command."""
    zellij = shutil.which("zellij")
    if not zellij:
        return {"ok": False, "error": "zellij not found"}

    session = mux.get("zellij_session", "")
    cmd = [zellij]
    if session:
        cmd.extend(["-s", session])
    cmd.extend(["action", "new-pane", "--direction", "right"])
    if cwd:
        cmd.extend(["--cwd", cwd])
    cmd.extend(["--", "sh", "-c", shell_cmd])

    result = await _run(cmd)
    if not result.get("ok"):
        return result

    terminal = {
        "multiplexer": "zellij",
        "zellij_session": session,
    }
    return {"ok": True, "terminal": terminal, "pane_id": session}
