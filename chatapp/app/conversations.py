"""Conversations, membership periods, and read position (FR-10 to FR-16, FR-47)."""
from app import access, clock
from app.errors import Conflict, Forbidden, NotFound, ValidationFailed
from app.ids import new_id

CONVERSATION_TYPES = ("dm", "group", "channel")


class ConversationService:
    def __init__(self, db, settings, audit, notifications, hub):
        self.db = db
        self.settings = settings
        self.audit = audit
        self.notifications = notifications
        self.hub = hub
        self.bot_provider = None  # set after construction: returns the assistant's user row, or None
        self.auto_join_bot = False

    def _bot_id(self) -> str | None:
        bot = self.bot_provider() if self.bot_provider else None
        return bot["id"] if bot else None

    def add_bot(self, conv: dict) -> None:
        """The assistant joins a group chat or channel. It never joins direct messages between people."""
        bot_id = self._bot_id()
        if not bot_id or conv["type"] == "dm" or self.is_member(bot_id, conv["id"]):
            return
        with self.db.transaction():
            self._open_period(conv, bot_id)
            self.audit.record("system", "assistant.join", "conversation", conv["id"], {})

    # --- lookups ----------------------------------------------------------
    def require_member(self, user_id: str, conversation_id: str) -> dict:
        """Not a member and does not exist look the same on purpose (DD-08)."""
        row = self.db.q_one(
            "SELECT c.* FROM conversations c JOIN memberships ms ON ms.conversation_id = c.id "
            "WHERE c.id = ? AND ms.user_id = ? AND ms.to_seq IS NULL",
            (conversation_id, user_id),
        )
        if not row:
            raise NotFound()
        return row

    def is_member(self, user_id: str, conversation_id: str) -> bool:
        return access.is_current_member(self.db, user_id, conversation_id)

    def member_ids(self, conversation_id: str) -> list[str]:
        rows = self.db.q_all(
            "SELECT user_id FROM memberships WHERE conversation_id = ? AND to_seq IS NULL", (conversation_id,)
        )
        return [r["user_id"] for r in rows]

    def ids_for_user(self, user_id: str) -> set[str]:
        rows = self.db.q_all(
            "SELECT conversation_id FROM memberships WHERE user_id = ? AND to_seq IS NULL", (user_id,)
        )
        return {r["conversation_id"] for r in rows}

    def unread_count(self, user_id: str, conversation_id: str) -> int:
        return self.db.scalar(
            "SELECT COUNT(*) FROM messages m WHERE m.conversation_id = ? AND m.sender_id != ? "
            "AND m.deleted_at IS NULL AND m.seq > COALESCE((SELECT last_read_seq FROM read_cursors "
            "WHERE user_id = ? AND conversation_id = ?), 0) AND " + access.visible_sql("m", with_current=False),
            (conversation_id, user_id, user_id, conversation_id) + access.visible_params(user_id, with_current=False),
        )

    def to_dict(self, row: dict, user_id: str) -> dict:
        members = self.db.q_all(
            "SELECT u.id, u.display_name, u.status FROM memberships ms JOIN users u ON u.id = ms.user_id "
            "WHERE ms.conversation_id = ? AND ms.to_seq IS NULL ORDER BY u.display_name COLLATE NOCASE",
            (row["id"],),
        )
        return {
            "id": row["id"],
            "type": row["type"],
            "name": row["name"],
            "members": members,
            "last_seq": row["last_seq"],
            "unread_count": self.unread_count(user_id, row["id"]),
            "created_at": row["created_at"],
        }

    def get_for_user(self, user_id: str, conversation_id: str) -> dict:
        return self.to_dict(self.require_member(user_id, conversation_id), user_id)

    def list_for_user(self, user_id: str) -> list[dict]:
        rows = self.db.q_all(
            "SELECT c.* FROM conversations c JOIN memberships ms ON ms.conversation_id = c.id "
            "WHERE ms.user_id = ? AND ms.to_seq IS NULL ORDER BY c.created_at",
            (user_id,),
        )
        return [self.to_dict(r, user_id) for r in rows]

    # --- membership internals --------------------------------------------
    def _open_period(self, conversation: dict, user_id: str) -> None:
        # Groups: a member sees messages from the join onward. Channels and direct messages: everything (FR-15).
        from_seq = conversation["last_seq"] + 1 if conversation["type"] == "group" else 1
        self.db.exec(
            "INSERT INTO memberships (conversation_id, user_id, from_seq, to_seq, joined_at) VALUES (?, ?, ?, NULL, ?)",
            (conversation["id"], user_id, from_seq, clock.iso()),
        )

    def _active_users(self, ids: list[str]) -> list[dict]:
        if not ids:
            return []
        marks = ",".join("?" * len(ids))
        rows = self.db.q_all(f"SELECT * FROM users WHERE id IN ({marks}) AND status = 'active'", tuple(ids))
        if len(rows) != len(ids):
            raise ValidationFailed("One or more members are unknown or deactivated.")
        return rows

    # --- commands -----------------------------------------------------------
    def create(self, actor: dict, ctype: str, name: str | None, member_ids: list[str]) -> tuple[dict, bool]:
        if ctype not in CONVERSATION_TYPES:
            raise ValidationFailed("Type must be dm, group, or channel.")
        others = list(dict.fromkeys(m for m in member_ids if m != actor["id"]))
        self._active_users(others)
        name = (name or "").strip() or None

        if ctype == "dm":
            if len(others) != 1:
                raise ValidationFailed("A direct message needs exactly one other person.")
            dm_key = ":".join(sorted([actor["id"], others[0]]))
            existing = self.db.q_one("SELECT * FROM conversations WHERE dm_key = ?", (dm_key,))
            if existing:
                return self.to_dict(existing, actor["id"]), False
            name = None
        else:
            if not name or len(name) > 50:
                raise ValidationFailed("Name must be 1 to 50 characters.")
            dm_key = None
            if ctype == "group" and not 1 <= len(others) <= self.settings.max_group_members - 1:
                raise ValidationFailed(f"A group chat needs 1 to {self.settings.max_group_members - 1} other members.")
            if ctype == "channel":
                if not actor["is_admin"]:
                    raise Forbidden("Only administrators can create channels.")
                if len(others) > self.settings.max_channel_members - 1:
                    raise ValidationFailed(f"A channel can have at most {self.settings.max_channel_members} members.")
                if self.db.scalar("SELECT 1 FROM conversations WHERE type = 'channel' AND name_key = ?", (name.lower(),)):
                    raise Conflict("A channel with that name already exists.")

        cid = new_id()
        notification_ids = []
        with self.db.transaction():
            self.db.exec(
                "INSERT INTO conversations (id, type, name, name_key, dm_key, created_by, created_at, last_seq) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, 0)",
                (cid, ctype, name, name.lower() if ctype == "channel" else None, dm_key, actor["id"], clock.iso()),
            )
            conversation = self.db.q_one("SELECT * FROM conversations WHERE id = ?", (cid,))
            self._open_period(conversation, actor["id"])
            for uid in others:
                self._open_period(conversation, uid)
                if ctype != "dm":
                    notification_ids.append(self.notifications.create(uid, "added", cid, actor["id"]))
            if ctype != "dm":
                self.audit.record(actor["id"], f"{ctype}.create", "conversation", cid, {"members": len(others) + 1})
                if self.auto_join_bot and self._bot_id() and self._bot_id() not in others:
                    self._open_period(conversation, self._bot_id())
        for uid in others:
            self.hub.publish_to_users([uid], {"type": "conversation_added", "conversation": self.get_for_user(uid, cid)})
        self.notifications.deliver(notification_ids)
        return self.get_for_user(actor["id"], cid), True

    def _managed(self, actor: dict, conversation_id: str) -> dict:
        """Members can manage their groups. Administrators can manage any channel without reading it (SEC-04)."""
        conv = self.db.q_one("SELECT * FROM conversations WHERE id = ?", (conversation_id,))
        if conv and conv["type"] == "channel" and actor["is_admin"]:
            return conv
        return self.require_member(actor["id"], conversation_id)

    def add_member(self, actor: dict, conversation_id: str, user_id: str) -> dict:
        conv = self._managed(actor, conversation_id)
        if conv["type"] == "dm":
            raise ValidationFailed("You cannot add members to a direct message.")
        if conv["type"] == "channel" and not actor["is_admin"]:
            raise Forbidden("Only administrators can add members to a channel.")
        self._active_users([user_id])
        limit = self.settings.max_group_members if conv["type"] == "group" else self.settings.max_channel_members
        with self.db.transaction():
            conv = self.db.q_one("SELECT * FROM conversations WHERE id = ?", (conversation_id,))
            current = self.member_ids(conversation_id)
            if user_id in current:
                raise Conflict("That person is already a member.")
            # The assistant does not count toward the member limits.
            people = [i for i in current if i != self._bot_id()]
            if user_id != self._bot_id() and len(people) >= limit:
                raise Conflict(f"This conversation already has the maximum of {limit} members.")
            self._open_period(conv, user_id)
            self.audit.record(actor["id"], "member.add", "conversation", conversation_id, {"user_id": user_id})
            nid = self.notifications.create(user_id, "added", conversation_id, actor["id"])
        self.hub.publish_to_users(
            [user_id], {"type": "conversation_added", "conversation": self.get_for_user(user_id, conversation_id)}
        )
        self.notifications.deliver([nid])
        return self.to_dict(self.db.q_one("SELECT * FROM conversations WHERE id = ?", (conversation_id,)), actor["id"])

    def remove_member(self, actor: dict, conversation_id: str, user_id: str) -> None:
        conv = self._managed(actor, conversation_id)
        if conv["type"] == "dm":
            raise ValidationFailed("You cannot leave or change a direct message.")
        if user_id != actor["id"] and not (conv["type"] == "channel" and actor["is_admin"]):
            raise Forbidden("You are not allowed to remove that member.")
        with self.db.transaction():
            conv = self.db.q_one("SELECT * FROM conversations WHERE id = ?", (conversation_id,))
            if user_id not in self.member_ids(conversation_id):
                raise NotFound("That person is not a member.")
            self.db.exec(
                "UPDATE memberships SET to_seq = ?, left_at = ? "
                "WHERE conversation_id = ? AND user_id = ? AND to_seq IS NULL",
                (conv["last_seq"], clock.iso(), conversation_id, user_id),
            )
            self.audit.record(actor["id"], "member.remove", "conversation", conversation_id, {"user_id": user_id})
        self.hub.publish_to_users([user_id], {"type": "conversation_removed", "conversation_id": conversation_id})

    def mark_read(self, user_id: str, conversation_id: str, seq: int) -> dict:
        conv = self.require_member(user_id, conversation_id)
        seq = min(max(seq, 0), conv["last_seq"])
        self.db.exec(
            "INSERT INTO read_cursors (user_id, conversation_id, last_read_seq) VALUES (?, ?, ?) "
            "ON CONFLICT (user_id, conversation_id) DO UPDATE SET "
            "last_read_seq = MAX(last_read_seq, excluded.last_read_seq)",
            (user_id, conversation_id, seq),
        )
        cursor = self.db.scalar(
            "SELECT last_read_seq FROM read_cursors WHERE user_id = ? AND conversation_id = ?",
            (user_id, conversation_id),
        )
        return {
            "conversation_id": conversation_id,
            "last_read_seq": cursor,
            "unread_count": self.unread_count(user_id, conversation_id),
        }
