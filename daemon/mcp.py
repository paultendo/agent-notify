"""MCP (Model Context Protocol) stdio server for agent-notify.

Exposes the daemon's capabilities as MCP tools that AI agents can call
natively. Works with Claude Code, Codex CLI, and Gemini CLI.

Usage:
    claude mcp add agent-notify -- python3 /path/to/codex-notify/daemon/mcp.py
    codex --mcp-config .mcp.json
    gemini --mcp-config .mcp.json

Wire format: newline-delimited JSON-RPC 2.0 over stdio.
Zero dependencies — Python stdlib only.
"""

import json
import os
import sys
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import URLError

SERVER_NAME = "agent-notify"
SERVER_VERSION = "0.1.0"
PROTOCOL_VERSION = "2025-11-25"

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


# ---------------------------------------------------------------------------
# Tool definitions
# ---------------------------------------------------------------------------

TOOLS = [
    {
        "name": "notify_list_agents",
        "description": (
            "List all tracked AI agent sessions. Returns session ID, agent name, "
            "status (active/idle/waiting/error/ended), project directory, event count, "
            "and parent/child relationships. Use this to see what other agents are doing."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "description": "Filter by status: active, idle, waiting, error, ended",
                    "enum": ["active", "idle", "waiting", "error", "ended"],
                },
            },
            "additionalProperties": False,
        },
        "annotations": {"readOnlyHint": True},
    },
    {
        "name": "notify_get_agent",
        "description": (
            "Get detailed information about a specific agent session, including "
            "terminal info, event history, heartbeat status, and parent/child relationships."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "session_id": {
                    "type": "string",
                    "description": "The session ID to look up",
                },
            },
            "required": ["session_id"],
            "additionalProperties": False,
        },
        "annotations": {"readOnlyHint": True},
    },
    {
        "name": "notify_agent_events",
        "description": (
            "Get the recent event history for a specific agent session. "
            "Shows what the agent has been doing — completions, approvals, errors, etc."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "session_id": {
                    "type": "string",
                    "description": "The session ID",
                },
                "limit": {
                    "type": "integer",
                    "description": "Max events to return (default 20)",
                    "default": 20,
                },
            },
            "required": ["session_id"],
            "additionalProperties": False,
        },
        "annotations": {"readOnlyHint": True},
    },
    {
        "name": "notify_spawn_agent",
        "description": (
            "Spawn a new AI agent in a new terminal pane. Creates a tmux/kitty/wezterm/zellij "
            "split and launches the agent with an optional prompt and working directory. "
            "Use this to delegate subtasks to sibling agents."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "agent": {
                    "type": "string",
                    "description": "Agent to spawn: claude, codex, or gemini",
                    "enum": ["claude", "codex", "gemini"],
                    "default": "claude",
                },
                "prompt": {
                    "type": "string",
                    "description": "Task prompt for the new agent",
                },
                "cwd": {
                    "type": "string",
                    "description": "Working directory for the new agent session",
                },
            },
            "additionalProperties": False,
        },
        "annotations": {"destructiveHint": False, "idempotentHint": False},
    },
    {
        "name": "notify_stop_agent",
        "description": (
            "Gracefully stop an agent session. Sends Ctrl-C then 'exit' to the "
            "agent's terminal pane and marks the session as ended."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "session_id": {
                    "type": "string",
                    "description": "The session ID to stop",
                },
            },
            "required": ["session_id"],
            "additionalProperties": False,
        },
        "annotations": {"destructiveHint": True},
    },
    {
        "name": "notify_send_message",
        "description": (
            "Send a message to another agent session. The message is routed through "
            "the agent mesh — depending on coordination rules, it may be auto-delivered, "
            "held for approval, or blocked. Messages are typed into the target agent's "
            "terminal pane."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "from_session": {
                    "type": "string",
                    "description": "Your session ID (the sender)",
                },
                "to_session": {
                    "type": "string",
                    "description": "Target agent's session ID",
                },
                "content": {
                    "type": "string",
                    "description": "Message content to send",
                },
                "message_type": {
                    "type": "string",
                    "description": "Message type: handoff, question, status, instruction",
                    "enum": ["handoff", "question", "status", "instruction"],
                    "default": "handoff",
                },
            },
            "required": ["from_session", "to_session", "content"],
            "additionalProperties": False,
        },
    },
    {
        "name": "notify_send_text",
        "description": (
            "Type text directly into another agent's terminal. Use this for "
            "fine-grained control — answering prompts, providing input, etc."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "session_id": {
                    "type": "string",
                    "description": "Target agent's session ID",
                },
                "text": {
                    "type": "string",
                    "description": "Text to type into the terminal",
                },
            },
            "required": ["session_id", "text"],
            "additionalProperties": False,
        },
    },
    {
        "name": "notify_approve_agent",
        "description": (
            "Send an approval keystroke (y + Enter) to an agent that is waiting "
            "for permission. Equivalent to clicking 'Allow' on a permission prompt."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "session_id": {
                    "type": "string",
                    "description": "The session ID of the waiting agent",
                },
            },
            "required": ["session_id"],
            "additionalProperties": False,
        },
    },
    {
        "name": "notify_reject_agent",
        "description": (
            "Send a rejection keystroke (n + Enter) to an agent that is waiting "
            "for permission. Equivalent to clicking 'Deny' on a permission prompt."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "session_id": {
                    "type": "string",
                    "description": "The session ID of the waiting agent",
                },
            },
            "required": ["session_id"],
            "additionalProperties": False,
        },
    },
    {
        "name": "notify_list_events",
        "description": (
            "List recent events across all agents. Filterable by agent name, "
            "category, and project. Shows the global activity feed."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "agent": {
                    "type": "string",
                    "description": "Filter by agent name (e.g. 'Claude')",
                },
                "category": {
                    "type": "string",
                    "description": "Filter by category: start, stop, completion, approval, question, error, auth",
                },
                "project": {
                    "type": "string",
                    "description": "Filter by project path (substring match)",
                },
                "limit": {
                    "type": "integer",
                    "description": "Max events to return (default 30)",
                    "default": 30,
                },
            },
            "additionalProperties": False,
        },
        "annotations": {"readOnlyHint": True},
    },
    {
        "name": "notify_health",
        "description": (
            "Check the agent-notify daemon health. Returns uptime, version, "
            "number of connected SSE clients, and agent counts."
        ),
        "inputSchema": {
            "type": "object",
            "additionalProperties": False,
        },
        "annotations": {"readOnlyHint": True},
    },
    {
        "name": "notify_list_messages",
        "description": (
            "List agent-to-agent messages in the mesh. Filterable by status "
            "(pending, delivered, rejected)."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "description": "Filter by message status",
                    "enum": ["pending", "delivered", "rejected"],
                },
                "limit": {
                    "type": "integer",
                    "description": "Max messages to return (default 30)",
                    "default": 30,
                },
            },
            "additionalProperties": False,
        },
        "annotations": {"readOnlyHint": True},
    },
    {
        "name": "notify_list_tasks",
        "description": (
            "List tasks tracked by the daemon. Tasks have dependencies — "
            "a task is only actionable when all its dependencies are done. "
            "Filterable by session and status."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "session_id": {
                    "type": "string",
                    "description": "Filter by session ID",
                },
                "status": {
                    "type": "string",
                    "description": "Filter by status: pending, in_progress, done, blocked",
                    "enum": ["pending", "in_progress", "done", "blocked"],
                },
            },
            "additionalProperties": False,
        },
        "annotations": {"readOnlyHint": True},
    },
    {
        "name": "notify_create_task",
        "description": (
            "Create a new task. Tasks can have dependencies on other task IDs — "
            "the task won't be actionable until all dependencies are done. "
            "Use this to break down work and coordinate between agents."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Task title",
                },
                "description": {
                    "type": "string",
                    "description": "Detailed task description",
                },
                "session_id": {
                    "type": "string",
                    "description": "Assign to a specific agent session",
                },
                "priority": {
                    "type": "string",
                    "description": "Priority level",
                    "enum": ["high", "medium", "low"],
                    "default": "medium",
                },
                "dependencies": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "description": "List of task IDs that must be done first",
                },
            },
            "required": ["title"],
            "additionalProperties": False,
        },
    },
    {
        "name": "notify_update_task",
        "description": (
            "Update a task's status, title, description, priority, or dependencies. "
            "Use this to mark tasks as in_progress or done."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "task_id": {
                    "type": "integer",
                    "description": "Task ID to update",
                },
                "status": {
                    "type": "string",
                    "description": "New status",
                    "enum": ["pending", "in_progress", "done", "blocked"],
                },
                "title": {"type": "string"},
                "description": {"type": "string"},
                "priority": {
                    "type": "string",
                    "enum": ["high", "medium", "low"],
                },
                "session_id": {
                    "type": "string",
                    "description": "Reassign to a different session",
                },
                "dependencies": {
                    "type": "array",
                    "items": {"type": "integer"},
                },
            },
            "required": ["task_id"],
            "additionalProperties": False,
        },
    },
    {
        "name": "notify_next_task",
        "description": (
            "Find the next actionable task — pending with all dependencies resolved. "
            "Returns the highest-priority task that's ready to work on. "
            "Optionally filter by session."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "session_id": {
                    "type": "string",
                    "description": "Only look at tasks assigned to this session",
                },
            },
            "additionalProperties": False,
        },
        "annotations": {"readOnlyHint": True},
    },
    {
        "name": "notify_set_context",
        "description": (
            "Set a shared context variable visible to all agents. Use this to share "
            "state across agent sessions — status flags, configuration, intermediate "
            "results, etc. Variables can be scoped globally or per-project."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "key": {
                    "type": "string",
                    "description": "Variable name (e.g. 'build_status', 'api_base_url')",
                },
                "value": {
                    "type": "string",
                    "description": "Variable value (serialized as string)",
                },
                "scope": {
                    "type": "string",
                    "description": "Scope: 'global' (all agents) or a project path for project-specific vars",
                    "default": "global",
                },
                "updated_by": {
                    "type": "string",
                    "description": "Your session ID or agent name (for audit trail)",
                },
            },
            "required": ["key", "value"],
            "additionalProperties": False,
        },
    },
    {
        "name": "notify_get_context",
        "description": (
            "Get a shared context variable. Returns the value, who last set it, "
            "and when. Use this to read state set by other agents."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "key": {
                    "type": "string",
                    "description": "Variable name to look up",
                },
                "scope": {
                    "type": "string",
                    "description": "Scope to search (default: 'global')",
                    "default": "global",
                },
            },
            "required": ["key"],
            "additionalProperties": False,
        },
        "annotations": {"readOnlyHint": True},
    },
    {
        "name": "notify_list_context",
        "description": (
            "List all shared context variables. Optionally filter by scope. "
            "Returns all keys, values, scopes, and who last updated each."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "scope": {
                    "type": "string",
                    "description": "Filter by scope (e.g. 'global' or a project path)",
                },
            },
            "additionalProperties": False,
        },
        "annotations": {"readOnlyHint": True},
    },
    {
        "name": "notify_delete_context",
        "description": "Delete a shared context variable.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "key": {
                    "type": "string",
                    "description": "Variable name to delete",
                },
                "scope": {
                    "type": "string",
                    "description": "Scope (default: 'global')",
                    "default": "global",
                },
            },
            "required": ["key"],
            "additionalProperties": False,
        },
    },
    {
        "name": "notify_add_route",
        "description": (
            "Add an after-work routing rule. When an agent completes or stops, "
            "the daemon can automatically trigger follow-up actions. Routing options:\n"
            "- next_task: Auto-assign next pending task from the DAG\n"
            "- handoff: Forward work to another session (template = target session_id)\n"
            "- spawn: Launch a new agent (template = JSON: {agent, prompt, cwd})\n"
            "- notify: Broadcast an SSE event (template = custom message)\n"
            "- pipeline: Run a sequence of actions (template = JSON array of {action, template})"
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "from_agent": {
                    "type": "string",
                    "description": "Agent name to match (or '*' for any)",
                    "default": "*",
                },
                "event_type": {
                    "type": "string",
                    "description": "Event type to trigger on",
                    "enum": ["completion", "stop", "*"],
                    "default": "completion",
                },
                "action": {
                    "type": "string",
                    "description": "Routing action to take",
                    "enum": ["next_task", "handoff", "spawn", "notify", "pipeline"],
                },
                "template": {
                    "type": "string",
                    "description": "Action-specific template (see action descriptions)",
                },
                "priority": {
                    "type": "integer",
                    "description": "Higher priority rules match first (default 0)",
                    "default": 0,
                },
            },
            "required": ["action"],
            "additionalProperties": False,
        },
    },
    {
        "name": "notify_list_rules",
        "description": (
            "List all coordination and routing rules. Shows message routing rules "
            "(approve, auto, block) and after-work routing rules (next_task, handoff, "
            "spawn, notify, pipeline)."
        ),
        "inputSchema": {
            "type": "object",
            "additionalProperties": False,
        },
        "annotations": {"readOnlyHint": True},
    },
    {
        "name": "notify_delete_rule",
        "description": "Delete a coordination or routing rule by ID.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "rule_id": {
                    "type": "integer",
                    "description": "Rule ID to delete",
                },
            },
            "required": ["rule_id"],
            "additionalProperties": False,
        },
    },
    {
        "name": "notify_set_preference",
        "description": (
            "Set a daemon preference (key-value pair). Preferences control "
            "notification behavior, thresholds, etc."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "key": {
                    "type": "string",
                    "description": "Preference key",
                },
                "value": {
                    "type": "string",
                    "description": "Preference value",
                },
            },
            "required": ["key", "value"],
            "additionalProperties": False,
        },
    },
]


