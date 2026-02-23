"""CLI subcommands for daemon, agent, and mesh management."""

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import URLError

from . import pid as pidmod

DEFAULT_PORT = 7878


def _port() -> int:
    return int(os.environ.get("CODEX_NOTIFY_DAEMON_PORT", DEFAULT_PORT))


def _base_url() -> str:
    return f"http://127.0.0.1:{_port()}"


def _api_get(path: str) -> dict | list | None:
    try:
        req = Request(f"{_base_url()}{path}")
        with urlopen(req, timeout=3) as resp:
            return json.loads(resp.read().decode())
    except (URLError, OSError, json.JSONDecodeError, ValueError):
        return None


def _api_post(path: str, body: dict | None = None) -> dict | list | None:
    try:
        data = json.dumps(body or {}).encode()
        req = Request(
            f"{_base_url()}{path}",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(req, timeout=5) as resp:
            return json.loads(resp.read().decode())
    except (URLError, OSError, json.JSONDecodeError, ValueError) as e:
        return {"error": str(e)}


def _api_delete(path: str) -> dict | None:
    try:
        req = Request(f"{_base_url()}{path}", method="DELETE")
        with urlopen(req, timeout=3) as resp:
            return json.loads(resp.read().decode())
    except (URLError, OSError, json.JSONDecodeError, ValueError):
        return None


def _require_daemon() -> None:
    if not pidmod.is_running():
        print("agent-notify daemon is not running", file=sys.stderr)
        print("Start it with: agent-notify daemon start", file=sys.stderr)
        sys.exit(1)


# --- Daemon commands ---

def cmd_daemon_start() -> None:
    if pidmod.is_running():
        pid = pidmod.read_pid()
        print(f"agent-notify daemon already running (PID {pid})")
        return

    daemon_dir = Path(__file__).resolve().parent.parent
    port = _port()

    cmd = [
        sys.executable, "-m", "daemon", "--serve", "--port", str(port),
    ]

    with open(os.devnull, "r") as devnull:
        proc = subprocess.Popen(
            cmd,
            cwd=str(daemon_dir),
            stdin=devnull,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )

    time.sleep(0.5)
    if proc.poll() is not None:
        print("agent-notify daemon failed to start", file=sys.stderr)
        sys.exit(1)

    print(f"agent-notify daemon started (PID {proc.pid}, port {port})")
    print(f"  dashboard: http://127.0.0.1:{port}")


def cmd_daemon_stop() -> None:
    if not pidmod.is_running():
        print("agent-notify daemon is not running")
        return

    pid = pidmod.read_pid()
    if pidmod.stop_daemon():
        print(f"agent-notify daemon stopped (PID {pid})")
    else:
        print("agent-notify daemon: failed to stop", file=sys.stderr)
        sys.exit(1)


def cmd_daemon_status() -> None:
    if not pidmod.is_running():
        print("agent-notify daemon is not running")
        return

    pid = pidmod.read_pid()
    health = _api_get("/api/health")
    if health:
        uptime = health.get("uptime", 0)
        mins = int(uptime // 60)
        secs = int(uptime % 60)
        print(f"agent-notify daemon running (PID {pid})")
        print(f"  version:     {health.get('version', '?')}")
        print(f"  uptime:      {mins}m {secs}s")
        print(f"  sse clients: {health.get('sse_clients', 0)}")
        print(f"  agents:      {health.get('agents_total', 0)} ({health.get('agents_active', 0)} active)")
        print(f"  port:        {_port()}")
        print(f"  dashboard:   http://127.0.0.1:{_port()}")
    else:
        print(f"agent-notify daemon running (PID {pid}) but not responding")


# --- Agent commands ---

def cmd_agents_list() -> None:
    _require_daemon()

    sessions = _api_get("/api/agents")
    if sessions is None:
        print("failed to connect to daemon", file=sys.stderr)
        sys.exit(1)

    if not sessions:
        print("no agent sessions")
        return

    header = f"{'SESSION ID':<20} {'AGENT':<10} {'STATUS':<10} {'LAST EVENT':<12} {'PROJECT':<30} {'EVENTS':>6}"
    print(header)
    print("-" * len(header))
    for s in sessions:
        sid = s.get("session_id", "")[:20]
        agent = s.get("agent_name", "")[:10]
        status = s.get("status", "")[:10]
        last_event = s.get("last_event", "")[:12]
        project = _shorten_path(s.get("project_cwd", ""))[:30]
        count = s.get("event_count", 0)
        print(f"{sid:<20} {agent:<10} {status:<10} {last_event:<12} {project:<30} {count:>6}")


def cmd_agents_status(session_id: str) -> None:
    _require_daemon()
    session = _api_get(f"/api/agents/{session_id}")
    if session is None:
        print("failed to connect to daemon", file=sys.stderr)
        sys.exit(1)
    if "error" in session:
        print(f"session not found: {session_id}", file=sys.stderr)
        sys.exit(1)
    print(json.dumps(session, indent=2))


def cmd_agents_approve(session_id: str) -> None:
    _require_daemon()
    result = _api_post(f"/api/agents/{session_id}/approve")
    if result and result.get("status") == "approved":
        print(f"approved: {session_id}")
    else:
        print(f"failed: {result}", file=sys.stderr)
        sys.exit(1)


def cmd_agents_reject(session_id: str) -> None:
    _require_daemon()
    result = _api_post(f"/api/agents/{session_id}/reject")
    if result and result.get("status") == "rejected":
        print(f"rejected: {session_id}")
    else:
        print(f"failed: {result}", file=sys.stderr)
        sys.exit(1)


def cmd_agents_send(session_id: str, text: str) -> None:
    _require_daemon()
    result = _api_post(f"/api/agents/{session_id}/send", {"text": text})
    if result and result.get("status") == "sent":
        print(f"sent to {session_id}")
    else:
        print(f"failed: {result}", file=sys.stderr)
        sys.exit(1)


def cmd_agents_interrupt(session_id: str) -> None:
    _require_daemon()
    result = _api_post(f"/api/agents/{session_id}/interrupt")
    if result and result.get("status") == "interrupted":
        print(f"interrupted: {session_id}")
    else:
        print(f"failed: {result}", file=sys.stderr)
        sys.exit(1)


def cmd_agents_spawn(agent: str = "claude", prompt: str = "", cwd: str = "") -> None:
    _require_daemon()
    body = {"agent": agent}
    if prompt:
        body["prompt"] = prompt
    if cwd:
        body["cwd"] = cwd
    result = _api_post("/api/agents/spawn", body)
    if result and result.get("status") == "spawned":
        sid = result.get("session_id", "")
        pane = result.get("pane_id", "")
        print(f"spawned {agent} agent")
        print(f"  session: {sid}")
        print(f"  pane:    {pane}")
    else:
        err = result.get("error", result) if result else "no response"
        print(f"failed to spawn: {err}", file=sys.stderr)
        sys.exit(1)


def cmd_agents_stop(session_id: str) -> None:
    _require_daemon()
    result = _api_post(f"/api/agents/{session_id}/stop")
    if result and result.get("status") == "stopped":
        warning = result.get("warning", "")
        print(f"stopped: {session_id}")
        if warning:
            print(f"  warning: {warning}")
    else:
        err = result.get("error", result) if result else "no response"
        print(f"failed: {err}", file=sys.stderr)
        sys.exit(1)


def cmd_agents_events(session_id: str) -> None:
    _require_daemon()
    events = _api_get(f"/api/agents/{session_id}/events")
    if events is None:
        print("failed to connect to daemon", file=sys.stderr)
        sys.exit(1)
    if isinstance(events, dict) and "error" in events:
        print(f"error: {events['error']}", file=sys.stderr)
        sys.exit(1)
    for e in events:
        t = e.get("created_at", "")[:19].replace("T", " ")
        cat = e.get("category", "")
        title = e.get("title", "")
        print(f"  {t}  [{cat:<10}]  {title}")


# --- Message commands ---

def cmd_messages_list() -> None:
    _require_daemon()
    messages = _api_get("/api/messages")
    if messages is None:
        print("failed to connect to daemon", file=sys.stderr)
        sys.exit(1)
    if not messages:
        print("no messages")
        return
    header = f"{'ID':>4} {'FROM':<16} {'TO':<16} {'TYPE':<10} {'STATUS':<10} {'CONTENT':<40}"
    print(header)
    print("-" * len(header))
    for m in messages:
        mid = m.get("id", 0)
        fr = m.get("from_session", "")[:16]
        to = m.get("to_session", "")[:16]
        mt = m.get("message_type", "")[:10]
        st = m.get("status", "")[:10]
        ct = m.get("content", "")[:40]
        print(f"{mid:>4} {fr:<16} {to:<16} {mt:<10} {st:<10} {ct:<40}")


def cmd_messages_send(from_session: str, to_session: str, content: str, msg_type: str = "handoff") -> None:
    _require_daemon()
    result = _api_post("/api/messages", {
        "from_session": from_session,
        "to_session": to_session,
        "content": content,
        "message_type": msg_type,
    })
    if result and "id" in result:
        action = result.get("action", "unknown")
        print(f"message {result['id']} created ({action})")
    else:
        print(f"failed: {result}", file=sys.stderr)
        sys.exit(1)


def cmd_messages_approve(message_id: str) -> None:
    _require_daemon()
    result = _api_post(f"/api/messages/{message_id}/approve")
    if result and result.get("action") == "delivered":
        print(f"message {message_id} approved and delivered")
    else:
        print(f"failed: {result}", file=sys.stderr)
        sys.exit(1)


def cmd_messages_reject(message_id: str) -> None:
    _require_daemon()
    result = _api_post(f"/api/messages/{message_id}/reject")
    if result and result.get("ok"):
        print(f"message {message_id} rejected")
    else:
        print(f"failed: {result}", file=sys.stderr)
        sys.exit(1)


# --- Rules commands ---

def cmd_rules_list() -> None:
    _require_daemon()
    rules = _api_get("/api/rules")
    if rules is None:
        print("failed to connect to daemon", file=sys.stderr)
        sys.exit(1)
    if not rules:
        print("no coordination rules (default: require approval for all)")
        return
    header = f"{'ID':>4} {'FROM':<12} {'TO':<12} {'EVENT TYPE':<12} {'ACTION':<10}"
    print(header)
    print("-" * len(header))
    for r in rules:
        print(f"{r.get('id',0):>4} {r.get('from_agent','*'):<12} {r.get('to_agent','*'):<12} {r.get('event_type','*'):<12} {r.get('action','approve'):<10}")


def cmd_rules_add(from_agent: str, to_agent: str, event_type: str, action: str) -> None:
    _require_daemon()
    if action not in ("auto", "approve", "block"):
        print(f"invalid action: {action} (use: auto, approve, block)", file=sys.stderr)
        sys.exit(1)
    result = _api_post("/api/rules", {
        "from_agent": from_agent,
        "to_agent": to_agent,
        "event_type": event_type,
        "action": action,
    })
    if result and "id" in result:
        print(f"rule {result['id']} created")
    else:
        print(f"failed: {result}", file=sys.stderr)
        sys.exit(1)


def cmd_rules_remove(rule_id: str) -> None:
    _require_daemon()
    result = _api_delete(f"/api/rules/{rule_id}")
    if result and result.get("status") == "deleted":
        print(f"rule {rule_id} deleted")
    else:
        print(f"failed: {result}", file=sys.stderr)
        sys.exit(1)


# --- Helpers ---

def _shorten_path(p: str) -> str:
    home = str(Path.home())
    if p.startswith(home):
        return "~" + p[len(home):]
    return p


def main() -> None:
    if len(sys.argv) < 2:
        _usage()
        sys.exit(1)

    group = sys.argv[1]
    sub = sys.argv[2] if len(sys.argv) > 2 else ""

    if group == "daemon":
        if sub == "start":
            cmd_daemon_start()
        elif sub == "stop":
            cmd_daemon_stop()
        elif sub == "status":
            cmd_daemon_status()
        else:
            print("Usage: agent-notify daemon <start|stop|status>", file=sys.stderr)
            sys.exit(1)

    elif group == "agents":
        sid = sys.argv[3] if len(sys.argv) > 3 else ""
        if sub == "list":
            cmd_agents_list()
        elif sub == "spawn":
            # agent-notify agents spawn [AGENT] [--prompt PROMPT] [--cwd DIR]
            agent = "claude"
            prompt = ""
            cwd = ""
            i = 3
            while i < len(sys.argv):
                if sys.argv[i] == "--prompt" and i + 1 < len(sys.argv):
                    prompt = sys.argv[i + 1]
                    i += 2
                elif sys.argv[i] == "--cwd" and i + 1 < len(sys.argv):
                    cwd = sys.argv[i + 1]
                    i += 2
                elif not sys.argv[i].startswith("--"):
                    agent = sys.argv[i]
                    i += 1
                else:
                    i += 1
            cmd_agents_spawn(agent, prompt, cwd)
        elif sub == "stop" and sid:
            cmd_agents_stop(sid)
        elif sub == "status" and sid:
            cmd_agents_status(sid)
        elif sub == "approve" and sid:
            cmd_agents_approve(sid)
        elif sub == "reject" and sid:
            cmd_agents_reject(sid)
        elif sub == "send" and sid and len(sys.argv) > 4:
            cmd_agents_send(sid, " ".join(sys.argv[4:]))
        elif sub == "interrupt" and sid:
            cmd_agents_interrupt(sid)
        elif sub == "events" and sid:
            cmd_agents_events(sid)
        else:
            print("Usage: agent-notify agents <list|spawn|stop|status|approve|reject|send|interrupt|events> [SESSION_ID] [args]", file=sys.stderr)
            sys.exit(1)

    elif group == "messages":
        if sub == "list":
            cmd_messages_list()
        elif sub == "send" and len(sys.argv) >= 6:
            msg_type = sys.argv[6] if len(sys.argv) > 6 else "handoff"
            cmd_messages_send(sys.argv[3], sys.argv[4], sys.argv[5], msg_type)
        elif sub == "approve" and len(sys.argv) > 3:
            cmd_messages_approve(sys.argv[3])
        elif sub == "reject" and len(sys.argv) > 3:
            cmd_messages_reject(sys.argv[3])
        else:
            print("Usage: agent-notify messages <list|send FROM TO CONTENT [TYPE]|approve ID|reject ID>", file=sys.stderr)
            sys.exit(1)

    elif group == "rules":
        if sub == "list":
            cmd_rules_list()
        elif sub == "add" and len(sys.argv) >= 7:
            cmd_rules_add(sys.argv[3], sys.argv[4], sys.argv[5], sys.argv[6])
        elif sub == "remove" and len(sys.argv) > 3:
            cmd_rules_remove(sys.argv[3])
        else:
            print("Usage: agent-notify rules <list|add FROM TO EVENT_TYPE ACTION|remove ID>", file=sys.stderr)
            sys.exit(1)

    elif group == "guard":
        if sub == "install":
            cmd_guard_install()
        elif sub == "status":
            cmd_guard_status()
        else:
            print("Usage: agent-notify guard <install|status>", file=sys.stderr)
            sys.exit(1)

    elif group == "mcp":
        if sub == "install":
            scope = "user"
            if len(sys.argv) > 3 and sys.argv[3] == "--scope" and len(sys.argv) > 4:
                scope = sys.argv[4]
            cmd_mcp_install(scope)
        elif sub == "serve":
            # Run the MCP server directly
            from .mcp import main as mcp_main
            mcp_main()
        else:
            print("Usage: agent-notify mcp <install [--scope user|project]|serve>", file=sys.stderr)
            sys.exit(1)

    else:
        print(f"Unknown command group: {group}", file=sys.stderr)
        _usage()
        sys.exit(1)


def cmd_guard_install() -> None:
    """Install the completion guard as a Claude Code Stop hook."""
    script_dir = Path(__file__).resolve().parent
    guard_path = str(script_dir / "guard.py")

    settings_path = Path.home() / ".claude" / "settings.json"
    settings = {}
    if settings_path.exists():
        try:
            settings = json.loads(settings_path.read_text())
        except (json.JSONDecodeError, ValueError):
            pass

    hooks = settings.setdefault("hooks", {})
    stop_hooks = hooks.setdefault("Stop", [])

    # Check if already installed
    guard_cmd = f"{sys.executable} {guard_path}"
    for group in stop_hooks:
        for h in group.get("hooks", []):
            if guard_path in h.get("command", ""):
                print("Completion guard already installed")
                return

    # Add the guard
    stop_hooks.append({
        "hooks": [{
            "type": "command",
            "command": guard_cmd,
        }],
    })

    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text(json.dumps(settings, indent=2) + "\n")
    print(f"Completion guard installed in {settings_path}")
    print(f"  command: {guard_cmd}")
    print()
    print("The guard will:")
    print("  - Allow the first stop (warm-up)")
    print("  - Block subsequent stops without AGENT_DONE:: signal")
    print(f"  - Give up after {3} attempts (set AGENT_NOTIFY_GUARD_MAX)")
    print()
    print("To uninstall, remove the Stop hook from ~/.claude/settings.json")


def cmd_guard_status() -> None:
    """Show completion guard status."""
    counter_dir = Path("/tmp/agent-notify-guard")
    if not counter_dir.exists():
        print("No active guard sessions")
        return

    files = list(counter_dir.iterdir())
    if not files:
        print("No active guard sessions")
        return

    print(f"{'SESSION ID':<40} {'BLOCK COUNT':>11}")
    print("-" * 53)
    for f in sorted(files):
        try:
            count = int(f.read_text().strip())
        except (ValueError, OSError):
            count = 0
        print(f"{f.name:<40} {count:>11}")


def cmd_mcp_install(scope: str = "user") -> None:
    """Register the MCP server with Claude Code, Codex, and Gemini."""
    script_dir = Path(__file__).resolve().parent
    mcp_path = str(script_dir / "mcp.py")

    # Claude Code
    claude = shutil.which("claude")
    if claude:
        import subprocess as sp
        try:
            sp.run(
                [claude, "mcp", "add", "--transport", "stdio", "--scope", scope,
                 "agent-notify", "--", sys.executable, mcp_path],
                check=True, capture_output=True, text=True,
            )
            print(f"Registered MCP server with Claude Code (scope: {scope})")
        except (sp.CalledProcessError, FileNotFoundError) as e:
            print(f"Claude Code MCP registration failed: {e}", file=sys.stderr)
    else:
        print("Claude Code not found (skipped)")

    # Generate .mcp.json for Codex and Gemini
    project_dir = script_dir.parent
    mcp_config = {
        "mcpServers": {
            "agent-notify": {
                "type": "stdio",
                "command": sys.executable,
                "args": [mcp_path],
            }
        }
    }
    mcp_json_path = project_dir / ".mcp.json"
    with open(mcp_json_path, "w") as f:
        json.dump(mcp_config, f, indent=2)
        f.write("\n")
    print(f"Created {mcp_json_path}")
    print(f"  MCP server: {mcp_path}")
    print(f"  Python: {sys.executable}")
    print()
    print("To use with Codex:  codex --mcp-config .mcp.json")
    print("To use with Gemini: gemini --mcp-config .mcp.json")


def _usage() -> None:
    print("Usage: agent-notify <daemon|agents|messages|rules|guard|mcp> <subcommand> [args]", file=sys.stderr)
    print("", file=sys.stderr)
    print("  daemon  start|stop|status", file=sys.stderr)
    print("  agents  list|spawn|stop|status|approve|reject|send|interrupt|events", file=sys.stderr)
    print("          spawn [AGENT] [--prompt TEXT] [--cwd DIR]", file=sys.stderr)
    print("  messages  list|send|approve|reject", file=sys.stderr)
    print("  rules   list|add|remove", file=sys.stderr)
    print("  guard   install|status", file=sys.stderr)
    print("  mcp     install [--scope user|project]|serve", file=sys.stderr)


if __name__ == "__main__":
    main()
