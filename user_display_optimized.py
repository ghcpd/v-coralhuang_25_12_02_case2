"""Optimized user display module with high performance, extensibility, and robustness.

Public API preserves backwards compatibility with the original:
- display_users
- get_user_by_id
- filter_users
- export_users_to_string

New capabilities:
- UserStore with O(1) lookups, snapshotting, deep copy, and streaming iterators
- Flexible filtering with partial match, multi-criteria, case sensitivity, and custom predicates
- Formatting profiles (compact, verbose, json) with optional field selection
- Structured logging with markers and graceful error handling
"""
from __future__ import annotations

import copy
import json
import logging
from dataclasses import dataclass
from io import StringIO
from typing import (
    Any,
    Callable,
    Dict,
    Iterable,
    Iterator,
    List,
    Mapping,
    MutableMapping,
    Optional,
    Sequence,
    Tuple,
    Union,
)

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logger = logging.getLogger("user_display")
if not logger.handlers:
    logger.addHandler(logging.NullHandler())
MARKER = "[USER_DISPLAY]"


def configure_logging(level: int = logging.INFO, handler: Optional[logging.Handler] = None) -> logging.Logger:
    """Configure module logger.

    Args:
        level: Logging level to set.
        handler: Optional handler to attach (clears existing handlers if provided).

    Returns:
        Configured logger instance.
    """
    logger.setLevel(level)
    if handler:
        logger.handlers.clear()
        logger.addHandler(handler)
    return logger


# ---------------------------------------------------------------------------
# Types & Defaults
# ---------------------------------------------------------------------------
User = Mapping[str, Any]
UserMutable = MutableMapping[str, Any]
DEFAULT_FIELDS: Tuple[str, ...] = (
    "id",
    "name",
    "email",
    "role",
    "status",
    "join_date",
    "last_login",
)

DEFAULT_LABELS: Dict[str, str] = {
    "id": "ID",
    "name": "Name",
    "email": "Email",
    "role": "Role",
    "status": "Status",
    "join_date": "JoinDate",
    "last_login": "LastLogin",
}


@dataclass(frozen=True)
class FilterCriteria:
    """Filter specification supporting multiple criteria and partial matching.

    Attributes:
        role: Exact role match.
        status: Exact status match.
        name_contains: Case-insensitive (by default) substring match against name.
        role_prefix: Prefix match against role.
        email_contains: Substring match against email.
        case_sensitive: Whether string comparisons are case sensitive.
        predicates: Optional additional callables returning bool for a user.
    """

    role: Optional[str] = None
    status: Optional[str] = None
    name_contains: Optional[str] = None
    role_prefix: Optional[str] = None
    email_contains: Optional[str] = None
    case_sensitive: bool = False
    predicates: Optional[Sequence[Callable[[User], bool]]] = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe_get(user: User, key: str, default: str = "<missing>") -> Any:
    try:
        return user[key]
    except Exception:
        return default


def _normalize(text: str, case_sensitive: bool) -> str:
    return text if case_sensitive else text.lower()


def _subset_user(user: User, fields: Optional[Sequence[str]]) -> Dict[str, Any]:
    if fields is None:
        return dict(user)
    return {k: _safe_get(user, k) for k in fields}


# ---------------------------------------------------------------------------
# Filtering
# ---------------------------------------------------------------------------

def _compile_predicates(criteria: Union[FilterCriteria, Mapping[str, Any], None]) -> Tuple[Sequence[Callable[[User], bool]], bool]:
    if criteria is None:
        return (), False

    if isinstance(criteria, Mapping) and not isinstance(criteria, FilterCriteria):
        crit = FilterCriteria(
            role=criteria.get("role"),
            status=criteria.get("status"),
            name_contains=criteria.get("name") or criteria.get("name_contains"),
            role_prefix=criteria.get("role_prefix"),
            email_contains=criteria.get("email_contains"),
            case_sensitive=bool(criteria.get("case_sensitive", False)),
            predicates=criteria.get("predicates"),
        )
    else:
        crit = criteria  # type: ignore

    cs = crit.case_sensitive
    predicates: List[Callable[[User], bool]] = []

    if crit.role is not None:
        val = _normalize(crit.role, cs)
        predicates.append(lambda u, val=val, cs=cs: _normalize(str(_safe_get(u, "role")), cs) == val)
    if crit.status is not None:
        val = _normalize(crit.status, cs)
        predicates.append(lambda u, val=val, cs=cs: _normalize(str(_safe_get(u, "status")), cs) == val)
    if crit.name_contains is not None:
        val = _normalize(crit.name_contains, cs)
        predicates.append(lambda u, val=val, cs=cs: val in _normalize(str(_safe_get(u, "name")), cs))
    if crit.role_prefix is not None:
        val = _normalize(crit.role_prefix, cs)
        predicates.append(lambda u, val=val, cs=cs: _normalize(str(_safe_get(u, "role")), cs).startswith(val))
    if crit.email_contains is not None:
        val = _normalize(crit.email_contains, cs)
        predicates.append(lambda u, val=val, cs=cs: val in _normalize(str(_safe_get(u, "email")), cs))

    if crit.predicates:
        predicates.extend(list(crit.predicates))

    return predicates, cs