# ---------------------------------------------------------------------------
# Tool handlers
# ---------------------------------------------------------------------------

def _handle_tool(name: str, args: dict) -> dict:
    """Dispatch a tool call. Returns {"content": [...], "isError": bool}."""
    try:
        result = _dispatch(name, args)
        text = json.dumps(result, indent=2) if isinstance(result, (dict, list)) else str(result)
        return {"content": [{"type": "text", "text": text}], "isError": False}
    except Exception as e:
        return {"content": [{"type": "text", "text": f"Error: {e}"}], "isError": True}


def _dispatch(name: str, args: dict):
    if name == "notify_list_agents":
        params = []
        if args.get("status"):
            params.append(f"status={args['status']}")
        query = "?" + "&".join(params) if params else ""
        result = _api_get(f"/api/agents{query}")
        if result is None:
            raise ConnectionError("daemon not running or not responding")
        return result

    if name == "notify_get_agent":
        result = _api_get(f"/api/agents/{args['session_id']}")
        if result is None:
            raise ConnectionError("daemon not running or not responding")
        return result

    if name == "notify_agent_events":
        limit = args.get("limit", 20)
        result = _api_get(f"/api/agents/{args['session_id']}/events?limit={limit}")
        if result is None:
            raise ConnectionError("daemon not running or not responding")
        return result

    if name == "notify_spawn_agent":
        body = {"agent": args.get("agent", "claude")}
        if args.get("prompt"):
            body["prompt"] = args["prompt"]
        if args.get("cwd"):
            body["cwd"] = args["cwd"]
        result = _api_post("/api/agents/spawn", body)
        if result and result.get("error"):
            raise RuntimeError(result["error"])
        return result

    if name == "notify_stop_agent":
        result = _api_post(f"/api/agents/{args['session_id']}/stop")
        if result and result.get("error"):
            raise RuntimeError(result["error"])
        return result

    if name == "notify_send_message":
        body = {
            "from_session": args["from_session"],
            "to_session": args["to_session"],
            "content": args["content"],
            "message_type": args.get("message_type", "handoff"),
        }
        result = _api_post("/api/messages", body)
        if result and result.get("error"):
            raise RuntimeError(result["error"])
        return result

    if name == "notify_send_text":
        result = _api_post(
            f"/api/agents/{args['session_id']}/send",
            {"text": args["text"]},
        )
        if result and result.get("error"):
            raise RuntimeError(result["error"])
        return result

    if name == "notify_approve_agent":
        result = _api_post(f"/api/agents/{args['session_id']}/approve")
        if result and result.get("error"):
            raise RuntimeError(result["error"])
        return result

    if name == "notify_reject_agent":
        result = _api_post(f"/api/agents/{args['session_id']}/reject")
        if result and result.get("error"):
            raise RuntimeError(result["error"])
        return result

    if name == "notify_list_events":
        params = []
        if args.get("agent"):
            params.append(f"agent={args['agent']}")
        if args.get("category"):
            params.append(f"category={args['category']}")
        if args.get("project"):
            params.append(f"project={args['project']}")
        limit = args.get("limit", 30)
        params.append(f"limit={limit}")
        query = "?" + "&".join(params)
        result = _api_get(f"/api/events{query}")
        if result is None:
            raise ConnectionError("daemon not running or not responding")
        return result

    if name == "notify_health":
        result = _api_get("/api/health")
        if result is None:
            raise ConnectionError("daemon not running or not responding")
        return result

    if name == "notify_list_messages":
        params = []
        if args.get("status"):
            params.append(f"status={args['status']}")
        limit = args.get("limit", 30)
        params.append(f"limit={limit}")
        query = "?" + "&".join(params)
        result = _api_get(f"/api/messages{query}")
        if result is None:
            raise ConnectionError("daemon not running or not responding")
        return result

    if name == "notify_list_tasks":
        params = []
        if args.get("session_id"):
            params.append(f"session_id={args['session_id']}")
        if args.get("status"):
            params.append(f"status={args['status']}")
        query = "?" + "&".join(params) if params else ""
        result = _api_get(f"/api/tasks{query}")
        if result is None:
            raise ConnectionError("daemon not running or not responding")
        return result

    if name == "notify_create_task":
        body = {"title": args["title"]}
        for field in ("description", "session_id", "priority", "dependencies"):
            if args.get(field):
                body[field] = args[field]
        result = _api_post("/api/tasks", body)
        if result and result.get("error"):
            raise RuntimeError(result["error"])
        return result

    if name == "notify_update_task":
        task_id = args.pop("task_id")
        # Use PUT via urllib
        try:
            data = json.dumps(args).encode()
            req = Request(
                f"{_base_url()}/api/tasks/{task_id}",
                data=data,
                headers={"Content-Type": "application/json"},
                method="PUT",
            )
            with urlopen(req, timeout=5) as resp:
                result = json.loads(resp.read().decode())
        except (URLError, OSError, json.JSONDecodeError, ValueError) as e:
            raise RuntimeError(str(e))
        return result

    if name == "notify_next_task":
        params = []
        if args.get("session_id"):
            params.append(f"session_id={args['session_id']}")
        query = "?" + "&".join(params) if params else ""
        result = _api_get(f"/api/tasks/next{query}")
        if result is None:
            raise ConnectionError("daemon not running or not responding")
        return result

    if name == "notify_set_context":
        body = {"key": args["key"], "value": args["value"]}
        if args.get("scope"):
            body["scope"] = args["scope"]
        if args.get("updated_by"):
            body["updated_by"] = args["updated_by"]
        result = _api_post("/api/context", body)
        if result and result.get("error"):
            raise RuntimeError(result["error"])
        return result

    if name == "notify_get_context":
        scope = args.get("scope", "global")
        # GET /api/context?scope=X — then filter by key client-side
        # (simpler than adding a key query param to the API)
        all_ctx = _api_get(f"/api/context?scope={scope}")
        if all_ctx is None:
            raise ConnectionError("daemon not running or not responding")
        key = args["key"]
        for item in all_ctx if isinstance(all_ctx, list) else []:
            if item.get("key") == key:
                return item
        return {"key": key, "scope": scope, "value": None, "message": "not found"}

    if name == "notify_list_context":
        params = []
        if args.get("scope"):
            params.append(f"scope={args['scope']}")
        query = "?" + "&".join(params) if params else ""
        result = _api_get(f"/api/context{query}")
        if result is None:
            raise ConnectionError("daemon not running or not responding")
        return result

    if name == "notify_delete_context":
        scope = args.get("scope", "global")
        result = _api_delete(f"/api/context/{args['key']}?scope={scope}")
        if result is None:
            raise ConnectionError("daemon not running or not responding")
        return result

    if name == "notify_add_route":
        body = {
            "from_agent": args.get("from_agent", "*"),
            "to_agent": "*",
            "event_type": args.get("event_type", "completion"),
            "action": args["action"],
            "priority": args.get("priority", 0),
            "template": args.get("template", ""),
        }
        result = _api_post("/api/rules", body)
        if result and result.get("error"):
            raise RuntimeError(result["error"])
        return result

    if name == "notify_list_rules":
        result = _api_get("/api/rules")
        if result is None:
            raise ConnectionError("daemon not running or not responding")
        return result

    if name == "notify_delete_rule":
        result = _api_delete(f"/api/rules/{args['rule_id']}")
        if result is None:
            raise ConnectionError("daemon not running or not responding")
        return result

    if name == "notify_set_preference":
        result = _api_post("/api/preferences", {
            "key": args["key"],
            "value": args["value"],
        })
        if result and result.get("error"):
            raise RuntimeError(result["error"])
        return result

    raise ValueError(f"unknown tool: {name}")


