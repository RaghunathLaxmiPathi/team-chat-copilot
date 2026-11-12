"""Who may see which message (DD-06, DD-08, FR-15). One rule, used everywhere."""

# A user may read a message only if they are a current member AND the message
# number falls inside one of their membership periods.
CURRENT_EXISTS = (
    "EXISTS (SELECT 1 FROM memberships cs WHERE cs.conversation_id = {m}.conversation_id "
    "AND cs.user_id = ? AND cs.to_seq IS NULL)"
)
VISIBLE_EXISTS = (
    "EXISTS (SELECT 1 FROM memberships vs WHERE vs.conversation_id = {m}.conversation_id "
    "AND vs.user_id = ? AND {m}.seq >= vs.from_seq AND (vs.to_seq IS NULL OR {m}.seq <= vs.to_seq))"
)


def visible_sql(alias: str = "m", with_current: bool = True) -> str:
    """SQL condition needing the user id bound twice (current, visible) or once."""
    parts = []
    if with_current:
        parts.append(CURRENT_EXISTS.format(m=alias))
    parts.append(VISIBLE_EXISTS.format(m=alias))
    return " AND ".join(parts)


def visible_params(user_id: str, with_current: bool = True) -> tuple:
    return (user_id, user_id) if with_current else (user_id,)


def is_current_member(db, user_id: str, conversation_id: str) -> bool:
    return db.scalar(
        "SELECT 1 FROM memberships WHERE conversation_id = ? AND user_id = ? AND to_seq IS NULL",
        (conversation_id, user_id),
    ) is not None


def can_see(db, user_id: str, conversation_id: str, seq: int) -> bool:
    if not is_current_member(db, user_id, conversation_id):
        return False
    return db.scalar(
        "SELECT 1 FROM memberships WHERE conversation_id = ? AND user_id = ? AND ? >= from_seq "
        "AND (to_seq IS NULL OR ? <= to_seq)",
        (conversation_id, user_id, seq, seq),
    ) is not None
