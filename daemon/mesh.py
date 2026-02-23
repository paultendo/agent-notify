"""Agent mesh — message routing between agents.

Agents communicate by sending structured messages through the daemon.
Messages are delivered by typing into the target agent's terminal pane.
Each agent stays in its own authenticated CLI session — the mesh just routes text.
"""

import json
from datetime import datetime, timezone

from .db import Database
from .terminal import send_text


async def route_message(db: Database, message_id: int) -> dict:
    """Route a message to its target agent's terminal.

    Checks coordination rules, delivers if auto-approved, otherwise
    leaves as pending for manual approval.

    Returns {"action": "delivered|pending|blocked", ...}
    """
    msg = db.get_message(message_id)
    if not msg:
        return {"action": "error", "error": "message not found"}

    # Look up source and target sessions
    from_session = db.get_session(msg["from_session"])
    to_session = db.get_session(msg["to_session"])

    if not to_session:
        return {"action": "error", "error": f"target session not found: {msg['to_session']}"}

    from_agent = from_session["agent_name"] if from_session else "unknown"
    to_agent = to_session["agent_name"]

    # Check coordination rules
    rule = db.match_rule(from_agent, to_agent, msg["message_type"])
    action = rule.get("action", "approve") if isinstance(rule, dict) else rule

    if action == "block":
        db.update_message_status(message_id, "rejected")
        return {"action": "blocked", "reason": "coordination rule"}

    if action == "auto":
        # Auto-deliver: type message into target terminal
        result = await deliver_message(db, msg, to_session)
        return result

    # Default: pending (requires manual approval)
    return {"action": "pending", "message_id": message_id}


async def deliver_message(db: Database, msg: dict, to_session: dict) -> dict:
    """Deliver a message by typing it into the target agent's terminal."""
    terminal = to_session.get("terminal", "{}")

    # Format the message as agent input
    content = msg.get("content", "")
    from_session = db.get_session(msg["from_session"])
    from_name = from_session["agent_name"] if from_session else "unknown"

    # Prefix with context so the receiving agent knows the source
    text = f"[From {from_name}] {content}\n"

    result = await send_text(terminal, text)

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%fZ")
    if result.get("ok"):
        db.update_message_status(msg["id"], "delivered", delivered_at=now)
        return {"action": "delivered", "message_id": msg["id"]}
    else:
        return {
            "action": "error",
            "message_id": msg["id"],
            "error": result.get("error", "delivery failed"),
        }


async def approve_message(db: Database, message_id: int) -> dict:
    """Manually approve and deliver a pending message."""
    msg = db.get_message(message_id)
    if not msg:
        return {"ok": False, "error": "message not found"}
    if msg["status"] != "pending":
        return {"ok": False, "error": f"message is {msg['status']}, not pending"}

    to_session = db.get_session(msg["to_session"])
    if not to_session:
        return {"ok": False, "error": "target session not found"}

    return await deliver_message(db, msg, to_session)


async def reject_message(db: Database, message_id: int) -> dict:
    """Reject a pending message."""
    msg = db.get_message(message_id)
    if not msg:
        return {"ok": False, "error": "message not found"}
    if msg["status"] != "pending":
        return {"ok": False, "error": f"message is {msg['status']}, not pending"}

    db.update_message_status(message_id, "rejected")
    return {"ok": True, "message_id": message_id, "status": "rejected"}
