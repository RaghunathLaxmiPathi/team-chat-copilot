"""SQLite storage: one connection, write-ahead log, full synchronous writes (DD-01, DD-05)."""
import sqlite3
from contextlib import contextmanager
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
  id TEXT PRIMARY KEY,
  username TEXT NOT NULL UNIQUE,
  display_name TEXT NOT NULL,
  is_admin INTEGER NOT NULL DEFAULT 0,
  is_bot INTEGER NOT NULL DEFAULT 0,
  copilot_auto INTEGER NOT NULL DEFAULT 1,
  copilot_history INTEGER NOT NULL DEFAULT 1,
  status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','deactivated')),
  created_at TEXT NOT NULL,
  deactivated_at TEXT
);

CREATE TABLE IF NOT EXISTS conversations (
  id TEXT PRIMARY KEY,
  type TEXT NOT NULL CHECK (type IN ('dm','group','channel')),
  name TEXT,
  name_key TEXT,
  dm_key TEXT UNIQUE,
  created_by TEXT NOT NULL REFERENCES users(id),
  created_at TEXT NOT NULL,
  last_seq INTEGER NOT NULL DEFAULT 0
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_channel_name ON conversations(name_key) WHERE type = 'channel';

CREATE TABLE IF NOT EXISTS memberships (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  conversation_id TEXT NOT NULL REFERENCES conversations(id),
  user_id TEXT NOT NULL REFERENCES users(id),
  from_seq INTEGER NOT NULL,
  to_seq INTEGER,
  joined_at TEXT NOT NULL,
  left_at TEXT
);
CREATE INDEX IF NOT EXISTS ix_memberships_user ON memberships(user_id, conversation_id);
CREATE UNIQUE INDEX IF NOT EXISTS ux_membership_current ON memberships(conversation_id, user_id) WHERE to_seq IS NULL;

CREATE TABLE IF NOT EXISTS messages (
  rid INTEGER PRIMARY KEY AUTOINCREMENT,
  id TEXT NOT NULL UNIQUE,
  conversation_id TEXT NOT NULL REFERENCES conversations(id),
  seq INTEGER NOT NULL,
  sender_id TEXT NOT NULL REFERENCES users(id),
  client_msg_id TEXT NOT NULL,
  body TEXT,
  reply_to_id TEXT,
  created_at TEXT NOT NULL,
  deleted_at TEXT,
  UNIQUE (conversation_id, seq),
  UNIQUE (sender_id, client_msg_id)
);
CREATE INDEX IF NOT EXISTS ix_messages_reply ON messages(reply_to_id);
CREATE INDEX IF NOT EXISTS ix_messages_deleted ON messages(deleted_at) WHERE deleted_at IS NOT NULL;
CREATE INDEX IF NOT EXISTS ix_messages_created ON messages(created_at);

CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts USING fts5(body, content='messages', content_rowid='rid');

CREATE TRIGGER IF NOT EXISTS messages_ai AFTER INSERT ON messages WHEN new.body IS NOT NULL BEGIN
  INSERT INTO messages_fts(rowid, body) VALUES (new.rid, new.body);
END;
CREATE TRIGGER IF NOT EXISTS messages_au_remove AFTER UPDATE OF body ON messages WHEN old.body IS NOT NULL BEGIN
  INSERT INTO messages_fts(messages_fts, rowid, body) VALUES ('delete', old.rid, old.body);
END;
CREATE TRIGGER IF NOT EXISTS messages_au_add AFTER UPDATE OF body ON messages WHEN new.body IS NOT NULL BEGIN
  INSERT INTO messages_fts(rowid, body) VALUES (new.rid, new.body);
END;

CREATE TABLE IF NOT EXISTS mentions (
  message_id TEXT NOT NULL REFERENCES messages(id),
  user_id TEXT NOT NULL REFERENCES users(id),
  PRIMARY KEY (message_id, user_id)
);

CREATE TABLE IF NOT EXISTS attachments (
  id TEXT PRIMARY KEY,
  conversation_id TEXT NOT NULL REFERENCES conversations(id),
  uploader_id TEXT NOT NULL REFERENCES users(id),
  message_id TEXT REFERENCES messages(id),
  filename TEXT NOT NULL,
  content_type TEXT NOT NULL,
  size_bytes INTEGER NOT NULL,
  storage_name TEXT NOT NULL,
  scan_status TEXT NOT NULL DEFAULT 'clean' CHECK (scan_status IN ('clean','pending','rejected')),
  created_at TEXT NOT NULL,
  deleted_at TEXT
);
CREATE INDEX IF NOT EXISTS ix_attachments_message ON attachments(message_id);

CREATE TABLE IF NOT EXISTS notifications (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL REFERENCES users(id),
  type TEXT NOT NULL CHECK (type IN ('mention','added')),
  conversation_id TEXT NOT NULL REFERENCES conversations(id),
  actor_id TEXT NOT NULL REFERENCES users(id),
  message_id TEXT,
  created_at TEXT NOT NULL,
  read_at TEXT
);
CREATE INDEX IF NOT EXISTS ix_notifications_user ON notifications(user_id, created_at);

CREATE TABLE IF NOT EXISTS notification_outbox (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL REFERENCES users(id),
  channel TEXT NOT NULL,
  type TEXT NOT NULL,
  conversation_id TEXT NOT NULL,
  actor_id TEXT NOT NULL,
  created_at TEXT NOT NULL,
  sent_at TEXT
);

CREATE TABLE IF NOT EXISTS read_cursors (
  user_id TEXT NOT NULL REFERENCES users(id),
  conversation_id TEXT NOT NULL REFERENCES conversations(id),
  last_read_seq INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (user_id, conversation_id)
);

CREATE TABLE IF NOT EXISTS audit_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts TEXT NOT NULL,
  actor_id TEXT NOT NULL,
  action TEXT NOT NULL,
  target_type TEXT NOT NULL,
  target_id TEXT NOT NULL,
  detail TEXT
);