# ---------------------------------------------------------------------------
# UserStore
# ---------------------------------------------------------------------------

class UserStore:
    """In-memory indexed user store with validation and snapshotting.

    Args:
        users: Iterable of user mappings.
        validator: Optional callable to validate a user; returns bool.
        required_fields: Fields that must exist; defaults to DEFAULT_FIELDS.
        drop_invalid: Whether to drop invalid entries; otherwise they remain.
    """

    def __init__(
        self,
        users: Iterable[User],
        validator: Optional[Callable[[User], bool]] = None,
        required_fields: Sequence[str] = DEFAULT_FIELDS,
        drop_invalid: bool = True,
    ) -> None:
        self._required_fields: Tuple[str, ...] = tuple(required_fields)
        self._validator = validator
        self._drop_invalid = drop_invalid
        self._users: List[UserMutable] = []
        self._by_id: Dict[Any, UserMutable] = {}
        self._invalid_count: int = 0

        for user in users:
            valid = self._validate(user)
            if not valid:
                self._invalid_count += 1
                if drop_invalid:
                    logger.error("%s Invalid user dropped: %s", MARKER, user)
                    continue
                logger.error("%s Invalid user retained: %s", MARKER, user)
            stored_user: UserMutable = user if isinstance(user, MutableMapping) else dict(user)
            self._users.append(stored_user)
            uid = stored_user.get("id") if isinstance(stored_user, Mapping) else None
            if uid is not None:
                self._by_id[uid] = stored_user

    def _validate(self, user: User) -> bool:
        try:
            for field in self._required_fields:
                if field not in user:
                    logger.error("%s Missing required field '%s' in user: %s", MARKER, field, user)
                    return False
            if self._validator:
                return bool(self._validator(user))
            return True
        except Exception as exc:  # pragma: no cover - defensive
            logger.error("%s Validator error: %s", MARKER, exc, exc_info=True)
            return False

    @property
    def invalid_count(self) -> int:
        return self._invalid_count

    def snapshot(self) -> List[UserMutable]:
        """Return a deep copy snapshot of users."""
        return copy.deepcopy(self._users)

    def copy(self, deep: bool = False) -> "UserStore":
        """Return a (optionally deep) copy of the store."""
        users = copy.deepcopy(self._users) if deep else list(self._users)
        return UserStore(users, validator=self._validator, required_fields=self._required_fields, drop_invalid=self._drop_invalid)

    def get_user_by_id(self, user_id: Any) -> Optional[UserMutable]:
        """O(1) lookup by id."""
        return self._by_id.get(user_id)

    def iter_users(self) -> Iterator[UserMutable]:
        return iter(self._users)

    def __iter__(self) -> Iterator[UserMutable]:  # pragma: no cover - alias
        return self.iter_users()

    def __len__(self) -> int:
        return len(self._users)

    def filter(self, criteria: Union[FilterCriteria, Mapping[str, Any], Callable[[User], bool], None]) -> Iterator[UserMutable]:
        """Stream users matching criteria.

        Args:
            criteria: FilterCriteria, mapping, callable predicate, or None.
        Returns:
            Iterator over users that match.
        """
        if callable(criteria):
            predicate_list: Sequence[Callable[[User], bool]] = (criteria,)  # type: ignore
            _cs = False
        else:
            predicate_list, _cs = _compile_predicates(criteria)

        if not predicate_list:
            return iter(self._users)

        def _all_predicates(user: User) -> bool:
            try:
                for pred in predicate_list:
                    if not pred(user):
                        return False
                return True
            except Exception as exc:  # pragma: no cover - defensive
                logger.error("%s Predicate error: %s", MARKER, exc, exc_info=True)
                return False

        return (u for u in self._users if _all_predicates(u))


# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------

def _format_compact(user: User, fields: Optional[Sequence[str]] = None) -> str:
    fields = tuple(fields) if fields is not None else DEFAULT_FIELDS
    parts = []
    for key in fields:
        label = DEFAULT_LABELS.get(key, key)
        parts.append(f"{label}:{_safe_get(user, key)}")
    return "|".join(parts)


