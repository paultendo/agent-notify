"""PID file management for the daemon process."""

import os
import signal
import time
from pathlib import Path

PID_DIR = os.path.join(Path.home(), ".codex")
PID_FILE = os.path.join(PID_DIR, "daemon.pid")


def write_pid() -> None:
    os.makedirs(PID_DIR, exist_ok=True)
    with open(PID_FILE, "w") as f:
        f.write(str(os.getpid()))


def read_pid() -> int | None:
    try:
        with open(PID_FILE) as f:
            return int(f.read().strip())
    except (FileNotFoundError, ValueError):
        return None


def is_running() -> bool:
    pid = read_pid()
    if pid is None:
        return False
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        # Stale PID file
        remove_pid()
        return False
    except PermissionError:
        return True


def remove_pid() -> None:
    try:
        os.remove(PID_FILE)
    except FileNotFoundError:
        pass


def stop_daemon() -> bool:
    pid = read_pid()
    if pid is None:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        remove_pid()
        return False
    except PermissionError:
        return False

    # Send SIGTERM
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        remove_pid()
        return True

    # Poll for up to 2 seconds
    for _ in range(20):
        time.sleep(0.1)
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            remove_pid()
            return True

    # SIGKILL fallback
    try:
        os.kill(pid, signal.SIGKILL)
        time.sleep(0.2)
    except ProcessLookupError:
        pass
    remove_pid()
    return True
