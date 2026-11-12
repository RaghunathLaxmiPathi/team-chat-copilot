"""In-app notifications and the email outbox (FR-26, DD-24). Never holds message text (PRV-04)."""
from app import clock
from app.errors import NotFound
from app.ids import new_id


class NotificationService:
    def __init__(self, db, hub):
        self.db = db
        self.hub = hub

    def create(self, user_id: str, ntype: str, conversation_id: str, actor_id: str, message_id: str | None = None) -> str:
        """Call inside the caller's transaction. Push with deliver() after the commit."""
        nid = new_id()
        if self.db.scalar("SELECT is_bot FROM users WHERE id = ?", (user_id,)):
            return None  # the assistant has no inbox and no email
        now = clock.iso()
        self.db.exec(
            "INSERT INTO notifications (id, user_id, type, conversation_id, actor_id, message_id, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (nid, user_id, ntype, conversation_id, actor_id, message_id, now),
        )
        if not self.hub.is_online(user_id):
            # Lab stub: queued and never sent. A real sender plugs in behind the outbox (risk R-13).
            self.db.exec(
                "INSERT INTO notification_outbox (id, user_id, channel, type, conversation_id, actor_id, created_at) "
                "VALUES (?, ?, 'email', ?, ?, ?, ?)",
                (new_id(), user_id, ntype, conversation_id, actor_id, now),
            )
        return nid

    _SELECT = (
        "SELECT n.id, n.user_id, n.type, n.conversation_id, n.actor_id, n.message_id, n.created_at, n.read_at, "
        "a.display_name AS actor_name, c.name AS cname, c.type AS ctype "
        "FROM notifications n JOIN users a ON a.id = n.actor_id JOIN conversations c ON c.id = n.conversation_id"
    )

    @staticmethod
    def _dict(row: dict) -> dict:
        return {
            "id": row["id"],
            "type": row["type"],
            "conversation_id": row["conversation_id"],
            "conversation_name": row["actor_name"] if row["ctype"] == "dm" else row["cname"],
            "actor_id": row["actor_id"],
            "actor_name": row["actor_name"],
            "message_id": row["message_id"],
            "created_at": row["created_at"],
            "read": row["read_at"] is not None,
        }

    def deliver(self, ids: list[str]) -> None:
        for nid in ids:
            if nid is None:
                continue
            row = self.db.q_one(self._SELECT + " WHERE n.id = ?", (nid,))
            if row:
                self.hub.publish_to_users([row["user_id"]], {"type": "notification", "notification": self._dict(row)})

    def list_for(self, user_id: str, unread_only: bool = False) -> dict:
        sql = self._SELECT + " WHERE n.user_id = ?"
        if unread_only:
            sql += " AND n.read_at IS NULL"
        sql += " ORDER BY n.created_at DESC, n.rowid DESC LIMIT 100"
        rows = self.db.q_all(sql, (user_id,))
        unread = self.db.scalar(
            "SELECT COUNT(*) FROM notifications WHERE user_id = ? AND read_at IS NULL", (user_id,)
        )
        return {"notifications": [self._dict(r) for r in rows], "unread_count": unread}

    def mark_read(self, user_id: str, notification_id: str) -> dict:
        row = self.db.q_one(self._SELECT + " WHERE n.id = ? AND n.user_id = ?", (notification_id, user_id))
        if not row:
            raise NotFound()
        if row["read_at"] is None:
            now = clock.iso()
            self.db.exec("UPDATE notifications SET read_at = ? WHERE id = ?", (now, notification_id))
            row["read_at"] = now
        return self._dict(row)