def _format_verbose(user: User, fields: Optional[Sequence[str]] = None) -> str:
    fields = tuple(fields) if fields is not None else DEFAULT_FIELDS
    lines = ["User:"]
    for key in fields:
        lines.append(f"  {DEFAULT_LABELS.get(key, key)}: {_safe_get(user, key)}")
    return "\n".join(lines)


def _format_json(user: User, fields: Optional[Sequence[str]] = None) -> str:
    subset = _subset_user(user, fields)
    return json.dumps(subset, ensure_ascii=False)


Formatter = Callable[[User, Optional[Sequence[str]]], str]
def _format_export(user: User, fields: Optional[Sequence[str]] = None) -> str:
    fields = tuple(fields) if fields is not None else DEFAULT_FIELDS
    lines = []
    for key in fields:
        label = DEFAULT_LABELS.get(key, key)
        prefix = "User ID" if key == "id" else label
        indent = "" if key == "id" else "  "
        lines.append(f"{indent}{prefix}: {_safe_get(user, key)}")
    lines.append("-" * 100)
    return "\n".join(lines)


FORMATTERS: Dict[str, Formatter] = {
    "compact": _format_compact,
    "verbose": _format_verbose,
    "json": _format_json,
    "export": _format_export,
}


def get_formatter(profile: Union[str, Formatter]) -> Formatter:
    if callable(profile):
        return profile  # type: ignore
    try:
        return FORMATTERS[profile]
    except KeyError as exc:
        raise ValueError(f"Unknown profile '{profile}'. Valid: {list(FORMATTERS)}") from exc


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def display_users(
    users: Union[Iterable[User], UserStore],
    show_all: bool = True,
    verbose: bool = False,
    profile: Union[str, Formatter] = "compact",
    fields: Optional[Sequence[str]] = None,
    stream: Optional[Any] = None,
) -> str:
    """Display users efficiently using buffered patterns.

    Args:
        users: Iterable or UserStore.
        show_all: Append summary line if True.
        verbose: Print progress to stdout.
        profile: Formatting profile name or callable.
        fields: Optional field selection.
        stream: Optional file-like to write to; when provided returns empty string.

    Returns:
        Aggregated string (unless stream is provided).
    """
    store = users if isinstance(users, UserStore) else UserStore(users, drop_invalid=False)
    formatter = get_formatter(profile)
    buffer = StringIO()
    processed = 0
    errors = 0

    for user in store.iter_users():
        if verbose:
            print(f"Processing user {_safe_get(user, 'id')}")
        try:
            line = formatter(user, fields)
        except Exception as exc:  # pragma: no cover - defensive
            errors += 1
            logger.error("%s Formatting error: %s", MARKER, exc, exc_info=True)
            continue
        buffer.write(line)
        buffer.write("\n")
        processed += 1

    if show_all:
        buffer.write(f"\n[INFO] Processed {processed} users.")
        if errors:
            buffer.write(f" [WARN] Errors: {errors}.")
        buffer.write("\n")

    result = buffer.getvalue()
    if stream is not None:
        stream.write(result)
        return ""
    return result


def get_user_by_id(users: Union[Iterable[User], UserStore], user_id: Any) -> Optional[User]:
    """O(1) lookup by id using UserStore index."""
    store = users if isinstance(users, UserStore) else UserStore(users)
    return store.get_user_by_id(user_id)


def filter_users(
    users: Union[Iterable[User], UserStore], criteria: Union[FilterCriteria, Mapping[str, Any], Callable[[User], bool], None]
) -> List[User]:
    """Filter users with combined criteria.

    Returns:
        List of users matching criteria.
    """
    store = users if isinstance(users, UserStore) else UserStore(users, drop_invalid=False)
    return list(store.filter(criteria))


def export_users_to_string(
    users: Union[Iterable[User], UserStore], profile: Union[str, Formatter] = "export", fields: Optional[Sequence[str]] = None
) -> str:
    """Export users to string efficiently with minimal temporary allocations."""
    buffer = StringIO()
    buffer.write("USER_EXPORT_START\n")
    buffer.write("=" * 100 + "\n")
    # Reuse display logic without summary
    content = display_users(users, show_all=False, verbose=False, profile=profile, fields=fields)
    buffer.write(content)
    buffer.write("USER_EXPORT_END\n")
    return buffer.getvalue()


__all__ = [
    "UserStore",
    "FilterCriteria",
    "display_users",
    "get_user_by_id",
    "filter_users",
    "export_users_to_string",
    "configure_logging",
]
