"""Asyncio HTTP server with manual HTTP/1.1 parsing.

Serves the API, SSE streams, and the web dashboard.
"""

import asyncio
import json
import mimetypes
import os
import signal
import sys
import time
from pathlib import Path
from urllib.parse import urlparse, parse_qs

from .db import Database
from .monitor import Monitor
from .pid import write_pid, remove_pid
from .routes import Router
from .sse import SSERegistry

STATIC_DIR = Path(__file__).parent / "static"

_STATUS_TEXT = {
    200: "OK",
    201: "Created",
    400: "Bad Request",
    404: "Not Found",
    405: "Method Not Allowed",
    500: "Internal Server Error",
}


class HttpServer:
    def __init__(self, port: int = 7878, db_path: str | None = None):
        self.port = port
        self.db = Database(db_path)
        self.sse = SSERegistry()
        self.start_time = time.time()
        self.monitor = Monitor(self.db, self.sse)
        self.router = Router(self.db, self.sse, self.monitor, self.start_time)
        self._server: asyncio.AbstractServer | None = None

    async def start(self) -> None:
        self.db.initialize()
        write_pid()
        self.sse.start()
        self.monitor.start()

        try:
            self._server = await asyncio.start_server(
                self._handle_connection, "127.0.0.1", self.port
            )
        except OSError as e:
            remove_pid()
            if "Address already in use" in str(e) or e.errno == 48:
                print(
                    f"agent-notify daemon: port {self.port} already in use. "
                    f"Another daemon may be running, or use CODEX_NOTIFY_DAEMON_PORT "
                    f"to pick a different port.",
                    file=sys.stderr,
                )
                sys.exit(1)
            raise

        loop = asyncio.get_running_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, lambda: asyncio.ensure_future(self.stop()))

        print(
            f"agent-notify daemon listening on http://127.0.0.1:{self.port}",
            file=sys.stderr,
        )

        async with self._server:
            await self._server.serve_forever()

    async def stop(self) -> None:
        print("agent-notify daemon shutting down...", file=sys.stderr)
        await self.monitor.stop()
        await self.sse.stop()
        if self._server:
            self._server.close()
            await self._server.wait_closed()
        remove_pid()
        asyncio.get_running_loop().stop()

    async def _handle_connection(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        try:
            request = await self._read_request(reader)
            if request is None:
                writer.close()
                return

            # Handle CORS preflight
            if request["method"] == "OPTIONS":
                self._write_response(writer, 200, "")
                await writer.drain()
                writer.close()
                return

            result = await self.router.dispatch(request)

            if result is None:
                # SSE: router signals writer ownership
                await self.sse.register(writer)
                return

            # Serve static file
            if result.get("serve_static"):
                await self._serve_static(writer, result["serve_static"])
                return

            status = result.get("status", 200)
            body = result.get("body", {})
            self._write_response(writer, status, json.dumps(body))
            await writer.drain()
        except (ConnectionResetError, BrokenPipeError):
            pass
        except Exception as e:
            try:
                self._write_response(
                    writer, 500, json.dumps({"error": str(e)})
                )
                await writer.drain()
            except Exception:
                pass
        finally:
            if writer and not writer.is_closing():
                try:
                    writer.close()
                except Exception:
                    pass

    async def _serve_static(
        self, writer: asyncio.StreamWriter, filename: str
    ) -> None:
        filepath = STATIC_DIR / filename
        if not filepath.is_file():
            self._write_response(writer, 404, '{"error":"not found"}')
            await writer.drain()
            return

        content = filepath.read_bytes()
        content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
        header = (
            f"HTTP/1.1 200 OK\r\n"
            f"Content-Type: {content_type}\r\n"
            f"Content-Length: {len(content)}\r\n"
            f"Cache-Control: no-cache\r\n"
            f"Connection: close\r\n"
            f"\r\n"
        )
        writer.write(header.encode() + content)
        await writer.drain()

    async def _read_request(self, reader: asyncio.StreamReader) -> dict | None:
        try:
            request_line = await asyncio.wait_for(
                reader.readline(), timeout=10
            )
        except (asyncio.TimeoutError, ConnectionResetError):
            return None

        if not request_line:
            return None

        try:
            line = request_line.decode().strip()
            parts = line.split(" ", 2)
            if len(parts) < 2:
                return None
            method = parts[0].upper()
            raw_path = parts[1]
        except (UnicodeDecodeError, IndexError):
            return None

        # Parse path and query string
        parsed = urlparse(raw_path)
        path = parsed.path.rstrip("/") or "/"
        query = {}
        for k, v in parse_qs(parsed.query).items():
            query[k] = v[0] if len(v) == 1 else v

        # Read headers
        headers = {}
        while True:
            try:
                header_line = await asyncio.wait_for(
                    reader.readline(), timeout=5
                )
            except (asyncio.TimeoutError, ConnectionResetError):
                break
            if header_line in (b"\r\n", b"\n", b""):
                break
            try:
                decoded = header_line.decode().strip()
                if ":" in decoded:
                    key, val = decoded.split(":", 1)
                    headers[key.strip().lower()] = val.strip()
            except UnicodeDecodeError:
                continue

        # Read body if Content-Length present
        body = {}
        content_length = int(headers.get("content-length", 0))
        if content_length > 0:
            try:
                raw = await asyncio.wait_for(
                    reader.readexactly(content_length), timeout=10
                )
                body = json.loads(raw.decode())
            except (asyncio.TimeoutError, json.JSONDecodeError, UnicodeDecodeError):
                body = {}

        return {
            "method": method,
            "path": path,
            "query": query,
            "headers": headers,
            "body": body,
        }

    def _write_response(
        self, writer: asyncio.StreamWriter, status: int, body: str
    ) -> None:
        status_text = _STATUS_TEXT.get(status, "Unknown")
        body_bytes = body.encode()
        header = (
            f"HTTP/1.1 {status} {status_text}\r\n"
            f"Content-Type: application/json\r\n"
            f"Content-Length: {len(body_bytes)}\r\n"
            f"Access-Control-Allow-Origin: *\r\n"
            f"Access-Control-Allow-Methods: GET, POST, PUT, DELETE, OPTIONS\r\n"
            f"Access-Control-Allow-Headers: Content-Type\r\n"
            f"Connection: close\r\n"
            f"\r\n"
        )
        writer.write(header.encode() + body_bytes)
