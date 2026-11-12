"""Real-time channel: connections, per-connection queues, resume, delivery confirmation.

Everything here runs on the event loop thread, so the methods that publish events are
plain (non-async) functions and never block (DD-01, DD-06).
"""
import asyncio
import logging
import re
from contextlib import suppress

from app import access, clock
from app.access import visible_sql, visible_params
from app.ids import new_id
from app.serializers import MESSAGE_SELECT

log = logging.getLogger("chatapp.hub")

_CLOSE = object()
_TIME_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$")

CLOSE_EXPIRED = 4401
CLOSE_DEACTIVATED = 4403
CLOSE_QUEUE_FULL = 4408


class Connection:
    def __init__(self, ws, user_id: str, exp_epoch: float, queue_size: int):
        self.id = new_id()
        self.ws = ws
        self.user_id = user_id
        self.exp_epoch = exp_epoch
        self.queue: asyncio.Queue = asyncio.Queue(maxsize=queue_size)
        self.close_code: int | None = None
        self.pending: dict[str, float] = {}  # message id -> server receive time (monotonic)


class ConnectionHub:
    def __init__(self, db, settings, slo):
        self.db = db
        self.settings = settings
        self.slo = slo
        self.messages = None  # set after construction (MessageService)
        self.conversations = None  # set after construction (ConversationService)
        self._conns: dict[str, Connection] = {}
        self._by_user: dict[str, set[str]] = {}
        self.deliveries_confirmed = 0
        self.deliveries_timed_out = 0

    # --- connection lifecycle -------------------------------------------
    def register(self, ws, user_id: str, exp_epoch: float) -> Connection:
        conn = Connection(ws, user_id, exp_epoch, self.settings.queue_size)
        self._conns[conn.id] = conn
        self._by_user.setdefault(user_id, set()).add(conn.id)
        log.info("connected", extra={"event": "ws_connect", "conn_id": conn.id, "user_id": user_id})
        return conn

    def unregister(self, conn: Connection) -> None:
        self._conns.pop(conn.id, None)
        ids = self._by_user.get(conn.user_id)
        if ids:
            ids.discard(conn.id)
            if not ids:
                del self._by_user[conn.user_id]
        log.info("disconnected", extra={"event": "ws_disconnect", "conn_id": conn.id,
                                        "user_id": conn.user_id, "code": conn.close_code})

    def is_online(self, user_id: str) -> bool:
        return bool(self._by_user.get(user_id))

    def connection_count(self) -> int:
        return len(self._conns)

    def stats(self) -> dict:
        return {
            "connections": len(self._conns),
            "deliveries_confirmed": self.deliveries_confirmed,
            "deliveries_timed_out": self.deliveries_timed_out,
        }

    async def run_writer(self, conn: Connection) -> None:
        """Sends queued frames in order. A slow client only slows itself (DD-01)."""
        try:
            while True:
                item = await conn.queue.get()
                if item is _CLOSE:
                    with suppress(Exception):
                        await conn.ws.close(code=conn.close_code or 1000)
                    return
                await conn.ws.send_json(item)
        except Exception:
            return  # client went away; the reader loop will notice

    # --- sending ----------------------------------------------------------
    def enqueue(self, conn: Connection, frame: dict) -> bool:
        if conn.close_code is not None:
            return False
        try:
            conn.queue.put_nowait(frame)
            return True
        except asyncio.QueueFull:
            self.force_close(conn, CLOSE_QUEUE_FULL)
            return False

    def force_close(self, conn: Connection, code: int) -> None:
        if conn.close_code is not None:
            return
        conn.close_code = code
        while not conn.queue.empty():
            conn.queue.get_nowait()
        conn.queue.put_nowait(_CLOSE)
        log.info("closing", extra={"event": "ws_close", "conn_id": conn.id, "user_id": conn.user_id, "code": code})

    def publish_to_users(self, user_ids, frame: dict) -> None:
        for uid in user_ids:
            for cid in list(self._by_user.get(uid, ())):
                conn = self._conns.get(cid)
                if conn:
                    self.enqueue(conn, frame)

    def publish_message(self, message: dict, member_ids, t0: float | None = None) -> None:
        """Push a stored message to every open connection of every current member."""
        frame = {"type": "message", "message": message}
        t0 = clock.monotonic() if t0 is None else t0
        for uid in member_ids:
            for cid in list(self._by_user.get(uid, ())):
                conn = self._conns.get(cid)
                if conn is None:
                    continue
                if self.enqueue(conn, frame) and uid != message["sender_id"]:
                    conn.pending[message["id"]] = t0

    def disconnect_user(self, user_id: str, code: int = CLOSE_DEACTIVATED) -> None:
        for cid in list(self._by_user.get(user_id, ())):
            conn = self._conns.get(cid)
            if conn:
                self.force_close(conn, code)

    # --- delivery confirmation (SLO-02) ----------------------------------
    def handle_ack(self, conn: Connection, message_id: str) -> None:
        t0 = conn.pending.pop(message_id, None)
        if t0 is None:
            return
        self.slo.record_latency_ms((clock.monotonic() - t0) * 1000.0)
        self.deliveries_confirmed += 1

    def sweep(self, now_monotonic: float | None = None, now_epoch: float | None = None) -> None:
        """Count unconfirmed deliveries as slowest-bucket samples and close expired sessions."""
        now_m = clock.monotonic() if now_monotonic is None else now_monotonic
        now_e = clock.epoch() if now_epoch is None else now_epoch
        for conn in list(self._conns.values()):
            for mid, t0 in list(conn.pending.items()):
                if now_m - t0 > self.settings.ack_timeout_s:
                    del conn.pending[mid]
                    self.slo.record_latency_ms(float("inf"))
                    self.deliveries_timed_out += 1
            if conn.exp_epoch <= now_e:
                self.force_close(conn, CLOSE_EXPIRED)

    # --- resume (FR-45, DD-12) --------------------------------------------
    def resume(self, conn: Connection, cursors: dict, since: str | None) -> None:
        # Taken before any reading, so a deletion during the resume is never missed (AR-04).
        server_time = clock.iso()
        user_id = conn.user_id
        current = self.conversations.ids_for_user(user_id)
        for cid, last in cursors.items():
            if cid not in current:
                continue
            msgs, has_more = self.messages.page_after(user_id, cid, int(last), self.settings.page_size)
            if msgs:
                self.enqueue(conn, {"type": "resume_page", "conversation_id": cid,
                                    "messages": msgs, "has_more": has_more})
        deleted = []
        if since:
            rows = self.db.q_all(
                "SELECT m.id, m.conversation_id FROM messages m WHERE m.deleted_at >= ? AND "
                + visible_sql("m"),
                (since,) + visible_params(user_id),
            )
            deleted = [{"conversation_id": r["conversation_id"], "message_id": r["id"]} for r in rows]
        self.enqueue(conn, {"type": "resume_done", "server_time": server_time, "deleted": deleted})

    @staticmethod
    def valid_time(value) -> bool:
        return isinstance(value, str) and bool(_TIME_RE.match(value))
