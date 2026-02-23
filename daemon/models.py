"""Dataclasses for daemon events, agent sessions, and mesh messages."""

from dataclasses import dataclass, field, asdict


@dataclass
class Terminal:
    bundle_id: str = ""
    multiplexer: str = ""
    tmux_socket: str = ""
    tmux_pane: str = ""
    kitty_window_id: str = ""
    kitty_socket: str = ""
    wezterm_pane: str = ""
    wezterm_socket: str = ""
    zellij_session: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Terminal":
        if not data or not isinstance(data, dict):
            return cls()
        known = {f.name for f in cls.__dataclass_fields__.values()}
        return cls(**{k: str(v) for k, v in data.items() if k in known})


@dataclass
class Event:
    agent_name: str = ""
    session_id: str = ""
    category: str = "completion"
    title: str = ""
    message: str = ""
    project_cwd: str = ""
    git_branch: str = ""
    terminal: Terminal = field(default_factory=Terminal)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["terminal"] = self.terminal.to_dict()
        return d

    @classmethod
    def from_dict(cls, data: dict) -> "Event":
        if not data or not isinstance(data, dict):
            return cls()
        terminal_data = data.get("terminal", {})
        if isinstance(terminal_data, str):
            import json
            try:
                terminal_data = json.loads(terminal_data)
            except (json.JSONDecodeError, TypeError):
                terminal_data = {}
        known = {f.name for f in cls.__dataclass_fields__.values()} - {"terminal"}
        kwargs = {k: v for k, v in data.items() if k in known}
        kwargs["terminal"] = Terminal.from_dict(terminal_data)
        return cls(**kwargs)


@dataclass
class Message:
    """Agent-to-agent mesh message."""
    from_session: str = ""
    to_session: str = ""
    message_type: str = "handoff"  # handoff, context, command
    content: str = ""
    status: str = "pending"  # pending, approved, delivered, rejected

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Message":
        if not data or not isinstance(data, dict):
            return cls()
        known = {f.name for f in cls.__dataclass_fields__.values()}
        return cls(**{k: v for k, v in data.items() if k in known})


@dataclass
class CoordinationRule:
    """Rule governing agent-to-agent message delivery."""
    from_agent: str = "*"   # agent name or * for any
    to_agent: str = "*"     # agent name or * for any
    event_type: str = "*"   # message_type or * for any
    action: str = "approve"  # auto, approve, block

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "CoordinationRule":
        if not data or not isinstance(data, dict):
            return cls()
        known = {f.name for f in cls.__dataclass_fields__.values()}
        return cls(**{k: v for k, v in data.items() if k in known})
