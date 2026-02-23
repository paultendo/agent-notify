#!/usr/bin/env python3
"""Completion guard — a Stop hook for Claude Code.

Inspired by blader/taskmaster. Prevents agents from stopping prematurely
by checking for a deterministic done signal and configurable completion criteria.

Install as a Claude Code Stop hook:
    {
        "hooks": {
            "Stop": [{
                "hooks": [{
                    "type": "command",
                    "command": "python3 /path/to/codex-notify/daemon/guard.py"
                }]
            }]
        }
    }

Or auto-install:  agent-notify guard install

Protocol:
    When an agent is truly finished, it should emit:
        AGENT_DONE::<session_id>
    in its final message. Without this signal, the guard may block the stop.

Counter-based escalation:
    - First stop attempt: always allow (warm-up)
    - Subsequent attempts without done signal: block and re-prompt
    - After AGENT_NOTIFY_GUARD_MAX attempts (default 3): allow anyway
    - Set AGENT_NOTIFY_GUARD_MAX=0 for unlimited blocking
"""

import json
import os
import sys
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import URLError

DONE_SIGNAL = "AGENT_DONE::"
COUNTER_DIR = Path("/tmp/agent-notify-guard")
DEFAULT_MAX = 3
DEFAULT_PORT = 7878


def _read_stdin() -> dict:
    """Read the hook input from stdin."""
    try:
        return json.loads(sys.stdin.read())
    except (json.JSONDecodeError, ValueError):
        return {}


def _get_counter(session_id: str) -> int:
    """Read the block counter for a session."""
    counter_file = COUNTER_DIR / session_id
    try:
        return int(counter_file.read_text().strip())
    except (FileNotFoundError, ValueError):
        return 0


def _set_counter(session_id: str, count: int) -> None:
    """Write the block counter for a session."""
    COUNTER_DIR.mkdir(parents=True, exist_ok=True)
    (COUNTER_DIR / session_id).write_text(str(count))


def _clear_counter(session_id: str) -> None:
    """Clear the counter (session completed)."""
    try:
        (COUNTER_DIR / session_id).unlink()
    except FileNotFoundError:
        pass


def _has_done_signal(text: str, session_id: str) -> bool:
    """Check if the done signal is present in the text."""
    if not text:
        return False
    # Accept both AGENT_DONE::<session_id> and bare AGENT_DONE::
    if f"{DONE_SIGNAL}{session_id}" in text:
        return True
    if DONE_SIGNAL in text:
        return True
    return False


def _is_subagent(data: dict) -> bool:
    """Detect if this is a subagent (short transcript = likely a sub-task)."""
    transcript_path = data.get("transcript_path", "")
    if not transcript_path:
        return False
    try:
        line_count = sum(1 for _ in open(transcript_path))
        return line_count < 20
    except (FileNotFoundError, PermissionError):
        return False


def _has_pending_tasks(session_id: str) -> tuple[bool, list[str]]:
    """Query the daemon for pending tasks assigned to this session.

    Returns (has_pending, task_titles).
    """
    port = int(os.environ.get("CODEX_NOTIFY_DAEMON_PORT", DEFAULT_PORT))
    try:
        req = Request(f"http://127.0.0.1:{port}/api/tasks?session_id={session_id}&status=pending")
        with urlopen(req, timeout=2) as resp:
            tasks = json.loads(resp.read().decode())
            if isinstance(tasks, list) and tasks:
                titles = [t.get("title", "untitled") for t in tasks[:5]]
                return True, titles
    except (URLError, OSError, json.JSONDecodeError, ValueError):
        pass
    return False, []


def _has_pending_global_tasks() -> tuple[bool, list[str]]:
    """Check for any unassigned pending tasks globally."""
    port = int(os.environ.get("CODEX_NOTIFY_DAEMON_PORT", DEFAULT_PORT))
    try:
        req = Request(f"http://127.0.0.1:{port}/api/tasks/next")
        with urlopen(req, timeout=2) as resp:
            result = json.loads(resp.read().decode())
            if isinstance(result, dict) and result.get("id"):
                return True, [result.get("title", "untitled")]
    except (URLError, OSError, json.JSONDecodeError, ValueError):
        pass
    return False, []


