"""High-performance, maintainable user display utilities.

This module provides:
- UserStore: an in-memory indexed store with snapshotting and iterators
- flexible filtering (composable criteria)
- configurable formatting profiles and field selection
- robust error handling and centralized logging using a consistent marker

Design goals: O(1) lookups, linear-time display/export, minimal temporary allocations
and easy extension.
"""
from __future__ import annotations

import copy
import json
import logging
from io import StringIO
from typing import Any, Callable, Dict, Iterable, Iterator, List, Optional, Sequence

LOG_MARKER = "[USER-DISPLAY]"
logger = logging.getLogger("user_display")
if not logger.handlers:
    # Basic configuration — tests or consuming application can reconfigure
    ch = logging.StreamHandler()
    ch.setFormatter(logging.Formatter(f"%(asctime)s %(levelname)s {LOG_MARKER} %(message)s"))
    logger.addHandler(ch)
    logger.setLevel(logging.INFO)


User = Dict[str, Any]
Validator = Callable[[User], bool]


def _safe_get(user: User, key: str, default: Any = "<missing>") -> Any:
    """Return user[key] or default; log a marker when missing but continue.

    The goal is to keep code robust against malformed entries.
    """
    if key in user:
        return user[key]
    logger.warning(f"Missing key '%s' for user %s", key, user.get("id", "<unknown>"))
    return default


class UserStore:
    """A fast in-memory user store with indexed lookups and snapshotting.

    The store builds an O(1) index by user id and provides iteration and copying
    without exposing internal structures.

    Args:
        users: Iterable of dict-like user objects.
        validator: Optional callable to validate users; falsey return marks user as invalid
    """

    def __init__(self, users: Iterable[User] = (), validator: Optional[Validator] = None) -> None:
        self._validator = validator
        self._users: List[User] = []
        self._by_id: Dict[Any, User] = {}
        self._load(users)

    def _load(self, users: Iterable[User]) -> None:
        for u in users:
            try:
                if self._validator and not self._validator(u):
                    logger.warning("Validation failed for user %s; skipping", u.get("id", "<unknown>"))
                    continue
                uid = u.get("id")
                if uid is None:
                    logger.warning("User missing id — skipping entry: %s", u)
                    continue
                # Use the provided dict as-is for speed, but store a shallow copy to avoid caller mutation
                entry = dict(u)
                self._users.append(entry)
                self._by_id[uid] = entry
            except Exception as exc:  # noqa: BLE001 - defensive
                logger.exception("Error loading user entry: %s — skipping", exc)

    def snapshot(self) -> "UserStore":
        """Return a deep copy of the store.

        Useful when you want to mutate a copy without affecting the original.
        """
        return copy.deepcopy(self)

    def __len__(self) -> int:
        return len(self._users)

    def __iter__(self) -> Iterator[User]:
        # Exposure as an iterator to support streaming without copying
        return iter(self._users)

    def iter_users(self) -> Iterator[User]:
        for u in self._users:
            yield u

    def get_user_by_id(self, user_id: Any) -> Optional[User]:
        """O(1) lookup for user by id.

        Returns the stored user dict or None.
        """
        return self._by_id.get(user_id)

    def to_list(self) -> List[User]:
        """Return a shallow copy list of users (safe to iterate)."""
        return list(self._users)


class Criterion:
    """Abstract base for a single filter criterion.

    Implementations must provide matches(user) -> bool.
    """

    def matches(self, user: User) -> bool:  # pragma: no cover - interface
        raise NotImplementedError()


class AndCriteria(Criterion):
    def __init__(self, criteria: Sequence[Criterion]):
        self.criteria = criteria

    def matches(self, user: User) -> bool:
        for c in self.criteria:
            if not c.matches(user):
                return False
        return True


class RoleEquals(Criterion):
    def __init__(self, role: str, case_sensitive: bool = False):
        self.role = role
        self.case_sensitive = case_sensitive

    def matches(self, user: User) -> bool:
        value = _safe_get(user, "role", "")
        if not self.case_sensitive:
            return str(value).lower() == self.role.lower()
        return str(value) == self.role


class StatusEquals(Criterion):
    def __init__(self, status: str, case_sensitive: bool = False):
        self.status = status
        self.case_sensitive = case_sensitive

    def matches(self, user: User) -> bool:
        value = _safe_get(user, "status", "")
        if not self.case_sensitive:
            return str(value).lower() == self.status.lower()
        return str(value) == self.status


