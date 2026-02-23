"""Route handlers for the daemon HTTP API.

Phase 1: Events, agents, health, SSE
Phase 2: Two-way control (approve, reject, send, interrupt)
Phase 3: Agent mesh (messages, coordination rules)
Phase 4: Monitoring (stuck detection, session events)
"""

import time
import uuid
from typing import Any

from .db import Database
from .mesh import route_message, approve_message, reject_message
from .monitor import Monitor
from .router import route_after_work
from .sse import SSERegistry
from .terminal import send_text, send_approve, send_reject, send_interrupt, spawn_pane, stop_session

VERSION = "0.1.0"


class Router:
    def __init__(
        self,
        db: Database,
        sse: SSERegistry,
        monitor: Monitor,
        start_time: float,
    ):
        self.db = db
        self.sse = sse
        self.monitor = monitor
        self.start_time = start_time

    async def dispatch(self, request: dict) -> dict | None:
        """Dispatch request to handler. Returns None for SSE (writer ownership)."""
        method = request["method"]
        path = request["path"]
        query = request.get("query", {})
        body = request.get("body", {})

        # --- Phase 1: Core ---

        if method == "POST" and path == "/api/events":
            return await self._post_event(body)

        if method == "GET" and path == "/api/events/stream":
            return None  # Signal SSE ownership

        if method == "GET" and path == "/api/events":
            return self._list_events(query)

        if method == "GET" and path == "/api/agents":
            return self._list_agents(query)

        if method == "GET" and path == "/api/health":
            return self._health()

        # POST /api/heartbeat
        if method == "POST" and path == "/api/heartbeat":
            return self._heartbeat(body)

        # --- Preferences ---

        if method == "GET" and path == "/api/preferences":
            return self._list_preferences()

        if method == "POST" and path == "/api/preferences":
            return self._set_preference(body)

        if method == "DELETE" and path.startswith("/api/preferences/"):
            key = path[len("/api/preferences/"):]
            return self._delete_preference(key)

        # --- Phase 2: Two-way control ---

        # POST /api/agents/spawn
        if method == "POST" and path == "/api/agents/spawn":
            return await self._agent_spawn(body)

        # POST /api/agents/{id}/stop
        if method == "POST" and path.startswith("/api/agents/") and path.endswith("/stop"):
            session_id = path[len("/api/agents/"):-len("/stop")]
            return await self._agent_stop(session_id)

        # POST /api/agents/{id}/approve
        if method == "POST" and path.startswith("/api/agents/") and path.endswith("/approve"):
            session_id = path[len("/api/agents/"):-len("/approve")]
            return await self._agent_approve(session_id)

        # POST /api/agents/{id}/reject
        if method == "POST" and path.startswith("/api/agents/") and path.endswith("/reject"):
            session_id = path[len("/api/agents/"):-len("/reject")]
            return await self._agent_reject(session_id)

        # POST /api/agents/{id}/send
        if method == "POST" and path.startswith("/api/agents/") and path.endswith("/send"):
            session_id = path[len("/api/agents/"):-len("/send")]
            return await self._agent_send(session_id, body)

        # POST /api/agents/{id}/interrupt
        if method == "POST" and path.startswith("/api/agents/") and path.endswith("/interrupt"):
            session_id = path[len("/api/agents/"):-len("/interrupt")]
            return await self._agent_interrupt(session_id)

        # GET /api/agents/{id}/events
        if method == "GET" and path.startswith("/api/agents/") and path.endswith("/events"):
            session_id = path[len("/api/agents/"):-len("/events")]
            return self._agent_events(session_id, query)

        # GET /api/agents/{id}/children
        if method == "GET" and path.startswith("/api/agents/") and path.endswith("/children"):
            session_id = path[len("/api/agents/"):-len("/children")]
            return self._agent_children(session_id)

        # GET /api/agents/{id}  (must come after more specific routes)
        if method == "GET" and path.startswith("/api/agents/"):
            session_id = path[len("/api/agents/"):]
            return self._get_agent(session_id)

        # --- Phase 3: Agent mesh ---

        if method == "POST" and path == "/api/messages":
            return await self._post_message(body)

        if method == "GET" and path == "/api/messages":
            return self._list_messages(query)

        # POST /api/messages/{id}/approve
        if method == "POST" and path.startswith("/api/messages/") and path.endswith("/approve"):
            msg_id = path[len("/api/messages/"):-len("/approve")]
            return await self._approve_message(msg_id)

        # POST /api/messages/{id}/reject
        if method == "POST" and path.startswith("/api/messages/") and path.endswith("/reject"):
            msg_id = path[len("/api/messages/"):-len("/reject")]
            return await self._reject_message(msg_id)

        # GET /api/messages/{id}
        if method == "GET" and path.startswith("/api/messages/"):
            msg_id = path[len("/api/messages/"):]
            return self._get_message(msg_id)

        # --- Tasks ---

        if method == "POST" and path == "/api/tasks":
            return self._post_task(body)

        if method == "GET" and path == "/api/tasks/next":
            return self._next_task(query)

        if method == "GET" and path == "/api/tasks":
            return self._list_tasks(query)

        # PUT /api/tasks/{id}
        if method == "PUT" and path.startswith("/api/tasks/"):
            task_id = path[len("/api/tasks/"):]
            return self._update_task(task_id, body)

        # DELETE /api/tasks/{id}
        if method == "DELETE" and path.startswith("/api/tasks/"):
            task_id = path[len("/api/tasks/"):]
            return self._delete_task(task_id)

        # GET /api/tasks/{id}
        if method == "GET" and path.startswith("/api/tasks/"):
            task_id = path[len("/api/tasks/"):]
            return self._get_task(task_id)

        # --- Context (shared variables) ---

        if method == "GET" and path == "/api/context":
            return self._list_context(query)

        if method == "POST" and path == "/api/context":
            return self._set_context(body)

        if method == "DELETE" and path.startswith("/api/context/"):
            key = path[len("/api/context/"):]
            scope = query.get("scope", "global")
            return self._delete_context(key, scope)

        # --- Coordination rules ---

        if method == "POST" and path == "/api/rules":
            return self._post_rule(body)

        if method == "GET" and path == "/api/rules":
            return self._list_rules()

        if method == "DELETE" and path.startswith("/api/rules/"):
            rule_id = path[len("/api/rules/"):]
            return self._delete_rule(rule_id)

        # --- Web UI ---
        if method == "GET" and path in ("/", "/ui", "/dashboard"):
            return {"status": 200, "body": "", "serve_static": "index.html"}

        return _response(404, {"error": "not found"})

    # --- Phase 1 handlers ---

    async def _post_event(self, body: dict) -> dict:
        if not body.get("title") and not body.get("agent_name"):
            return _response(400, {"error": "title or agent_name required"})

        event_id = self.db.insert_event(body)
        self.db.upsert_session(body)

        # Clear stuck alert on new activity
        session_id = body.get("session_id", "")
        if session_id:
            self.monitor.clear_alert(session_id)

        event_data = self.db.get_event(event_id)
        if event_data:
            await self.sse.broadcast(event_data)

        # After-work routing: trigger on completion/stop events
        route_results = await route_after_work(self.db, body)
        if route_results:
            for rr in route_results:
                await self.sse.broadcast({
                    "type": "route",
                    "session_id": body.get("session_id", ""),
                    **rr,
                })

        return _response(201, {"id": event_id, "status": "created"})

    def _list_events(self, query: dict) -> dict:
        limit = _int_param(query, "limit", 50)
        events = self.db.list_events(
            agent=query.get("agent"),
            category=query.get("category"),
            project=query.get("project"),
            since=query.get("since"),
            limit=limit,
        )
        return _response(200, events)

    def _list_agents(self, query: dict) -> dict:
        sessions = self.db.list_sessions(status=query.get("status"))
        return _response(200, sessions)

    def _get_agent(self, session_id: str) -> dict:
        session = self.db.get_session(session_id)
        if not session:
            return _response(404, {"error": "session not found"})
        return _response(200, session)

    def _health(self) -> dict:
        uptime = time.time() - self.start_time
        sessions = self.db.list_sessions()
        active = sum(1 for s in sessions if s["status"] in ("active", "waiting"))
        return _response(200, {
            "status": "ok",
            "version": VERSION,
            "uptime": round(uptime, 1),
            "sse_clients": self.sse.client_count,
            "agents_total": len(sessions),
            "agents_active": active,
        })

    # --- Phase 2 handlers ---

    async def _agent_spawn(self, body: dict) -> dict:
        agent = body.get("agent", "claude")
        prompt = body.get("prompt", "")
        cwd = body.get("cwd", "")

        result = await spawn_pane(agent=agent, prompt=prompt, cwd=cwd)
        if not result.get("ok"):
            return _response(500, {"error": result.get("error", "spawn failed")})

        terminal = result.get("terminal", {})
        pane_id = result.get("pane_id", "")

        # Register a synthetic start event so the daemon tracks this session
        session_id = f"spawn-{uuid.uuid4().hex[:12]}"
        event_data = {
            "agent_name": agent.capitalize(),
            "session_id": session_id,
            "category": "start",
            "title": f"{agent.capitalize()}: Spawned from daemon",
            "message": prompt or "New session",
            "project_cwd": cwd,
            "terminal": terminal,
        }
        self.db.insert_event(event_data)
        self.db.upsert_session(event_data)

        await self.sse.broadcast({
            "type": "spawn", "action": "spawned",
            "session_id": session_id, "agent_name": agent.capitalize(),
            "pane_id": pane_id,
        })

        return _response(201, {
            "status": "spawned",
            "session_id": session_id,
            "pane_id": pane_id,
            "terminal": terminal,
        })

    async def _agent_stop(self, session_id: str) -> dict:
        session = self.db.get_session(session_id)
        if not session:
            return _response(404, {"error": "session not found"})

        terminal_data = session.get("terminal", "{}")
        result = await stop_session(terminal_data)

        # Mark session as ended regardless of terminal result
        stop_data = {
            "agent_name": session["agent_name"],
            "session_id": session_id,
            "category": "stop",
            "title": f"{session['agent_name']}: Stopped by user",
        }
        self.db.insert_event(stop_data)
        self.db.upsert_session(stop_data)

        await self.sse.broadcast({
            "type": "action", "action": "stop",
            "session_id": session_id, "agent_name": session["agent_name"],
        })

        if result.get("ok"):
            return _response(200, {"status": "stopped", "session_id": session_id})
        # Session marked ended but terminal command failed
        return _response(200, {
            "status": "stopped",
            "session_id": session_id,
            "warning": result.get("error", "terminal command failed"),
        })

    async def _agent_approve(self, session_id: str) -> dict:
        session = self.db.get_session(session_id)
        if not session:
            return _response(404, {"error": "session not found"})
        result = await send_approve(session.get("terminal", "{}"))
        if result.get("ok"):
            await self.sse.broadcast({
                "type": "action", "action": "approve",
                "session_id": session_id, "agent_name": session["agent_name"],
            })
            return _response(200, {"status": "approved", "session_id": session_id})
        return _response(500, {"error": result.get("error", "failed")})

    async def _agent_reject(self, session_id: str) -> dict:
        session = self.db.get_session(session_id)
        if not session:
            return _response(404, {"error": "session not found"})
        result = await send_reject(session.get("terminal", "{}"))
        if result.get("ok"):
            await self.sse.broadcast({
                "type": "action", "action": "reject",
                "session_id": session_id, "agent_name": session["agent_name"],
            })
            return _response(200, {"status": "rejected", "session_id": session_id})
        return _response(500, {"error": result.get("error", "failed")})

    async def _agent_send(self, session_id: str, body: dict) -> dict:
        session = self.db.get_session(session_id)
        if not session:
            return _response(404, {"error": "session not found"})
        text = body.get("text", "")
        if not text:
            return _response(400, {"error": "text required"})
        # Append newline if not present
        if not text.endswith("\n"):
            text += "\n"
        result = await send_text(session.get("terminal", "{}"), text)
        if result.get("ok"):
            await self.sse.broadcast({
                "type": "action", "action": "send",
                "session_id": session_id, "agent_name": session["agent_name"],
                "text": body.get("text", ""),
            })
            return _response(200, {"status": "sent", "session_id": session_id})
        return _response(500, {"error": result.get("error", "failed")})

    async def _agent_interrupt(self, session_id: str) -> dict:
        session = self.db.get_session(session_id)
        if not session:
            return _response(404, {"error": "session not found"})
        result = await send_interrupt(session.get("terminal", "{}"))
        if result.get("ok"):
            await self.sse.broadcast({
                "type": "action", "action": "interrupt",
                "session_id": session_id, "agent_name": session["agent_name"],
            })
            return _response(200, {"status": "interrupted", "session_id": session_id})
        return _response(500, {"error": result.get("error", "failed")})

    def _agent_events(self, session_id: str, query: dict) -> dict:
        session = self.db.get_session(session_id)
        if not session:
            return _response(404, {"error": "session not found"})
        limit = _int_param(query, "limit", 50)
        events = self.db.session_events(session_id, limit=limit)
        return _response(200, events)

    # --- Phase 3 handlers ---

    async def _post_message(self, body: dict) -> dict:
        if not body.get("from_session") or not body.get("to_session"):
            return _response(400, {"error": "from_session and to_session required"})
        if not body.get("content"):
            return _response(400, {"error": "content required"})

        msg_id = self.db.insert_message(body)
        result = await route_message(self.db, msg_id)

        msg_data = self.db.get_message(msg_id)
        if msg_data:
            await self.sse.broadcast({
                "type": "message",
                **msg_data,
                "routing": result.get("action", "unknown"),
            })

        return _response(201, {"id": msg_id, **result})

    def _list_messages(self, query: dict) -> dict:
        limit = _int_param(query, "limit", 50)
        messages = self.db.list_messages(
            status=query.get("status"),
            limit=limit,
        )
        return _response(200, messages)

    def _get_message(self, msg_id_str: str) -> dict:
        try:
            msg_id = int(msg_id_str)
        except ValueError:
            return _response(400, {"error": "invalid message id"})
        msg = self.db.get_message(msg_id)
        if not msg:
            return _response(404, {"error": "message not found"})
        return _response(200, msg)

    async def _approve_message(self, msg_id_str: str) -> dict:
        try:
            msg_id = int(msg_id_str)
        except ValueError:
            return _response(400, {"error": "invalid message id"})
        result = await approve_message(self.db, msg_id)
        if result.get("action") == "delivered":
            await self.sse.broadcast({
                "type": "message_action", "action": "approved",
                "message_id": msg_id,
            })
            return _response(200, result)
        return _response(500, result)

    async def _reject_message(self, msg_id_str: str) -> dict:
        try:
            msg_id = int(msg_id_str)
        except ValueError:
            return _response(400, {"error": "invalid message id"})
        result = await reject_message(self.db, msg_id)
        if result.get("ok"):
            await self.sse.broadcast({
                "type": "message_action", "action": "rejected",
                "message_id": msg_id,
            })
            return _response(200, result)
        return _response(400, result)

    # --- Task handlers ---

    def _post_task(self, body: dict) -> dict:
        if not body.get("title"):
            return _response(400, {"error": "title required"})
        task_id = self.db.insert_task(body)
        return _response(201, {"id": task_id, "status": "created"})

    def _list_tasks(self, query: dict) -> dict:
        limit = _int_param(query, "limit", 100)
        tasks = self.db.list_tasks(
            session_id=query.get("session_id"),
            status=query.get("status"),
            limit=limit,
        )
        return _response(200, tasks)

    def _get_task(self, task_id_str: str) -> dict:
        try:
            task_id = int(task_id_str)
        except ValueError:
            return _response(400, {"error": "invalid task id"})
        task = self.db.get_task(task_id)
        if not task:
            return _response(404, {"error": "task not found"})
        return _response(200, task)

    def _update_task(self, task_id_str: str, body: dict) -> dict:
        try:
            task_id = int(task_id_str)
        except ValueError:
            return _response(400, {"error": "invalid task id"})
        if self.db.update_task(task_id, body):
            task = self.db.get_task(task_id)
            return _response(200, task)
        return _response(404, {"error": "task not found"})

    def _delete_task(self, task_id_str: str) -> dict:
        try:
            task_id = int(task_id_str)
        except ValueError:
            return _response(400, {"error": "invalid task id"})
        if self.db.delete_task(task_id):
            return _response(200, {"status": "deleted"})
        return _response(404, {"error": "task not found"})

    def _next_task(self, query: dict) -> dict:
        task = self.db.next_task(session_id=query.get("session_id"))
        if task:
            return _response(200, task)
        return _response(200, {"message": "no actionable tasks"})

    # --- Coordination rules handlers ---

    def _post_rule(self, body: dict) -> dict:
        rule_id = self.db.insert_rule(body)
        return _response(201, {"id": rule_id, "status": "created"})

    def _list_rules(self) -> dict:
        rules = self.db.list_rules()
        return _response(200, rules)

    def _delete_rule(self, rule_id_str: str) -> dict:
        try:
            rule_id = int(rule_id_str)
        except ValueError:
            return _response(400, {"error": "invalid rule id"})
        if self.db.delete_rule(rule_id):
            return _response(200, {"status": "deleted"})
        return _response(404, {"error": "rule not found"})

    # --- Heartbeat ---

    def _heartbeat(self, body: dict) -> dict:
        session_id = body.get("session_id", "")
        if not session_id:
            return _response(400, {"error": "session_id required"})
        found = self.db.heartbeat(session_id)
        if found:
            self.monitor.clear_alert(session_id)
            return _response(200, {"status": "ok"})
        return _response(404, {"error": "session not found"})

    # --- Swarm: child sessions ---

    def _agent_children(self, session_id: str) -> dict:
        children = self.db.child_sessions(session_id)
        return _response(200, children)

    # --- Context (shared variables) ---

    def _list_context(self, query: dict) -> dict:
        ctx = self.db.list_context(scope=query.get("scope"))
        return _response(200, ctx)

    def _set_context(self, body: dict) -> dict:
        key = body.get("key", "")
        if not key:
            return _response(400, {"error": "key required"})
        value = body.get("value", "")
        scope = body.get("scope", "global")
        updated_by = body.get("updated_by", "")
        self.db.set_context(key, value, scope=scope, updated_by=updated_by)
        return _response(200, {"status": "ok", "key": key, "scope": scope, "value": value})

    def _delete_context(self, key: str, scope: str) -> dict:
        if self.db.delete_context(key, scope=scope):
            return _response(200, {"status": "deleted"})
        return _response(404, {"error": "context variable not found"})

    # --- Preferences ---

    def _list_preferences(self) -> dict:
        prefs = self.db.list_preferences()
        return _response(200, prefs)

    def _set_preference(self, body: dict) -> dict:
        key = body.get("key", "")
        value = body.get("value", "")
        if not key:
            return _response(400, {"error": "key required"})
        self.db.set_preference(key, value)
        return _response(200, {"status": "ok", "key": key, "value": value})

    def _delete_preference(self, key: str) -> dict:
        if self.db.delete_preference(key):
            return _response(200, {"status": "deleted"})
        return _response(404, {"error": "preference not found"})


def _response(status: int, body: Any) -> dict:
    return {"status": status, "body": body}


def _int_param(query: dict, key: str, default: int) -> int:
    if key in query:
        try:
            return int(query[key])
        except ValueError:
            pass
    return default
