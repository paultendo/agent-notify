"""SQLite event store, agent session registry, and mesh message bus."""

import json
import os
import sqlite3
from pathlib import Path

DEFAULT_DB_PATH = os.path.join(Path.home(), ".codex", "daemon.db")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_name        TEXT NOT NULL,
    session_id        TEXT NOT NULL DEFAULT '',
    parent_session_id TEXT NOT NULL DEFAULT '',
    category          TEXT NOT NULL DEFAULT 'completion',
    title             TEXT NOT NULL,
    message           TEXT NOT NULL DEFAULT '',
    project_cwd       TEXT NOT NULL DEFAULT '',
    git_branch        TEXT NOT NULL DEFAULT '',
    terminal          TEXT NOT NULL DEFAULT '{}',
    work_summary      TEXT NOT NULL DEFAULT '',
    created_at        TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

CREATE TABLE IF NOT EXISTS agent_sessions (
    session_id        TEXT PRIMARY KEY,
    parent_session_id TEXT NOT NULL DEFAULT '',
    agent_name        TEXT NOT NULL,
    project_cwd       TEXT NOT NULL DEFAULT '',
    git_branch        TEXT NOT NULL DEFAULT '',
    terminal          TEXT NOT NULL DEFAULT '{}',
    status            TEXT NOT NULL DEFAULT 'active',
    last_event        TEXT NOT NULL DEFAULT 'completion',
    first_seen        TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    last_seen         TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    last_heartbeat    TEXT NOT NULL DEFAULT '',
    ended_at          TEXT NOT NULL DEFAULT '',
    event_count       INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS preferences (
    key         TEXT PRIMARY KEY,
    value       TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS messages (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    from_session  TEXT NOT NULL,
    to_session    TEXT NOT NULL,
    message_type  TEXT NOT NULL DEFAULT 'handoff',
    content       TEXT NOT NULL DEFAULT '',
    status        TEXT NOT NULL DEFAULT 'pending',
    created_at    TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    delivered_at  TEXT
);

CREATE TABLE IF NOT EXISTS coordination_rules (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    from_agent  TEXT NOT NULL DEFAULT '*',
    to_agent    TEXT NOT NULL DEFAULT '*',
    event_type  TEXT NOT NULL DEFAULT '*',
    action      TEXT NOT NULL DEFAULT 'approve',
    priority    INTEGER NOT NULL DEFAULT 0,
    template    TEXT NOT NULL DEFAULT '',
    created_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

CREATE TABLE IF NOT EXISTS tasks (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id    TEXT NOT NULL DEFAULT '',
    title         TEXT NOT NULL,
    description   TEXT NOT NULL DEFAULT '',
    status        TEXT NOT NULL DEFAULT 'pending',
    priority      TEXT NOT NULL DEFAULT 'medium',
    dependencies  TEXT NOT NULL DEFAULT '[]',
    created_at    TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    updated_at    TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

CREATE TABLE IF NOT EXISTS context (
    key           TEXT NOT NULL,
    scope         TEXT NOT NULL DEFAULT 'global',
    value         TEXT NOT NULL DEFAULT '',
    updated_by    TEXT NOT NULL DEFAULT '',
    updated_at    TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    PRIMARY KEY (key, scope)
);
"""

_STATUS_MAP = {
    "start": "active",
    "completion": "idle",
    "approval": "waiting",
    "question": "waiting",
    "error": "error",
    "auth": "active",
    "stop": "ended",
}

# Migration: add columns that may not exist in older databases
_MIGRATIONS = [
    "ALTER TABLE events ADD COLUMN parent_session_id TEXT NOT NULL DEFAULT ''",
    "ALTER TABLE events ADD COLUMN work_summary TEXT NOT NULL DEFAULT ''",
    "ALTER TABLE agent_sessions ADD COLUMN parent_session_id TEXT NOT NULL DEFAULT ''",
    "ALTER TABLE agent_sessions ADD COLUMN last_heartbeat TEXT NOT NULL DEFAULT ''",
    "ALTER TABLE agent_sessions ADD COLUMN ended_at TEXT NOT NULL DEFAULT ''",
    "CREATE TABLE IF NOT EXISTS preferences (key TEXT PRIMARY KEY, value TEXT NOT NULL DEFAULT '')",
    """CREATE TABLE IF NOT EXISTS tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT NOT NULL DEFAULT '',
        title TEXT NOT NULL,
        description TEXT NOT NULL DEFAULT '',
        status TEXT NOT NULL DEFAULT 'pending',
        priority TEXT NOT NULL DEFAULT 'medium',
        dependencies TEXT NOT NULL DEFAULT '[]',
        created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
        updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
    )""",
    """CREATE TABLE IF NOT EXISTS context (
        key TEXT NOT NULL,
        scope TEXT NOT NULL DEFAULT 'global',
        value TEXT NOT NULL DEFAULT '',
        updated_by TEXT NOT NULL DEFAULT '',
        updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
        PRIMARY KEY (key, scope)
    )""",
    "ALTER TABLE coordination_rules ADD COLUMN priority INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE coordination_rules ADD COLUMN template TEXT NOT NULL DEFAULT ''",
]


class Database:
    def __init__(self, path: str | None = None):
        self.path = path or os.environ.get("CODEX_NOTIFY_DAEMON_DB", DEFAULT_DB_PATH)

    def initialize(self) -> None:
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        conn = sqlite3.connect(self.path)
        try:
            conn.executescript("PRAGMA journal_mode=WAL;\n" + _SCHEMA)
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_events_agent ON events(agent_name)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_events_category ON events(category)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_events_session ON events(session_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_events_created ON events(created_at)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_messages_status ON messages(status)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_messages_to ON messages(to_session)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_sessions_parent ON agent_sessions(parent_session_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_tasks_session ON tasks(session_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_context_scope ON context(scope)"
            )
            # Run migrations for existing databases
            for sql in _MIGRATIONS:
                try:
                    conn.execute(sql)
                except sqlite3.OperationalError:
                    pass  # column/table already exists
            conn.commit()
        finally:
            conn.close()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def insert_event(self, data: dict) -> int:
        terminal = data.get("terminal", {})
        if isinstance(terminal, dict):
            terminal = json.dumps(terminal)
        conn = self._connect()
        try:
            cur = conn.execute(
                """INSERT INTO events (agent_name, session_id, parent_session_id,
                   category, title, message, project_cwd, git_branch, terminal,
                   work_summary)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    data.get("agent_name", ""),
                    data.get("session_id", ""),
                    data.get("parent_session_id", ""),
                    data.get("category", "completion"),
                    data.get("title", ""),
                    data.get("message", ""),
                    data.get("project_cwd", ""),
                    data.get("git_branch", ""),
                    terminal,
                    data.get("work_summary", ""),
                ),
            )
            conn.commit()
            return cur.lastrowid
        finally:
            conn.close()

    def get_event(self, event_id: int) -> dict | None:
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT * FROM events WHERE id = ?", (event_id,)
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def list_events(
        self,
        agent: str | None = None,
        category: str | None = None,
        project: str | None = None,
        since: str | None = None,
        limit: int = 50,
    ) -> list[dict]:
        clauses = []
        params: list = []
        if agent:
            clauses.append("agent_name = ?")
            params.append(agent)
        if category:
            clauses.append("category = ?")
            params.append(category)
        if project:
            clauses.append("project_cwd LIKE ?")
            params.append(f"%{project}%")
        if since:
            clauses.append("created_at >= ?")
            params.append(since)
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        limit = min(max(limit, 1), 1000)
        params.append(limit)
        conn = self._connect()
        try:
            rows = conn.execute(
                f"SELECT * FROM events{where} ORDER BY id DESC LIMIT ?", params
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def upsert_session(self, data: dict) -> None:
        session_id = data.get("session_id", "")
        if not session_id:
            return
        category = data.get("category", "completion")
        status = _STATUS_MAP.get(category, "active")
        terminal = data.get("terminal", {})
        if isinstance(terminal, dict):
            terminal = json.dumps(terminal)
        parent = data.get("parent_session_id", "")
        conn = self._connect()
        try:
            conn.execute(
                """INSERT INTO agent_sessions
                   (session_id, parent_session_id, agent_name, project_cwd,
                    git_branch, terminal, status, last_event, event_count)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
                   ON CONFLICT(session_id) DO UPDATE SET
                     agent_name  = excluded.agent_name,
                     parent_session_id = CASE WHEN excluded.parent_session_id != ''
                                              THEN excluded.parent_session_id
                                              ELSE agent_sessions.parent_session_id END,
                     project_cwd = CASE WHEN excluded.project_cwd != ''
                                        THEN excluded.project_cwd
                                        ELSE agent_sessions.project_cwd END,
                     git_branch  = CASE WHEN excluded.git_branch != ''
                                        THEN excluded.git_branch
                                        ELSE agent_sessions.git_branch END,
                     terminal    = CASE WHEN excluded.terminal != '{}'
                                        THEN excluded.terminal
                                        ELSE agent_sessions.terminal END,
                     status      = ?,
                     last_event  = excluded.last_event,
                     last_seen   = strftime('%Y-%m-%dT%H:%M:%fZ','now'),
                     ended_at    = CASE WHEN ? = 'ended'
                                        THEN strftime('%Y-%m-%dT%H:%M:%fZ','now')
                                        ELSE agent_sessions.ended_at END,
                     event_count = agent_sessions.event_count + 1
                """,
                (
                    session_id,
                    parent,
                    data.get("agent_name", ""),
                    data.get("project_cwd", ""),
                    data.get("git_branch", ""),
                    terminal,
                    status,
                    category,
                    status,
                    status,
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def heartbeat(self, session_id: str) -> bool:
        """Update last_heartbeat and last_seen for a session. Returns True if found."""
        conn = self._connect()
        try:
            conn.execute(
                """UPDATE agent_sessions
                   SET last_heartbeat = strftime('%Y-%m-%dT%H:%M:%fZ','now'),
                       last_seen = strftime('%Y-%m-%dT%H:%M:%fZ','now')
                   WHERE session_id = ?""",
                (session_id,),
            )
            conn.commit()
            return conn.total_changes > 0
        finally:
            conn.close()

    def child_sessions(self, parent_session_id: str) -> list[dict]:
        """Get all sub-agent sessions for a parent."""
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT * FROM agent_sessions WHERE parent_session_id = ? ORDER BY first_seen",
                (parent_session_id,),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def list_sessions(self, status: str | None = None) -> list[dict]:
        conn = self._connect()
        try:
            if status:
                rows = conn.execute(
                    "SELECT * FROM agent_sessions WHERE status = ? ORDER BY last_seen DESC",
                    (status,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM agent_sessions ORDER BY last_seen DESC"
                ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_session(self, session_id: str) -> dict | None:
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT * FROM agent_sessions WHERE session_id = ?", (session_id,)
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def session_events(self, session_id: str, limit: int = 50) -> list[dict]:
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT * FROM events WHERE session_id = ? ORDER BY id DESC LIMIT ?",
                (session_id, min(max(limit, 1), 1000)),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def stale_sessions(self, seconds: int = 300) -> list[dict]:
        conn = self._connect()
        try:
            # Use last_heartbeat if available, otherwise last_seen
            rows = conn.execute(
                """SELECT * FROM agent_sessions
                   WHERE status IN ('active', 'waiting')
                     AND COALESCE(NULLIF(last_heartbeat, ''), last_seen)
                         < strftime('%Y-%m-%dT%H:%M:%fZ', 'now', ? || ' seconds')
                   ORDER BY last_seen ASC""",
                (f"-{seconds}",),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    # --- Preferences ---

    def get_preference(self, key: str) -> str | None:
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT value FROM preferences WHERE key = ?", (key,)
            ).fetchone()
            return row["value"] if row else None
        finally:
            conn.close()

    def set_preference(self, key: str, value: str) -> None:
        conn = self._connect()
        try:
            conn.execute(
                """INSERT INTO preferences (key, value) VALUES (?, ?)
                   ON CONFLICT(key) DO UPDATE SET value = excluded.value""",
                (key, value),
            )
            conn.commit()
        finally:
            conn.close()

    def list_preferences(self) -> dict:
        conn = self._connect()
        try:
            rows = conn.execute("SELECT * FROM preferences ORDER BY key").fetchall()
            return {r["key"]: r["value"] for r in rows}
        finally:
            conn.close()

    def delete_preference(self, key: str) -> bool:
        conn = self._connect()
        try:
            conn.execute("DELETE FROM preferences WHERE key = ?", (key,))
            conn.commit()
            return conn.total_changes > 0
        finally:
            conn.close()

    # --- Messages (agent mesh) ---

    def insert_message(self, data: dict) -> int:
        conn = self._connect()
        try:
            cur = conn.execute(
                """INSERT INTO messages (from_session, to_session, message_type,
                   content, status)
                   VALUES (?, ?, ?, ?, ?)""",
                (
                    data.get("from_session", ""),
                    data.get("to_session", ""),
                    data.get("message_type", "handoff"),
                    data.get("content", ""),
                    data.get("status", "pending"),
                ),
            )
            conn.commit()
            return cur.lastrowid
        finally:
            conn.close()

    def get_message(self, message_id: int) -> dict | None:
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT * FROM messages WHERE id = ?", (message_id,)
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def list_messages(self, status: str | None = None, limit: int = 50) -> list[dict]:
        conn = self._connect()
        try:
            if status:
                rows = conn.execute(
                    "SELECT * FROM messages WHERE status = ? ORDER BY id DESC LIMIT ?",
                    (status, min(max(limit, 1), 1000)),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM messages ORDER BY id DESC LIMIT ?",
                    (min(max(limit, 1), 1000),),
                ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def update_message_status(
        self, message_id: int, status: str, delivered_at: str | None = None
    ) -> bool:
        conn = self._connect()
        try:
            if delivered_at:
                conn.execute(
                    "UPDATE messages SET status = ?, delivered_at = ? WHERE id = ?",
                    (status, delivered_at, message_id),
                )
            else:
                conn.execute(
                    "UPDATE messages SET status = ? WHERE id = ?",
                    (status, message_id),
                )
            conn.commit()
            return conn.total_changes > 0
        finally:
            conn.close()

    # --- Coordination rules ---

    def insert_rule(self, data: dict) -> int:
        conn = self._connect()
        try:
            cur = conn.execute(
                """INSERT INTO coordination_rules
                   (from_agent, to_agent, event_type, action, priority, template)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    data.get("from_agent", "*"),
                    data.get("to_agent", "*"),
                    data.get("event_type", "*"),
                    data.get("action", "approve"),
                    data.get("priority", 0),
                    data.get("template", ""),
                ),
            )
            conn.commit()
            return cur.lastrowid
        finally:
            conn.close()

    def list_rules(self) -> list[dict]:
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT * FROM coordination_rules ORDER BY id"
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def delete_rule(self, rule_id: int) -> bool:
        conn = self._connect()
        try:
            conn.execute("DELETE FROM coordination_rules WHERE id = ?", (rule_id,))
            conn.commit()
            return conn.total_changes > 0
        finally:
            conn.close()

    # --- Tasks ---

    def insert_task(self, data: dict) -> int:
        deps = data.get("dependencies", [])
        if isinstance(deps, list):
            deps = json.dumps(deps)
        conn = self._connect()
        try:
            cur = conn.execute(
                """INSERT INTO tasks (session_id, title, description, status,
                   priority, dependencies)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    data.get("session_id", ""),
                    data.get("title", ""),
                    data.get("description", ""),
                    data.get("status", "pending"),
                    data.get("priority", "medium"),
                    deps,
                ),
            )
            conn.commit()
            return cur.lastrowid
        finally:
            conn.close()

    def get_task(self, task_id: int) -> dict | None:
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT * FROM tasks WHERE id = ?", (task_id,)
            ).fetchone()
            if not row:
                return None
            d = dict(row)
            try:
                d["dependencies"] = json.loads(d.get("dependencies", "[]"))
            except (json.JSONDecodeError, TypeError):
                d["dependencies"] = []
            return d
        finally:
            conn.close()

    def list_tasks(
        self,
        session_id: str | None = None,
        status: str | None = None,
        limit: int = 100,
    ) -> list[dict]:
        clauses = []
        params: list = []
        if session_id:
            clauses.append("session_id = ?")
            params.append(session_id)
        if status:
            clauses.append("status = ?")
            params.append(status)
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        limit = min(max(limit, 1), 1000)
        params.append(limit)
        conn = self._connect()
        try:
            rows = conn.execute(
                f"SELECT * FROM tasks{where} ORDER BY priority = 'high' DESC, "
                f"priority = 'medium' DESC, id ASC LIMIT ?",
                params,
            ).fetchall()
            result = []
            for r in rows:
                d = dict(r)
                try:
                    d["dependencies"] = json.loads(d.get("dependencies", "[]"))
                except (json.JSONDecodeError, TypeError):
                    d["dependencies"] = []
                result.append(d)
            return result
        finally:
            conn.close()

    def update_task(self, task_id: int, data: dict) -> bool:
        sets = ["updated_at = strftime('%Y-%m-%dT%H:%M:%fZ','now')"]
        params: list = []
        for field in ("title", "description", "status", "priority", "session_id"):
            if field in data:
                sets.append(f"{field} = ?")
                params.append(data[field])
        if "dependencies" in data:
            deps = data["dependencies"]
            if isinstance(deps, list):
                deps = json.dumps(deps)
            sets.append("dependencies = ?")
            params.append(deps)
        params.append(task_id)
        conn = self._connect()
        try:
            conn.execute(
                f"UPDATE tasks SET {', '.join(sets)} WHERE id = ?", params
            )
            conn.commit()
            return conn.total_changes > 0
        finally:
            conn.close()

    def delete_task(self, task_id: int) -> bool:
        conn = self._connect()
        try:
            conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
            conn.commit()
            return conn.total_changes > 0
        finally:
            conn.close()

    def next_task(self, session_id: str | None = None) -> dict | None:
        """Find the next actionable task: pending, with all dependencies done."""
        # Get ALL done task IDs (cross-session) for dependency resolution
        all_tasks = self.list_tasks(limit=1000)
        done_ids = {t["id"] for t in all_tasks if t["status"] == "done"}
        # Get candidate tasks (filtered by session if specified)
        candidates = self.list_tasks(session_id=session_id, limit=500)
        for t in candidates:
            if t["status"] != "pending":
                continue
            deps = t.get("dependencies", [])
            if all(d in done_ids for d in deps):
                return t
        return None

    # --- Context (shared variables) ---

    def set_context(self, key: str, value: str, scope: str = "global", updated_by: str = "") -> None:
        conn = self._connect()
        try:
            conn.execute(
                """INSERT INTO context (key, scope, value, updated_by)
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT(key, scope) DO UPDATE SET
                     value = excluded.value,
                     updated_by = excluded.updated_by,
                     updated_at = strftime('%Y-%m-%dT%H:%M:%fZ','now')""",
                (key, scope, value, updated_by),
            )
            conn.commit()
        finally:
            conn.close()

    def get_context(self, key: str, scope: str = "global") -> dict | None:
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT * FROM context WHERE key = ? AND scope = ?",
                (key, scope),
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def list_context(self, scope: str | None = None) -> list[dict]:
        conn = self._connect()
        try:
            if scope:
                rows = conn.execute(
                    "SELECT * FROM context WHERE scope = ? ORDER BY key",
                    (scope,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM context ORDER BY scope, key"
                ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def delete_context(self, key: str, scope: str = "global") -> bool:
        conn = self._connect()
        try:
            conn.execute(
                "DELETE FROM context WHERE key = ? AND scope = ?",
                (key, scope),
            )
            conn.commit()
            return conn.total_changes > 0
        finally:
            conn.close()

    def match_rule(self, from_agent: str, to_agent: str, event_type: str) -> dict:
        """Find the most specific matching coordination rule. Returns full rule dict."""
        conn = self._connect()
        try:
            # Most specific first: exact match > wildcard
            for fa, ta, et in [
                (from_agent, to_agent, event_type),
                (from_agent, to_agent, "*"),
                (from_agent, "*", event_type),
                ("*", to_agent, event_type),
                (from_agent, "*", "*"),
                ("*", to_agent, "*"),
                ("*", "*", event_type),
                ("*", "*", "*"),
            ]:
                row = conn.execute(
                    """SELECT * FROM coordination_rules
                       WHERE from_agent = ? AND to_agent = ? AND event_type = ?
                       ORDER BY priority DESC
                       LIMIT 1""",
                    (fa, ta, et),
                ).fetchone()
                if row:
                    return dict(row)
            return {"action": "approve", "template": "", "priority": 0}
        finally:
            conn.close()

    def match_rules_for_event(self, agent_name: str, event_type: str) -> list[dict]:
        """Find all rules matching an agent's event. Used for after-work routing."""
        conn = self._connect()
        try:
            rows = conn.execute(
                """SELECT * FROM coordination_rules
                   WHERE (from_agent = ? OR from_agent = '*')
                     AND (event_type = ? OR event_type = '*')
                   ORDER BY priority DESC, id ASC""",
                (agent_name, event_type),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()
