"""Turn database rows into the shapes the API and real-time channel send."""
from collections import defaultdict

MESSAGE_SELECT = (
    "SELECT m.id, m.conversation_id, m.seq, m.sender_id, m.client_msg_id, m.body, m.reply_to_id, "
    "m.created_at, m.deleted_at, u.display_name AS sender_name, u.status AS sender_status "
    "FROM messages m JOIN users u ON u.id = m.sender_id"
)


def public_user(row: dict) -> dict:
    return {
        "id": row["id"],
        "username": row["username"],
        "display_name": row["display_name"],
        "is_admin": bool(row["is_admin"]),
        "is_bot": bool(row.get("is_bot", 0)),
        "copilot_auto": bool(row.get("copilot_auto", 0)),
        "copilot_history": bool(row.get("copilot_history", 0)),
        "status": row["status"],
    }


def hydrate_messages(db, rows: list[dict]) -> list[dict]:
    if not rows:
        return []
    ids = [r["id"] for r in rows]
    marks = ",".join("?" * len(ids))
    mentions = defaultdict(list)
    for r in db.q_all(f"SELECT message_id, user_id FROM mentions WHERE message_id IN ({marks})", tuple(ids)):
        mentions[r["message_id"]].append(r["user_id"])
    files = defaultdict(list)
    for r in db.q_all(
        f"SELECT id, message_id, filename, content_type, size_bytes FROM attachments "
        f"WHERE message_id IN ({marks}) AND deleted_at IS NULL ORDER BY created_at",
        tuple(ids),
    ):
        files[r["message_id"]].append(
            {"id": r["id"], "filename": r["filename"], "content_type": r["content_type"], "size_bytes": r["size_bytes"]}
        )
    out = []
    for r in rows:
        deleted = r["deleted_at"] is not None
        out.append({
            "id": r["id"],
            "conversation_id": r["conversation_id"],
            "seq": r["seq"],
            "sender_id": r["sender_id"],
            "sender_name": r["sender_name"],
            "sender_status": r["sender_status"],
            "body": None if deleted else r["body"],
            "deleted": deleted,
            "reply_to_id": r["reply_to_id"],
            "mentions": [] if deleted else sorted(mentions.get(r["id"], [])),
            "attachments": [] if deleted else files.get(r["id"], []),
            "client_msg_id": r["client_msg_id"],
            "created_at": r["created_at"],
        })
    return out
