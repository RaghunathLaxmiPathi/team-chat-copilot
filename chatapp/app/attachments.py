"""File uploads (FR-24, DD-22). Files are stored under generated names, never the user's name."""
import os
import re
from pathlib import Path

from app import access, clock
from app.errors import NotFound, PayloadTooLarge, UnsupportedMedia, ValidationFailed
from app.ids import new_id

_DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
_PPTX = "application/vnd.openxmlformats-officedocument.presentationml.presentation"

ALLOWED_TYPES = {
    "png": {"image/png"},
    "jpg": {"image/jpeg"},
    "jpeg": {"image/jpeg"},
    "gif": {"image/gif"},
    "webp": {"image/webp"},
    "pdf": {"application/pdf"},
    "txt": {"text/plain"},
    "md": {"text/markdown", "text/plain", "text/x-markdown"},
    "csv": {"text/csv", "application/vnd.ms-excel", "text/plain"},
    "docx": {_DOCX},
    "xlsx": {_XLSX},
    "pptx": {_PPTX},
}


class AllowAllScanner:
    """Lab stub: accepts every file. Production uses a real malware scanner (risk R-08)."""

    def scan(self, filename: str, data: bytes) -> bool:
        return True


def clean_filename(name: str) -> str:
    name = os.path.basename((name or "").replace("\\", "/"))
    name = re.sub(r"[\x00-\x1f\x7f]", "", name).strip()
    return name[:200] or "file"


class AttachmentService:
    def __init__(self, db, settings, conversations, scanner=None):
        self.db = db
        self.settings = settings
        self.conversations = conversations
        self.scanner = scanner or AllowAllScanner()
        self.dir = Path(settings.attachment_dir)
        self.dir.mkdir(parents=True, exist_ok=True)

    @property
    def max_bytes(self) -> int:
        return self.settings.max_upload_mb * 1024 * 1024

    def store(self, user_id: str, conversation_id: str, filename: str, content_type: str, data: bytes) -> dict:
        self.conversations.require_member(user_id, conversation_id)
        filename = clean_filename(filename)
        if not data:
            raise ValidationFailed("The file is empty.")
        if len(data) > self.max_bytes:
            raise PayloadTooLarge(f"File is larger than {self.settings.max_upload_mb} MB.")
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        allowed = ALLOWED_TYPES.get(ext)
        declared = (content_type or "").split(";")[0].strip().lower()
        if not allowed or (declared and declared != "application/octet-stream" and declared not in allowed):
            raise UnsupportedMedia("This file type is not allowed.")
        if not self.scanner.scan(filename, data):
            raise ValidationFailed("The file failed the security scan.")
        aid = new_id()
        storage_name = f"{new_id()}.{ext}"
        (self.dir / storage_name).write_bytes(data)
        content = sorted(allowed)[0] if declared in ("", "application/octet-stream") else declared
        self.db.exec(
            "INSERT INTO attachments (id, conversation_id, uploader_id, message_id, filename, content_type, "
            "size_bytes, storage_name, scan_status, created_at) VALUES (?, ?, ?, NULL, ?, ?, ?, ?, 'clean', ?)",
            (aid, conversation_id, user_id, filename, content, len(data), storage_name, clock.iso()),
        )
        return {"id": aid, "filename": filename, "content_type": content, "size_bytes": len(data)}

    def open_for(self, user_id: str, attachment_id: str) -> tuple[Path, str, str]:
        row = self.db.q_one("SELECT * FROM attachments WHERE id = ?", (attachment_id,))
        if not row or row["deleted_at"] or row["scan_status"] != "clean":
            raise NotFound()
        if row["message_id"] is None:
            # Not sent yet: only the uploader may open it (AR-07).
            if row["uploader_id"] != user_id or not access.is_current_member(self.db, user_id, row["conversation_id"]):
                raise NotFound()
        else:
            msg = self.db.q_one("SELECT conversation_id, seq FROM messages WHERE id = ?", (row["message_id"],))
            if not msg or not access.can_see(self.db, user_id, msg["conversation_id"], msg["seq"]):
                raise NotFound()
        path = self.dir / row["storage_name"]
        if not path.exists():
            raise NotFound()
        return path, row["filename"], row["content_type"]

    def validate_for_message(self, user_id: str, conversation_id: str, ids: list[str]) -> list[dict]:
        if len(set(ids)) != len(ids):
            raise ValidationFailed("The same attachment was listed twice.")
        if len(ids) > self.settings.max_attachments_per_message:
            raise ValidationFailed(f"A message can have at most {self.settings.max_attachments_per_message} attachments.")
        rows = []
        for aid in ids:
            row = self.db.q_one("SELECT * FROM attachments WHERE id = ?", (aid,))
            if (not row or row["uploader_id"] != user_id or row["conversation_id"] != conversation_id
                    or row["message_id"] is not None or row["deleted_at"] or row["scan_status"] != "clean"):
                raise ValidationFailed("An attachment is not available for this message.")
            rows.append(row)
        return rows

    def link_to_message(self, ids: list[str], message_id: str) -> None:
        for aid in ids:
            self.db.exec("UPDATE attachments SET message_id = ? WHERE id = ?", (message_id, aid))

    def mark_deleted_for_message(self, message_id: str) -> list[str]:
        """Call inside the caller's transaction. Returns file names to remove after the commit."""
        names = [r["storage_name"] for r in self.db.q_all(
            "SELECT storage_name FROM attachments WHERE message_id = ? AND deleted_at IS NULL", (message_id,))]
        self.db.exec(
            "UPDATE attachments SET deleted_at = ?, filename = '' WHERE message_id = ? AND deleted_at IS NULL",
            (clock.iso(), message_id),
        )
        return names

    def remove_files(self, storage_names: list[str]) -> None:
        for name in storage_names:
            try:
                (self.dir / name).unlink(missing_ok=True)
            except OSError:
                pass

    def cleanup_unsent(self, now=None) -> int:
        """Remove uploads that were never sent with a message (FR-24)."""
        from datetime import timedelta
        cutoff = clock.iso((now or clock.now()) - timedelta(seconds=self.settings.unsent_upload_ttl_s))
        rows = self.db.q_all(
            "SELECT id, storage_name FROM attachments WHERE message_id IS NULL AND deleted_at IS NULL AND created_at < ?",
            (cutoff,),
        )
        if rows:
            with self.db.transaction():
                for r in rows:
                    self.db.exec("DELETE FROM attachments WHERE id = ?", (r["id"],))
            self.remove_files([r["storage_name"] for r in rows])
        return len(rows)

    def total_bytes(self) -> int:
        return self.db.scalar("SELECT COALESCE(SUM(size_bytes), 0) FROM attachments WHERE deleted_at IS NULL")
