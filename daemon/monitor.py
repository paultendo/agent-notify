"""Background monitor for stuck agent detection with graduated escalation.

Uses a graduated stall counter with hysteresis — inspired by Magentic-One's
two-loop architecture. Instead of a single alert, the monitor escalates through
severity levels:

  Level 0: Normal — agent producing events
  Level 1: Stale  — no events for STALE_THRESHOLD (2 min). Broadcast warning.
  Level 2: Stuck  — no events for STUCK_THRESHOLD (5 min). Broadcast alert.
  Level 3: Dead   — no events for DEAD_THRESHOLD (15 min). Broadcast critical.

Hysteresis: a single new event resets the counter to 0, preventing flapping.
"""

import asyncio

from .db import Database
from .sse import SSERegistry

# Thresholds in seconds
STALE_THRESHOLD = 120
STUCK_THRESHOLD = 300
DEAD_THRESHOLD = 900
# Check every 30 seconds for more responsive escalation
CHECK_INTERVAL = 30


class Monitor:
    def __init__(self, db: Database, sse: SSERegistry, threshold: int = STUCK_THRESHOLD):
        self.db = db
        self.sse = sse
        self.threshold = threshold
        self._task: asyncio.Task | None = None
        # Track escalation level per session: session_id -> level (0-3)
        self._levels: dict[str, int] = {}

    def start(self) -> None:
        if self._task is None:
            self._task = asyncio.ensure_future(self._loop())

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    async def _loop(self) -> None:
        while True:
            await asyncio.sleep(CHECK_INTERVAL)
            try:
                await self._check()
            except Exception:
                pass  # monitor should never crash the daemon

    async def _check(self) -> None:
        """Check all active sessions and escalate/de-escalate as needed."""
        # Check stale at each threshold level
        for level, threshold, alert_type, severity in [
            (1, STALE_THRESHOLD, "stale_agent", "warning"),
            (2, STUCK_THRESHOLD, "stuck_agent", "alert"),
            (3, DEAD_THRESHOLD, "dead_agent", "critical"),
        ]:
            stale = self.db.stale_sessions(threshold)
            for session in stale:
                sid = session["session_id"]
                current_level = self._levels.get(sid, 0)

                # Only escalate, never repeat the same level
                if current_level >= level:
                    continue

                self._levels[sid] = level
                await self.sse.broadcast({
                    "type": "alert",
                    "alert_type": alert_type,
                    "severity": severity,
                    "level": level,
                    "session_id": sid,
                    "agent_name": session.get("agent_name", ""),
                    "project_cwd": session.get("project_cwd", ""),
                    "status": session.get("status", ""),
                    "last_seen": session.get("last_seen", ""),
                    "message": _alert_message(session, level),
                })

    def clear_alert(self, session_id: str) -> None:
        """Reset escalation level when agent produces new activity (hysteresis)."""
        if session_id in self._levels:
            del self._levels[session_id]

    def get_level(self, session_id: str) -> int:
        """Get current escalation level for a session."""
        return self._levels.get(session_id, 0)


def _alert_message(session: dict, level: int) -> str:
    agent = session.get("agent_name", "Agent")
    project = session.get("project_cwd", "?")
    if level == 1:
        return f"{agent} in {project} may be stalling (no recent output)"
    if level == 2:
        return f"{agent} in {project} appears stuck (no output for 5+ min)"
    if level == 3:
        return f"{agent} in {project} appears dead (no output for 15+ min)"
    return f"{agent} in {project} status unknown"