class NameContains(Criterion):
    def __init__(self, fragment: str, case_sensitive: bool = False):
        self.fragment = fragment
        self.case_sensitive = case_sensitive

    def matches(self, user: User) -> bool:
        value = _safe_get(user, "name", "")
        if not self.case_sensitive:
            return self.fragment.lower() in str(value).lower()
        return self.fragment in str(value)


class RolePrefix(Criterion):
    def __init__(self, prefix: str, case_sensitive: bool = False):
        self.prefix = prefix
        self.case_sensitive = case_sensitive

    def matches(self, user: User) -> bool:
        value = _safe_get(user, "role", "")
        if not self.case_sensitive:
            return str(value).lower().startswith(self.prefix.lower())
        return str(value).startswith(self.prefix)


def filter_users_iter(users: Iterable[User], criterion: Optional[Criterion]) -> Iterator[User]:
    """Stream users that match the provided criterion.

    If criterion is None, yields original users unchanged.
    """
    if criterion is None:
        for u in users:
            yield u
        return

    for u in users:
        try:
            if criterion.matches(u):
                yield u
        except Exception:
            logger.exception("Error evaluating filter for user %s - skipping", u.get("id", "<unknown>"))


_DEFAULT_FIELDS = ["id", "name", "email", "role", "status", "join_date", "last_login"]


def _format_compact(user: User, fields: Sequence[str]) -> str:
    parts: List[str] = []
    for f in fields:
        parts.append(f"{f}:{_safe_get(user, f)}")
    return "|".join(parts)


def _format_verbose(user: User, fields: Sequence[str]) -> str:
    sio = StringIO()
    try:
        uid = _safe_get(user, "id")
        sio.write(f"User ID: {uid}\n")
        for f in fields:
            if f == "id":
                continue
            sio.write(f"  {f}: {_safe_get(user, f)}\n")
        return sio.getvalue().rstrip("\n")
    finally:
        sio.close()


def _format_json(user: User, fields: Sequence[str]) -> str:
    out = {f: _safe_get(user, f) for f in fields}
    return json.dumps(out, separators=(",", ":"))


_PROFILES = {
    "compact": _format_compact,
    "verbose": _format_verbose,
    "json": _format_json,
}


def display_users(
    users: Iterable[User],
    *,
    profile: str = "compact",
    fields: Optional[Sequence[str]] = None,
    show_all: bool = True,
    logger_level: Optional[int] = None,
) -> str:
    """Render users to a human-readable string.

    Args:
        users: Iterable of user dicts or a UserStore.
        profile: one of 'compact', 'verbose', 'json'.
        fields: optional sequence of fields to include; defaults to a sensible set.
        show_all: append an informational line about count when True.
        logger_level: optional logging level to set for the duration of this call.

    Returns:
        A string with the formatted users joined by newlines.
    """
    if fields is None:
        fields = _DEFAULT_FIELDS

    formatter = _PROFILES.get(profile)
    if formatter is None:
        raise ValueError(f"Unknown profile: {profile}")

    prev_level = None
    if logger_level is not None:
        prev_level = logger.level
        logger.setLevel(logger_level)

    lines: List[str] = []
    processed = 0
    try:
        for u in users:
            try:
                lines.append(formatter(u, fields))
                processed += 1
            except Exception:
                logger.exception("Failed to format user %s - skipping", u.get("id", "<unknown>"))
                continue
        if show_all:
            lines.append(f"\n[INFO] Processed {processed} users.")
        return "\n".join(lines)
    finally:
        if prev_level is not None:
            logger.setLevel(prev_level)


def export_users_to_string(users: Iterable[User], fields: Optional[Sequence[str]] = None) -> str:
    """Export users to a compact multi-line string efficiently.

    This avoids creating a lot of temporary strings in loops.
    """
    if fields is None:
        fields = _DEFAULT_FIELDS

    sio = StringIO()
    try:
        sio.write("USER_EXPORT_START\n")
        sio.write("=" * 100 + "\n")
        for u in users:
            try:
                sio.write(_format_verbose(u, fields))
                sio.write("\n")
                sio.write("-" * 100 + "\n")
            except Exception:
                logger.exception("Error exporting user %s - skipping", u.get("id", "<unknown>"))
                continue
        sio.write("USER_EXPORT_END\n")
        return sio.getvalue()
    finally:
        sio.close()


__all__ = [
    "UserStore",
    "display_users",
    "export_users_to_string",
    "Criterion",
    "AndCriteria",
    "RoleEquals",
    "StatusEquals",
    "NameContains",
    "RolePrefix",
    "filter_users_iter",
]
