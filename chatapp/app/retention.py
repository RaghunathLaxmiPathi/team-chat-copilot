"""Removes message content older than the retention period (NFR-05, DD-18). Off by default."""
from datetime import timedelta

from app import clock


class RetentionService:
    def __init__(self, db, messages, settings):
        self.db = db
        self.messages = messages
        self.settings = settings

    def purge(self, days: int | None = None, now=None) -> int:
        days = self.settings.retention_days if days is None else days
        if days <= 0:
            return 0
        cutoff = clock.iso((now or clock.now()) - timedelta(days=days))
        rows = self.db.q_all(
            "SELECT id, conversation_id FROM messages WHERE deleted_at IS NULL AND created_at < ?", (cutoff,)
        )
        for row in rows:
            self.messages.tombstone(row)
        return len(rows)