CREATE TABLE IF NOT EXISTS slo_minutes (
  minute TEXT PRIMARY KEY,
  req_total INTEGER NOT NULL,
  req_failed INTEGER NOT NULL,
  lat_counts TEXT NOT NULL,
  lat_total INTEGER NOT NULL
);
"""


class Database:
    def __init__(self, path: str):
        self.path = path
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        # Autocommit mode: transactions are explicit (see transaction()).
        self.conn = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA synchronous=FULL")
        self.conn.execute("PRAGMA foreign_keys=ON")
        self.conn.execute("PRAGMA busy_timeout=5000")
        self.conn.executescript(SCHEMA)
        # Databases created before the assistant existed do not have the is_bot column yet.
        if not any(r["name"] == "is_bot" for r in self.conn.execute("PRAGMA table_info(users)")):
            self.conn.execute("ALTER TABLE users ADD COLUMN is_bot INTEGER NOT NULL DEFAULT 0")
        if not any(r["name"] == "copilot_auto" for r in self.conn.execute("PRAGMA table_info(users)")):
            self.conn.execute("ALTER TABLE users ADD COLUMN copilot_auto INTEGER NOT NULL DEFAULT 1")
        if not any(r["name"] == "copilot_history" for r in self.conn.execute("PRAGMA table_info(users)")):
            self.conn.execute("ALTER TABLE users ADD COLUMN copilot_history INTEGER NOT NULL DEFAULT 1")
        self._depth = 0

    @contextmanager
    def transaction(self):
        """All-or-nothing unit of work. Nested use joins the outer transaction."""
        if self._depth == 0:
            self.conn.execute("BEGIN IMMEDIATE")
        self._depth += 1
        try:
            yield self
        except BaseException:
            self._depth -= 1
            if self._depth == 0:
                self.conn.execute("ROLLBACK")
            raise
        else:
            self._depth -= 1
            if self._depth == 0:
                self.conn.execute("COMMIT")

    def exec(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        return self.conn.execute(sql, params)

    def q_one(self, sql: str, params: tuple = ()) -> dict | None:
        row = self.conn.execute(sql, params).fetchone()
        return dict(row) if row else None

    def q_all(self, sql: str, params: tuple = ()) -> list[dict]:
        return [dict(r) for r in self.conn.execute(sql, params).fetchall()]

    def scalar(self, sql: str, params: tuple = ()):
        row = self.conn.execute(sql, params).fetchone()
        return row[0] if row else None

    def size_bytes(self) -> int:
        if self.path == ":memory:":
            return 0
        total = 0
        for suffix in ("", "-wal"):
            p = Path(self.path + suffix)
            if p.exists():
                total += p.stat().st_size
        return total

    def backup(self, dest_path: str) -> None:
        """Consistent copy while the service is running (NFR-03)."""
        Path(dest_path).parent.mkdir(parents=True, exist_ok=True)
        dest = sqlite3.connect(dest_path)
        try:
            self.conn.backup(dest)
        finally:
            dest.close()

    def close(self) -> None:
        self.conn.close()
