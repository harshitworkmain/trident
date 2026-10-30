"""WebSocket fan-out hub.

Best-effort by design: clients load a REST snapshot, then apply events; every event carries a
per-topic `seq`, and a client that sees a gap (or reconnects) reloads the snapshot. Publishing is
thread-safe, so sync request handlers and jobs can publish into the event loop.
"""

from __future__ import annotations

import asyncio
import json
import logging
import threading
from dataclasses import dataclass, field
from typing import Dict, Optional, Set

from fastapi import WebSocket

from .db import iso, utcnow
from .observability import METRICS

logger = logging.getLogger('trident.realtime')
TOPICS = ('sos', 'alerts', 'devices', 'weather', 'rov', 'system')
QUEUE_MAX = 500          # a client this far behind is dropped; it will reconnect and resync
MAX_SOCKETS_PER_USER = 10
RECHECK_S = 30           # an open socket re-checks its account (deactivated / demoted users lose it)


@dataclass(eq=False)
class Client:
    ws: WebSocket
    user: str
    topics: Set[str] = field(default_factory=lambda: set(TOPICS))
    queue: asyncio.Queue = field(default_factory=lambda: asyncio.Queue(QUEUE_MAX))


class Hub:
    def __init__(self):
        self.clients: Set[Client] = set()
        self.seq: Dict[str, int] = {t: 0 for t in TOPICS}
        self.lock = threading.Lock()
        self.loop: Optional[asyncio.AbstractEventLoop] = None

    def bind(self, loop: asyncio.AbstractEventLoop) -> None:
        self.loop = loop

    def publish(self, topic: str, data: dict) -> None:
        """Callable from any thread."""
        with self.lock:
            self.seq[topic] += 1
            msg = json.dumps({'type': 'event', 'topic': topic, 'seq': self.seq[topic], 'ts': iso(utcnow()),
                              'data': data}, default=str)
        if self.loop is None or self.loop.is_closed():
            return
        try:
            running = asyncio.get_running_loop()
        except RuntimeError:
            running = None
        if running is self.loop:
            self._fan_out(topic, msg)
        else:
            self.loop.call_soon_threadsafe(self._fan_out, topic, msg)

    def _fan_out(self, topic: str, msg: str) -> None:
        for c in list(self.clients):
            if topic in c.topics:
                try:
                    c.queue.put_nowait(msg)
                except asyncio.QueueFull:
                    logger.warning('dropping slow websocket client %s', c.user)
                    self.clients.discard(c)
                    asyncio.ensure_future(c.ws.close(code=1013))

    def disconnect_user(self, user: str) -> None:
        """Close every socket of a user (deactivation, role change, logout). Callable from any thread."""
        def close():
            for c in [c for c in self.clients if c.user == user]:
                self.clients.discard(c)
                asyncio.ensure_future(c.ws.close(code=4401))
        if self.loop is not None and not self.loop.is_closed():
            self.loop.call_soon_threadsafe(close)

    async def serve(self, ws: WebSocket, user: str, still_valid=None) -> None:
        if sum(c.user == user for c in self.clients) >= MAX_SOCKETS_PER_USER:
            await ws.close(code=4429)
            return
        client = Client(ws, user)
        self.clients.add(client)
        METRICS.set_gauge('ws_clients', len(self.clients))
        await ws.send_text(json.dumps({'type': 'hello', 'server_time': iso(utcnow()), 'topics': list(TOPICS),
                                       'seq': dict(self.seq)}))
        sender = asyncio.create_task(self._sender(client))
        watchdog = asyncio.create_task(self._watch(client, still_valid)) if still_valid else None
        try:
            while True:
                raw = await ws.receive_text()
                try:
                    msg = json.loads(raw)
                except ValueError:
                    continue
                if msg.get('type') == 'subscribe' and isinstance(msg.get('topics'), list):
                    client.topics = {t for t in msg['topics'] if t in TOPICS}
                elif msg.get('type') == 'ping':
                    await client.queue.put(json.dumps({'type': 'pong', 'server_time': iso(utcnow())}))
        except Exception:
            pass                                       # disconnects end the receive loop
        finally:
            sender.cancel()
            if watchdog:
                watchdog.cancel()
            self.clients.discard(client)
            METRICS.set_gauge('ws_clients', len(self.clients))

    async def _watch(self, client: Client, still_valid) -> None:
        try:
            while True:
                await asyncio.sleep(RECHECK_S)
                if not await asyncio.to_thread(still_valid):
                    self.clients.discard(client)
                    await client.ws.close(code=4401)
                    return
        except asyncio.CancelledError:
            pass
        except Exception:
            pass

    @staticmethod
    async def _sender(client: Client) -> None:
        try:
            while True:
                await client.ws.send_text(await client.queue.get())
        except Exception:
            pass


HUB = Hub()
