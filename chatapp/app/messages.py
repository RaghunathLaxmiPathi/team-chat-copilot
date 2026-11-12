"""Sending, ordering, threads, deletion, and paging (FR-20 to FR-29, FR-41 to FR-46)."""
import re

from app import access, clock
from app.access import visible_params, visible_sql
from app.errors import Conflict, Forbidden, NotFound, RateLimited, ValidationFailed
from app.ids import new_id
from app.serializers import MESSAGE_SELECT, hydrate_messages

MENTION_RE = re.compile(r"(?<![\w@])@([A-Za-z0-9._-]{3,32})")
MAX_MENTIONS = 20


class MessageService:
    def __init__(self, db, settings, conversations, attachments, notifications, rate, hub):
        self.db = db
        self.settings = settings
        self.conversations = conversations
        self.attachments = attachments
        self.notifications = notifications
        self.rate = rate
        self.hub = hub
        self.assistant = None  # set after construction (CopilotService)

    # --- reading ------------------------------------------------------------
    def _by_id(self, message_id: str) -> dict | None:
        return self.db.q_one(MESSAGE_SELECT + " WHERE m.id = ?", (message_id,))

    def _visible_row(self, user_id: str, message_id: str) -> dict:
        row = self._by_id(message_id)
        if not row or not access.can_see(self.db, user_id, row["conversation_id"], row["seq"]):
            raise NotFound()
        return row

    def _page(self, user_id: str, cid: str, where: str, params: tuple, order: str, limit: int) -> list[dict]:
        sql = (MESSAGE_SELECT + " WHERE m.conversation_id = ? AND " + where + " AND "
               + visible_sql("m", with_current=False) + f" ORDER BY m.seq {order} LIMIT ?")
        return self.db.q_all(sql, (cid,) + params + visible_params(user_id, with_current=False) + (limit,))

    def _exists(self, user_id: str, cid: str, where: str, params: tuple) -> bool:
        sql = ("SELECT 1 FROM messages m WHERE m.conversation_id = ? AND " + where + " AND "
               + visible_sql("m", with_current=False) + " LIMIT 1")
        return self.db.scalar(sql, (cid,) + params + visible_params(user_id, with_current=False)) is not None

    def page_after(self, user_id: str, cid: str, after_seq: int, limit: int) -> tuple[list[dict], bool]:
        rows = self._page(user_id, cid, "m.seq > ?", (after_seq,), "ASC", limit + 1)
        has_more = len(rows) > limit
        return hydrate_messages(self.db, rows[:limit]), has_more

    def list_messages(self, user_id: str, cid: str, limit: int | None, before_seq: int | None,
                      after_seq: int | None, around_seq: int | None) -> dict:
        self.conversations.require_member(user_id, cid)
        if sum(x is not None for x in (before_seq, after_seq, around_seq)) > 1:
            raise ValidationFailed("Use only one of before_seq, after_seq, or around_seq.")
        limit = max(1, min(limit or self.settings.page_size, self.settings.page_size))
        if after_seq is not None:
            rows = self._page(user_id, cid, "m.seq > ?", (after_seq,), "ASC", limit)
        elif around_seq is not None:
            half = 25
            before = self._page(user_id, cid, "m.seq < ?", (around_seq,), "DESC", half)
            rest = self._page(user_id, cid, "m.seq >= ?", (around_seq,), "ASC", half + 1)
            rows = list(reversed(before)) + rest
        elif before_seq is not None:
            rows = list(reversed(self._page(user_id, cid, "m.seq < ?", (before_seq,), "DESC", limit)))
        else:
            rows = list(reversed(self._page(user_id, cid, "1 = 1", (), "DESC", limit)))
        if rows:
            low, high = rows[0]["seq"], rows[-1]["seq"]
            more_before = self._exists(user_id, cid, "m.seq < ?", (low,))
            more_after = self._exists(user_id, cid, "m.seq > ?", (high,))
        else:
            more_before = more_after = False
        return {"messages": hydrate_messages(self.db, rows), "has_more_before": more_before, "has_more_after": more_after}

    def thread(self, user_id: str, message_id: str) -> dict:
        row = self._visible_row(user_id, message_id)
        root_id = row["reply_to_id"] or row["id"]
        root = row if root_id == row["id"] else self._visible_row(user_id, root_id)
        replies = self._page(user_id, root["conversation_id"], "m.reply_to_id = ?", (root_id,), "ASC", 1000)
        return {"root": hydrate_messages(self.db, [root])[0], "replies": hydrate_messages(self.db, replies)}

    # --- sending ------------------------------------------------------------
    def _parse_mentions(self, body: str, conversation_id: str, sender_id: str) -> list[str]:
        names = []
        for match in MENTION_RE.finditer(body):
            raw = match.group(1).lower()
            for candidate in (raw, raw.rstrip(".-_")):
                if len(candidate) >= 3 and candidate not in names:
                    names.append(candidate)
            if len(names) >= MAX_MENTIONS:
                break
        if not names:
            return []
        marks = ",".join("?" * len(names))
        rows = self.db.q_all(
            f"SELECT u.id FROM users u JOIN memberships ms ON ms.user_id = u.id "
            f"WHERE u.username IN ({marks}) AND u.status = 'active' AND ms.conversation_id = ? "
            f"AND ms.to_seq IS NULL AND u.id != ?",
            tuple(names) + (conversation_id, sender_id),
        )
        return [r["id"] for r in rows]

    def send(self, user: dict, conversation_id: str, client_msg_id: str, body: str,
             reply_to_id: str | None = None, attachment_ids: list[str] | None = None,
             t0: float | None = None) -> tuple[dict, bool]:
        t0 = clock.monotonic() if t0 is None else t0
        attachment_ids = attachment_ids or []
        client_msg_id = (client_msg_id or "").strip()
        if not 8 <= len(client_msg_id) <= 64:
            raise ValidationFailed("client_msg_id must be 8 to 64 characters.")
        body = (body or "").strip()
        if not body:
            raise ValidationFailed("Message cannot be empty.")
        if len(body) > self.settings.max_message_chars:
            raise ValidationFailed(f"Message is too long (limit {self.settings.max_message_chars} characters).")

        conv = self.conversations.require_member(user["id"], conversation_id)
        if conv["type"] == "dm":
            other_status = self.db.scalar(
                "SELECT u.status FROM memberships ms JOIN users u ON u.id = ms.user_id "
                "WHERE ms.conversation_id = ? AND ms.user_id != ? AND ms.to_seq IS NULL",
                (conversation_id, user["id"]),
            )
            if other_status == "deactivated":
                raise Conflict("This person is no longer a member.", code="conversation_closed")

        existing = self.db.q_one(
            MESSAGE_SELECT + " WHERE m.sender_id = ? AND m.client_msg_id = ?", (user["id"], client_msg_id)
        )
        if existing:
            if existing["conversation_id"] != conversation_id:
                raise Conflict("That client_msg_id was already used in another conversation.")
            return hydrate_messages(self.db, [existing])[0], True

        allowed, retry_after = (True, 0) if user.get("is_bot") else self.rate.check_and_record(user["id"])
        if not allowed:
            raise RateLimited(retry_after)

        root_id = None
        if reply_to_id:
            parent = self.db.q_one("SELECT * FROM messages WHERE id = ?", (reply_to_id,))
            if (not parent or parent["conversation_id"] != conversation_id
                    or not access.can_see(self.db, user["id"], conversation_id, parent["seq"])):
                raise ValidationFailed("The message you are replying to is not in this conversation.")
            if parent["deleted_at"]:
                raise ValidationFailed("You cannot reply to a deleted message.")
            root_id = parent["reply_to_id"] or parent["id"]
        self.attachments.validate_for_message(user["id"], conversation_id, attachment_ids)

        message_id = new_id()
        notification_ids = []
        with self.db.transaction():
            seq = self.db.scalar("SELECT last_seq FROM conversations WHERE id = ?", (conversation_id,)) + 1
            self.db.exec("UPDATE conversations SET last_seq = ? WHERE id = ?", (seq, conversation_id))
            self.db.exec(
                "INSERT INTO messages (id, conversation_id, seq, sender_id, client_msg_id, body, reply_to_id, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (message_id, conversation_id, seq, user["id"], client_msg_id, body, root_id, clock.iso()),
            )
            for uid in self._parse_mentions(body, conversation_id, user["id"]):
                self.db.exec("INSERT INTO mentions (message_id, user_id) VALUES (?, ?)", (message_id, uid))
                notification_ids.append(
                    self.notifications.create(uid, "mention", conversation_id, user["id"], message_id)
                )
            self.attachments.link_to_message(attachment_ids, message_id)
        # Committed. From here nothing can fail the send, and there is no await before publishing,
        # so events leave in the same order as the sequence numbers (DD-03, FR-41).
        message = hydrate_messages(self.db, [self._by_id(message_id)])[0]
        self.hub.publish_message(message, self.conversations.member_ids(conversation_id), t0)
        self.notifications.deliver(notification_ids)
        if self.assistant is not None:
            self.assistant.on_message(conv, message)
        return message, False

    # --- deleting -----------------------------------------------------------
    def delete(self, user: dict, message_id: str) -> None:
        row = self._visible_row(user["id"], message_id)
        if row["sender_id"] != user["id"]:
            raise Forbidden("Only the author can delete a message.")
        if row["deleted_at"]:
            return
        self.tombstone(row)

    def tombstone(self, row: dict) -> None:
        """Remove content from every copy the service controls, in one transaction (DD-11)."""
        with self.db.transaction():
            self.db.exec("UPDATE messages SET body = NULL, deleted_at = ? WHERE id = ?", (clock.iso(), row["id"]))
            self.db.exec("DELETE FROM mentions WHERE message_id = ?", (row["id"],))
            self.db.exec("DELETE FROM notifications WHERE message_id = ?", (row["id"],))
            files = self.attachments.mark_deleted_for_message(row["id"])
        self.attachments.remove_files(files)
        self.hub.publish_to_users(
            self.conversations.member_ids(row["conversation_id"]),
            {"type": "message_deleted", "conversation_id": row["conversation_id"], "message_id": row["id"]},
        )
