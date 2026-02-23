"""Server-Sent Events client registry and broadcast."""

import asyncio
import json


class SSERegistry:
    def __init__(self):
        self._clients: list[asyncio.StreamWriter] = []
        self._lock = asyncio.Lock()
        self._keepalive_task: asyncio.Task | None = None

    def start(self) -> None:
        if self._keepalive_task is None:
            self._keepalive_task = asyncio.ensure_future(self._keepalive_loop())

    async def stop(self) -> None:
        if self._keepalive_task:
            self._keepalive_task.cancel()
            try:
                await self._keepalive_task
            except asyncio.CancelledError:
                pass
            self._keepalive_task = None
        async with self._lock:
            for writer in self._clients:
                try:
                    writer.close()
                except Exception:
                    pass
            self._clients.clear()

    @property
    def client_count(self) -> int:
        return len(self._clients)

    async def register(self, writer: asyncio.StreamWriter) -> None:
        """Send SSE headers and hold the connection open until disconnect."""
        header = (
            "HTTP/1.1 200 OK\r\n"
            "Content-Type: text/event-stream\r\n"
            "Cache-Control: no-cache\r\n"
            "Connection: keep-alive\r\n"
            "Access-Control-Allow-Origin: *\r\n"
            "\r\n"
        )
        writer.write(header.encode())
        await writer.drain()

        async with self._lock:
            self._clients.append(writer)

        # Block until client disconnects
        try:
            while True:
                await asyncio.sleep(1)
                if writer.is_closing():
                    break
        except (ConnectionResetError, BrokenPipeError, asyncio.CancelledError):
            pass
        finally:
            async with self._lock:
                if writer in self._clients:
                    self._clients.remove(writer)

    async def broadcast(self, event: dict) -> None:
        data = json.dumps(event)
        payload = f"event: notification\ndata: {data}\n\n".encode()
        dead: list[asyncio.StreamWriter] = []
        async with self._lock:
            for writer in self._clients:
                try:
                    writer.write(payload)
                    await writer.drain()
                except (ConnectionResetError, BrokenPipeError, OSError):
                    dead.append(writer)
            for writer in dead:
                self._clients.remove(writer)
                try:
                    writer.close()
                except Exception:
                    pass

    async def _keepalive_loop(self) -> None:
        while True:
            await asyncio.sleep(15)
            payload = b": keepalive\n\n"
            dead: list[asyncio.StreamWriter] = []
            async with self._lock:
                for writer in self._clients:
                    try:
                        writer.write(payload)
                        await writer.drain()
                    except (ConnectionResetError, BrokenPipeError, OSError):
                        dead.append(writer)
                for writer in dead:
                    self._clients.remove(writer)
                    try:
                        writer.close()
                    except Exception:
                        pass