# ---------------------------------------------------------------------------
# JSON-RPC message handling
# ---------------------------------------------------------------------------

def _response(req_id, result: dict) -> dict:
    return {"jsonrpc": "2.0", "id": req_id, "result": result}


def _error(req_id, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}}


def _handle_message(msg: dict) -> dict | None:
    """Handle a JSON-RPC message. Returns a response dict, or None for notifications."""
    method = msg.get("method", "")
    req_id = msg.get("id")
    params = msg.get("params", {})

    # Notifications (no id) — handle silently
    if req_id is None:
        return None

    if method == "initialize":
        return _response(req_id, {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {
                "tools": {"listChanged": False},
            },
            "serverInfo": {
                "name": SERVER_NAME,
                "version": SERVER_VERSION,
            },
            "instructions": (
                "agent-notify is a control plane for coordinating multiple AI coding agents. "
                "Use these tools to see what other agents are doing, spawn new agents, "
                "send messages between agents, and manage agent sessions."
            ),
        })

    if method == "ping":
        return _response(req_id, {})

    if method == "tools/list":
        return _response(req_id, {"tools": TOOLS})

    if method == "tools/call":
        tool_name = params.get("name", "")
        arguments = params.get("arguments", {})

        # Check tool exists
        known = {t["name"] for t in TOOLS}
        if tool_name not in known:
            return _error(req_id, -32602, f"Unknown tool: {tool_name}")

        result = _handle_tool(tool_name, arguments)
        return _response(req_id, result)

    return _error(req_id, -32601, f"Method not found: {method}")


# ---------------------------------------------------------------------------
# Main stdio loop
# ---------------------------------------------------------------------------

def main() -> None:
    """Run the MCP stdio server."""
    _log("agent-notify MCP server starting")
    _log(f"daemon endpoint: {_base_url()}")

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue

        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            resp = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Parse error"}}
            _write(resp)
            continue

        resp = _handle_message(msg)
        if resp is not None:
            _write(resp)


def _write(msg: dict) -> None:
    """Write a JSON-RPC message to stdout."""
    sys.stdout.write(json.dumps(msg, separators=(",", ":")) + "\n")
    sys.stdout.flush()


def _log(msg: str) -> None:
    """Log to stderr (safe for MCP servers)."""
    print(f"[agent-notify-mcp] {msg}", file=sys.stderr, flush=True)


if __name__ == "__main__":
    main()
