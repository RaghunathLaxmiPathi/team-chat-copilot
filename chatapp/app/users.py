"""Users and administration (FR-02 to FR-05, DD-07, DD-19)."""
import re

from app import clock
from app.errors import Conflict, NotFound, ValidationFailed
from app.hub import CLOSE_DEACTIVATED
from app.ids import new_id
from app.serializers import public_user

USERNAME_RE = re.compile(r"^[a-z0-9._-]{3,32}$")
MIN_ADMINS = 2


class UserService:
    def __init__(self, db, audit, hub, copilot_auto_default: bool = True):
        self.db = db
        self.audit = audit
        self.hub = hub
        self.copilot_auto_default = copilot_auto_default

    def get(self, user_id: str) -> dict | None:
        return self.db.q_one("SELECT * FROM users WHERE id = ?", (user_id,))

    def get_by_username(self, username: str) -> dict | None:
        return self.db.q_one("SELECT * FROM users WHERE username = ?", (username,))

    def list_all(self) -> list[dict]:
        rows = self.db.q_all("SELECT * FROM users ORDER BY display_name COLLATE NOCASE, username")
        return [public_user(r) for r in rows]

    def active_admin_count(self) -> int:
        return self.db.scalar("SELECT COUNT(*) FROM users WHERE is_admin = 1 AND status = 'active'")

    def create(self, actor_id: str, username: str, display_name: str, is_admin: bool = False) -> dict:
        username = (username or "").strip()
        display_name = (display_name or "").strip()
        if not USERNAME_RE.match(username):
            raise ValidationFailed("User name must be 3 to 32 characters: a-z, 0-9, dot, dash, underscore.")
        if not 1 <= len(display_name) <= 60:
            raise ValidationFailed("Display name must be 1 to 60 characters.")
        if self.get_by_username(username):
            raise Conflict("That user name is already taken.")
        uid = new_id()
        with self.db.transaction():
            self.db.exec(
                "INSERT INTO users (id, username, display_name, is_admin, copilot_auto, status, created_at) "
                "VALUES (?, ?, ?, ?, ?, 'active', ?)",
                (uid, username, display_name, 1 if is_admin else 0, 1 if self.copilot_auto_default else 0, clock.iso()),
            )
            self.audit.record(actor_id, "user.create", "user", uid, {"username": username, "is_admin": is_admin})
        return public_user(self.get(uid))

    def set_admin(self, actor_id: str, user_id: str, is_admin: bool) -> dict:
        with self.db.transaction():
            user = self.get(user_id)
            if not user:
                raise NotFound("User not found.")
            if user["status"] != "active":
                raise Conflict("That user is deactivated.")
            if bool(user["is_admin"]) == is_admin:
                return public_user(user)
            if not is_admin and self.active_admin_count() - 1 < MIN_ADMINS:
                raise Conflict("There must always be at least two administrators.")
            self.db.exec("UPDATE users SET is_admin = ? WHERE id = ?", (1 if is_admin else 0, user_id))
            self.audit.record(actor_id, "user.role", "user", user_id, {"is_admin": is_admin})
        return public_user(self.get(user_id))

    def deactivate(self, actor_id: str, user_id: str) -> dict:
        with self.db.transaction():
            user = self.get(user_id)
            if not user:
                raise NotFound("User not found.")
            if user["id"] == actor_id:
                raise Conflict("You cannot deactivate yourself.")
            if user["is_bot"]:
                raise Conflict("The assistant cannot be deactivated. Turn it off with CHATAPP_COPILOT=false.")
            if user["status"] == "deactivated":
                return public_user(user)
            if user["is_admin"] and self.active_admin_count() - 1 < MIN_ADMINS:
                raise Conflict("There must always be at least two administrators.")
            now = clock.iso()
            self.db.exec("UPDATE users SET status = 'deactivated', deactivated_at = ? WHERE id = ?", (now, user_id))
            # Leave groups and channels. Direct messages keep their two members (F-01).
            self.db.exec(
                "UPDATE memberships SET to_seq = (SELECT last_seq FROM conversations c "
                "WHERE c.id = memberships.conversation_id), left_at = ? "
                "WHERE user_id = ? AND to_seq IS NULL AND conversation_id IN "
                "(SELECT id FROM conversations WHERE type IN ('group', 'channel'))",
                (now, user_id),
            )
            self.audit.record(actor_id, "user.deactivate", "user", user_id, {})
        self.hub.disconnect_user(user_id, CLOSE_DEACTIVATED)
        return public_user(self.get(user_id))

    def set_copilot_prefs(self, user_id: str, auto: bool | None = None, history: bool | None = None) -> dict:
        if auto is not None:
            self.db.exec("UPDATE users SET copilot_auto = ? WHERE id = ?", (1 if auto else 0, user_id))
        if history is not None:
            self.db.exec("UPDATE users SET copilot_history = ? WHERE id = ?", (1 if history else 0, user_id))
        return public_user(self.get(user_id))

    def seed(self, admin_usernames, member_usernames) -> None:
        """First start: create the configured administrators and sample members (lab only, risk R-18)."""
        for name in admin_usernames:
            if not self.get_by_username(name):
                self.create("system", name, name.capitalize(), is_admin=True)
        for name in member_usernames:
            if not self.get_by_username(name):
                self.create("system", name, name.capitalize(), is_admin=False)
        if self.active_admin_count() < MIN_ADMINS:
            raise RuntimeError("At least two administrators are required (set CHATAPP_ADMIN_USERNAMES).")