def _compliance_prompt(session_id: str, attempt: int, pending_tasks: list[str] | None = None) -> str:
    """Generate the compliance prompt that forces the agent to verify completion."""
    task_section = ""
    if pending_tasks:
        task_list = "\n".join(f"   - {t}" for t in pending_tasks)
        task_section = f"""
2. PENDING TASKS: The daemon reports these tasks are still pending:
{task_list}
   Complete them now or mark them done if already finished.
"""
    else:
        task_section = """
2. TASK LIST: Check your task list (if any). Are ALL tasks marked completed?
   If not, complete them now.
"""

    return f"""COMPLETION VERIFICATION REQUIRED (attempt {attempt})

Before you can stop, verify ALL of the following:

1. GOAL CHECK: Restate the user's original request. Is it FULLY achieved?
   Answer YES or NO.
{task_section}
3. ERROR CHECK: Were there any errors, failed tests, or broken builds?
   If yes, fix them now.

4. LOOSE ENDS: Are there any TODOs, placeholders, or "will implement later" items?
   If yes, address them now.

5. VERIFICATION: Did you actually run/test what you built?
   If not, do it now.

If everything is truly complete, include this signal in your response:
    {DONE_SIGNAL}{session_id}

If anything is NOT complete, continue working. Progress is not completion.
Do not stop until the user's goal is fully achieved."""


def main() -> None:
    data = _read_stdin()
    session_id = data.get("session_id", "unknown")
    last_message = data.get("last_assistant_message", "")
    stop_hook_active = data.get("stop_hook_active", False)
    event_name = data.get("hook_event_name", "")

    # Skip subagent sessions
    if _is_subagent(data):
        _log(f"[{session_id}] skipping subagent")
        sys.exit(0)

    # Check for done signal
    if _has_done_signal(last_message, session_id):
        _clear_counter(session_id)
        _log(f"[{session_id}] done signal found, allowing stop")
        sys.exit(0)

    # Check for pending tasks (plan-aware guard)
    has_tasks, task_titles = _has_pending_tasks(session_id)
    if not has_tasks:
        _, global_titles = _has_pending_global_tasks()
        if global_titles:
            has_tasks = True
            task_titles = global_titles

    # Get counter
    count = _get_counter(session_id)
    max_blocks = int(os.environ.get("AGENT_NOTIFY_GUARD_MAX", DEFAULT_MAX))

    # First stop is allowed (warm-up) UNLESS there are pending tasks
    if count == 0 and not stop_hook_active and not has_tasks:
        _set_counter(session_id, 1)
        _log(f"[{session_id}] first stop, allowing (warm-up)")
        sys.exit(0)

    # If pending tasks exist, always block (even on first stop)
    if has_tasks and count == 0:
        _set_counter(session_id, 1)
        _log(f"[{session_id}] blocking first stop — {len(task_titles)} pending tasks")
        prompt = _compliance_prompt(session_id, 1, pending_tasks=task_titles)
        result = {"decision": "block", "reason": prompt}
        print(json.dumps(result))
        sys.exit(0)

    # If already being re-prompted (stop_hook_active), this is a retry
    if stop_hook_active:
        count += 1
        _set_counter(session_id, count)

        # Check max blocks (but tasks override: never give up if tasks remain)
        if max_blocks > 0 and count >= max_blocks and not has_tasks:
            _clear_counter(session_id)
            _log(f"[{session_id}] max blocks ({max_blocks}) reached, allowing stop")
            sys.exit(0)

        _log(f"[{session_id}] blocking stop (attempt {count}/{max_blocks or 'unlimited'})")
        prompt = _compliance_prompt(session_id, count, pending_tasks=task_titles if has_tasks else None)

        result = {"decision": "block", "reason": prompt}
        print(json.dumps(result))
        sys.exit(0)

    # Not yet active, first real block
    _set_counter(session_id, count + 1)
    _log(f"[{session_id}] blocking stop (attempt {count + 1})")
    prompt = _compliance_prompt(session_id, count + 1, pending_tasks=task_titles if has_tasks else None)

    result = {"decision": "block", "reason": prompt}
    print(json.dumps(result))
    sys.exit(0)


def _log(msg: str) -> None:
    print(f"[agent-notify-guard] {msg}", file=sys.stderr, flush=True)


if __name__ == "__main__":
    main()
