"""Entry point: python3 -m daemon --serve --port PORT"""

import argparse
import asyncio
import os
import sys

from .server import HttpServer

DEFAULT_PORT = 7878


def main() -> None:
    parser = argparse.ArgumentParser(description="agent-notify daemon")
    parser.add_argument(
        "--serve", action="store_true", help="Start the HTTP server"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("CODEX_NOTIFY_DAEMON_PORT", DEFAULT_PORT)),
        help=f"Port to listen on (default: {DEFAULT_PORT})",
    )
    parser.add_argument(
        "--db",
        type=str,
        default=os.environ.get("CODEX_NOTIFY_DAEMON_DB"),
        help="Database file path (default: ~/.codex/daemon.db)",
    )
    args = parser.parse_args()

    if not args.serve:
        parser.print_help()
        sys.exit(1)

    server = HttpServer(port=args.port, db_path=args.db)
    try:
        asyncio.run(server.start())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
