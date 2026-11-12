"""Search limited to what the caller may see (FR-25, PRV-02)."""
import re

from app.access import visible_params, visible_sql
from app.errors import ValidationFailed
from app.serializers import hydrate_messages

_WORD = re.compile(r"\w+", re.UNICODE)


class SearchService:
    def __init__(self, db):
        self.db = db

    def search(self, user_id: str, q: str, limit: int | None) -> dict:
        q = (q or "").strip()
        if not 2 <= len(q) <= 100:
            raise ValidationFailed("Search text must be 2 to 100 characters.")
        limit = max(1, min(limit or 50, 50))
        # Words only, each quoted: users can never inject search syntax.
        terms = _WORD.findall(q)[:10]
        if not terms:
            return {"results": []}
        match = " ".join(f'"{t}"' for t in terms)
        rows = self.db.q_all(
            "SELECT m.id, m.conversation_id, m.seq, m.sender_id, m.client_msg_id, m.body, m.reply_to_id, "
            "m.created_at, m.deleted_at, u.display_name AS sender_name, u.status AS sender_status, "
            "c.name AS cname, c.type AS ctype "
            "FROM messages_fts JOIN messages m ON m.rid = messages_fts.rowid "
            "JOIN users u ON u.id = m.sender_id JOIN conversations c ON c.id = m.conversation_id "
            "WHERE messages_fts MATCH ? AND m.deleted_at IS NULL AND " + visible_sql("m")
            + " ORDER BY m.created_at DESC, m.rid DESC LIMIT ?",
            (match,) + visible_params(user_id) + (limit,),
        )
        messages = hydrate_messages(self.db, rows)
        results = []
        for msg, row in zip(messages, rows):
            if row["ctype"] == "dm":
                name = self.db.scalar(
                    "SELECT u.display_name FROM memberships ms JOIN users u ON u.id = ms.user_id "
                    "WHERE ms.conversation_id = ? AND ms.user_id != ? AND ms.to_seq IS NULL LIMIT 1",
                    (row["conversation_id"], user_id),
                ) or "Direct message"
            else:
                name = row["cname"]
            body = msg["body"] or ""
            results.append({
                "message": msg,
                "conversation_name": name,
                "excerpt": body if len(body) <= 160 else body[:160] + "...",
            })
        return {"results": results}
