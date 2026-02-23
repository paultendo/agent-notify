"""After-work routing — triggered when an agent completes or stops.

Supports multiple routing strategies:

  next_task   — Auto-assign the next pending task from the DAG to the same agent.
                Template field is ignored. The agent receives the task title + description.

  handoff     — Hand off to another agent session. Template field contains the
                target session_id. The source agent's work summary (if any) is
                forwarded as a message.

  spawn       — Spawn a new agent in a new pane. Template field is a JSON string:
                {"agent": "claude", "prompt": "...", "cwd": "..."}.

  notify      — Just broadcast an SSE event. No terminal action. Template field
                is an optional custom message.

  pipeline    — Run a sequence of routing actions. Template field is a JSON array
                of {action, template} objects, executed in order.

Rules are matched via coordination_rules where event_type = 'completion' or 'stop'
and action is one of the above. The `priority` field controls precedence when
multiple rules match.
"""

import json

from .db import Database
from .terminal import send_text, spawn_pane


async def route_after_work(db: Database, event_data: dict) -> list[dict]:
    """Run after-work routing for a completed/stopped agent.

    Returns a list of routing results (one per matched rule).
    """
    agent_name = event_data.get("agent_name", "")
    category = event_data.get("category", "")
    session_id = event_data.get("session_id", "")

    # Only trigger on completion or stop
    if category not in ("completion", "stop"):
        return []

    rules = db.match_rules_for_event(agent_name, category)
    # Filter to routing actions (not approve/block/auto which are for messages)
    route_rules = [r for r in rules if r.get("action") in (
        "next_task", "handoff", "spawn", "notify", "pipeline",
    )]

    if not route_rules:
        return []

    results = []
    for rule in route_rules:
        result = await _execute_route(db, rule, event_data, session_id)
        results.append(result)

    return results


async def _execute_route(
    db: Database, rule: dict, event_data: dict, session_id: str
) -> dict:
    """Execute a single routing action."""
    action = rule.get("action", "")
    template = rule.get("template", "")

    if action == "next_task":
        return await _route_next_task(db, session_id)

    if action == "handoff":
        return await _route_handoff(db, event_data, template, session_id)

    if action == "spawn":
        return await _route_spawn(db, event_data, template)

    if action == "notify":
        return _route_notify(event_data, template)

    if action == "pipeline":
        return await _route_pipeline(db, event_data, template, session_id)

    return {"action": action, "status": "unknown_action"}


async def _route_next_task(db: Database, session_id: str) -> dict:
    """Assign next pending task to the agent that just finished."""
    task = db.next_task(session_id=session_id)
    if not task:
        # Try global tasks (no session filter)
        task = db.next_task()

    if not task:
        return {"action": "next_task", "status": "no_tasks"}

    # Mark as in_progress and assign to this session
    db.update_task(task["id"], {"status": "in_progress", "session_id": session_id})

    # Send the task to the agent's terminal
    session = db.get_session(session_id)
    if session:
        text = f"[Next Task #{task['id']}] {task['title']}"
        if task.get("description"):
            text += f"\n{task['description']}"
        text += "\n"
        await send_text(session.get("terminal", "{}"), text)

    return {
        "action": "next_task",
        "status": "assigned",
        "task_id": task["id"],
        "task_title": task["title"],
    }


async def _route_handoff(
    db: Database, event_data: dict, template: str, from_session_id: str
) -> dict:
    """Hand off work to another agent session."""
    target_session_id = template.strip()
    if not target_session_id:
        return {"action": "handoff", "status": "no_target", "error": "template must contain target session_id"}

    target = db.get_session(target_session_id)
    if not target:
        return {"action": "handoff", "status": "target_not_found", "error": f"session {target_session_id} not found"}

    # Build handoff message
    agent_name = event_data.get("agent_name", "Agent")
    summary = event_data.get("work_summary", "")
    message = event_data.get("message", "")
    content = summary or message or "Work completed"

    text = f"[Handoff from {agent_name}] {content}\n"
    result = await send_text(target.get("terminal", "{}"), text)

    # Also store as a message in the mesh
    db.insert_message({
        "from_session": from_session_id,
        "to_session": target_session_id,
        "message_type": "handoff",
        "content": content,
        "status": "delivered" if result.get("ok") else "pending",
    })

    return {
        "action": "handoff",
        "status": "delivered" if result.get("ok") else "pending",
        "target_session_id": target_session_id,
    }


async def _route_spawn(db: Database, event_data: dict, template: str) -> dict:
    """Spawn a new agent from template."""
    try:
        config = json.loads(template) if template else {}
    except json.JSONDecodeError:
        config = {"prompt": template}

    agent = config.get("agent", "claude")
    prompt = config.get("prompt", "")
    cwd = config.get("cwd", event_data.get("project_cwd", ""))

    # If prompt contains {summary}, substitute the work summary
    summary = event_data.get("work_summary", "")
    if "{summary}" in prompt and summary:
        prompt = prompt.replace("{summary}", summary)

    result = await spawn_pane(agent=agent, prompt=prompt, cwd=cwd)
    if result.get("ok"):
        return {
            "action": "spawn",
            "status": "spawned",
            "pane_id": result.get("pane_id", ""),
            "agent": agent,
        }
    return {"action": "spawn", "status": "failed", "error": result.get("error", "")}


def _route_notify(event_data: dict, template: str) -> dict:
    """Just return data for SSE broadcast (no terminal action)."""
    return {
        "action": "notify",
        "status": "ok",
        "message": template or f"{event_data.get('agent_name', 'Agent')} finished",
    }


async def _route_pipeline(
    db: Database, event_data: dict, template: str, session_id: str
) -> dict:
    """Execute a sequence of routing actions."""
    try:
        steps = json.loads(template) if template else []
    except json.JSONDecodeError:
        return {"action": "pipeline", "status": "invalid_template"}

    if not isinstance(steps, list):
        return {"action": "pipeline", "status": "invalid_template"}

    results = []
    for step in steps:
        if not isinstance(step, dict):
            continue
        step_rule = {"action": step.get("action", ""), "template": step.get("template", "")}
        result = await _execute_route(db, step_rule, event_data, session_id)
        results.append(result)

    return {"action": "pipeline", "status": "ok", "steps": results}
