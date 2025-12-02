"""Optimized user display module with indexing, formatting profiles, filtering, and robust logging.

This module preserves the public function names of the baseline implementation while
adding a high-performance, extensible architecture.
"""

from __future__ import annotations

import copy
import json
import logging
from dataclasses import dataclass, field
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
    Union,
)

LOG_MARKER_INFO = "[USER-INFO]"
LOG_MARKER_WARN = "[USER-WARN]"
LOG_MARKER_ERROR = "[USER-ERROR]"

DEFAULT_FIELDS: Sequence[str] = (
    "id",
    "name",
    "email",
    "role",
    "status",
    "join_date",
    "last_login",
)

# Human-friendly labels for compact profile (maintains baseline format)
FIELD_LABELS: Dict[str, str] = {
    "id": "ID",
    "name": "Name",
    "email": "Email",
    "role": "Role",
    "status": "Status",
    "join_date": "JoinDate",
    "last_login": "LastLogin",
}


# ----------------------------------------------------------------------------
# Logging helpers
# ----------------------------------------------------------------------------
logger = logging.getLogger("user_display")
# Add a NullHandler by default to avoid "No handler found" warnings.
if not logger.handlers:
    logger.addHandler(logging.NullHandler())
logger.setLevel(logging.INFO)


def _get_logger(custom_logger: Optional[logging.Logger]) -> logging.Logger:
    return custom_logger or logger


# ----------------------------------------------------------------------------
# Filtering
# ----------------------------------------------------------------------------
@dataclass(frozen=True)
class UserFilterCriteria:
    """Criteria container for user filtering.

    Attributes:
        role: Exact role match required.
        status: Exact status match required.
        name_contains: Substring to search for in the name field.
        role_prefix: Prefix that the role must start with.
        case_sensitive: Whether textual comparisons are case-sensitive.
        extra: Additional callables taking a user mapping and returning bool.
    """

    role: Optional[str] = None
    status: Optional[str] = None
    name_contains: Optional[str] = None
    role_prefix: Optional[str] = None
    case_sensitive: bool = False
    extra: Sequence[Callable[[Mapping[str, Any]], bool]] = field(default_factory=tuple)


class UserFilter:
    """Composable filter for users.

    This object encapsulates a list of predicate callables. It can be extended
    without modifying existing logic by adding more predicates.
    """

    def __init__(
        self,
        predicates: Optional[Sequence[Callable[[Mapping[str, Any]], bool]]] = None,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self._predicates: List[Callable[[Mapping[str, Any]], bool]] = list(predicates or [])
        self._logger = _get_logger(logger)

    @classmethod
    def from_criteria(
        cls,
        criteria: Union[UserFilterCriteria, Mapping[str, Any]],
        logger: Optional[logging.Logger] = None,
    ) -> "UserFilter":
        """Construct a UserFilter from criteria.

        Args:
            criteria: UserFilterCriteria or mapping with keys like role, status,
                name, name_contains, role_prefix, case_sensitive.
        """

        if isinstance(criteria, UserFilterCriteria):
            case_sensitive = criteria.case_sensitive
            role_expected = criteria.role
            status_expected = criteria.status
            name_contains = criteria.name_contains
            role_prefix = criteria.role_prefix
            extra_predicates = list(criteria.extra)
        else:
            case_sensitive = bool(criteria.get("case_sensitive", False))
            role_expected = criteria.get("role")
            status_expected = criteria.get("status")
            # support both 'name' (legacy) and 'name_contains'
            name_contains = criteria.get("name_contains", criteria.get("name"))
            role_prefix = criteria.get("role_prefix")
            extra_predicates = []  # mappings cannot embed callables safely

        def _normalize(text: str) -> str:
            return text if case_sensitive else text.lower()

        preds: List[Callable[[Mapping[str, Any]], bool]] = []

        if role_expected is not None:
            role_norm = _normalize(str(role_expected))

            def role_pred(user: Mapping[str, Any]) -> bool:
                try:
                    val = user.get("role") if isinstance(user, Mapping) else user["role"]
                    return _normalize(str(val)) == role_norm
                except Exception:
                    return False

            preds.append(role_pred)

        if status_expected is not None:
            status_norm = _normalize(str(status_expected))

            def status_pred(user: Mapping[str, Any]) -> bool:
                try:
                    val = user.get("status") if isinstance(user, Mapping) else user["status"]
                    return _normalize(str(val)) == status_norm
                except Exception:
                    return False

            preds.append(status_pred)

        if name_contains is not None:
            needle = _normalize(str(name_contains))

            def name_pred(user: Mapping[str, Any]) -> bool:
                try:
                    val = user.get("name") if isinstance(user, Mapping) else user["name"]
                    return needle in _normalize(str(val))
                except Exception:
                    return False

            preds.append(name_pred)

        if role_prefix is not None:
            prefix = _normalize(str(role_prefix))

            def role_prefix_pred(user: Mapping[str, Any]) -> bool:
                try:
                    val = user.get("role") if isinstance(user, Mapping) else user["role"]
                    return _normalize(str(val)).startswith(prefix)
                except Exception:
                    return False

            preds.append(role_prefix_pred)

        preds.extend(extra_predicates)
        return cls(predicates=preds, logger=logger)

    def add(self, predicate: Callable[[Mapping[str, Any]], bool]) -> None:
        self._predicates.append(predicate)

    def matches(self, user: Mapping[str, Any]) -> bool:
        for pred in self._predicates:
            try:
                if not pred(user):
                    return False
            except Exception as exc:  # defensive robustness
                self._logger.warning("%s predicate failed: %s", LOG_MARKER_WARN, exc)
                return False
        return True


# ----------------------------------------------------------------------------
# UserStore
# ----------------------------------------------------------------------------
class UserStore:
    """In-memory indexed user store.

    Supports efficient ID lookups (O(1)), snapshotting, iteration, and composable
    filtering. Users are stored as shallow copies of the provided mappings to
    avoid external mutation side effects.
    """

    def __init__(
        self,
        users: Optional[Iterable[Mapping[str, Any]]] = None,
        validators: Optional[Sequence[Callable[[Mapping[str, Any]], bool]]] = None,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self._logger = _get_logger(logger)
        self._validators: List[Callable[[Mapping[str, Any]], bool]] = list(validators or [])
        self._users: List[Dict[str, Any]] = []
        self._index_by_id: Dict[Any, Dict[str, Any]] = {}
        if users:
            self.extend(users)

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------
    def _is_valid(self, user: Mapping[str, Any]) -> bool:
        for validator in self._validators:
            try:
                if not validator(user):
                    self._logger.warning("%s validator failed for user %s", LOG_MARKER_WARN, user)
                    return False
            except Exception as exc:
                self._logger.error("%s validator exception for user %s: %s", LOG_MARKER_ERROR, user, exc)
                return False
        return True

    # ------------------------------------------------------------------
    # Mutation
    # ------------------------------------------------------------------
    def add(self, user: Mapping[str, Any]) -> bool:
        """Add a user to the store (shallow copy). Returns True if added."""
        if not self._is_valid(user):
            return False
        user_copy = dict(user)
        uid = user_copy.get("id")
        if uid is not None:
            self._index_by_id[uid] = user_copy
        else:
            self._logger.warning("%s user missing 'id' field: %s", LOG_MARKER_WARN, user)
        self._users.append(user_copy)
        return True

    def extend(self, users: Iterable[Mapping[str, Any]]) -> int:
        count = 0
        for user in users:
            if self.add(user):
                count += 1
        return count

    # ------------------------------------------------------------------
    # Accessors
    # ------------------------------------------------------------------
    def get_user_by_id(self, user_id: Any) -> Optional[Dict[str, Any]]:
        return self._index_by_id.get(user_id)

    def __iter__(self) -> Iterator[Dict[str, Any]]:
        return iter(self._users)

    def iter(self) -> Iterator[Dict[str, Any]]:
        return self.__iter__()

    def __len__(self) -> int:  # pragma: no cover - trivial
        return len(self._users)

    def snapshot(self, deep: bool = True) -> "UserStore":
        users_copy = copy.deepcopy(self._users) if deep else list(self._users)
        return UserStore(users_copy, validators=self._validators, logger=self._logger)

    def copy(self) -> "UserStore":
        return self.snapshot(deep=False)

    def filter(
        self,
        criteria: Optional[Union[UserFilter, UserFilterCriteria, Mapping[str, Any]]] = None,
    ) -> Iterator[Dict[str, Any]]:
        if criteria is None:
            yield from self._users
            return
        if isinstance(criteria, UserFilter):
            filt = criteria
        else:
            filt = UserFilter.from_criteria(criteria)
        for user in self._users:
            if filt.matches(user):
                yield user


# ----------------------------------------------------------------------------
# Formatting helpers
# ----------------------------------------------------------------------------
def _safe_get(user: Mapping[str, Any], key: str, default: Any = "<missing>") -> Any:
    try:
        if isinstance(user, Mapping):
            return user.get(key, default)
        return user[key]  # type: ignore[index]
    except Exception:
        return default


def format_user(
    user: Mapping[str, Any],
    *,
    profile: str = "compact",
    fields: Optional[Sequence[str]] = None,
    case_sensitive: bool = True,
) -> str:
    """Format a user mapping according to the chosen profile.

    Args:
        user: User mapping.
        profile: One of {"compact", "verbose", "json"}.
        fields: Optional subset of fields; defaults to DEFAULT_FIELDS.
        case_sensitive: No-op for now (placeholder for future field name handling).
    """

    selected_fields = fields or DEFAULT_FIELDS

    if profile == "compact":
        # Efficient string assembly with join
        parts = []
        for field in selected_fields:
            val = _safe_get(user, field)
            label = FIELD_LABELS.get(field, field)
            parts.append(f"{label}:{val}")
        return "|".join(parts)

    if profile == "verbose":
        lines = []
        for field in selected_fields:
            val = _safe_get(user, field)
            lines.append(f"  {field.capitalize()}: {val}")
        return "\n".join(lines)

    if profile == "json":
        data = {field: _safe_get(user, field, None) for field in selected_fields}
        return json.dumps(data, separators=(",", ":"))

    raise ValueError(f"Unknown profile: {profile}")


# ----------------------------------------------------------------------------
# Public functions (backward compatible signatures with enhancements)
# ----------------------------------------------------------------------------
def display_users(
    users: Union[Iterable[Mapping[str, Any]], UserStore],
    show_all: bool = True,
    verbose: bool = False,
    profile: str = "compact",
    fields: Optional[Sequence[str]] = None,
    criteria: Optional[Union[UserFilter, UserFilterCriteria, Mapping[str, Any]]] = None,
    validators: Optional[Sequence[Callable[[Mapping[str, Any]], bool]]] = None,
    case_sensitive: bool = False,
    logger: Optional[logging.Logger] = None,
) -> str:
    """Display users with optional filtering and formatting profiles.

    Args:
        users: Iterable of user mappings or a UserStore.
        show_all: Append processed count tail (legacy behavior).
        verbose: Print per-user processing messages (legacy behavior) and log info.
        profile: Formatting profile (compact, verbose, json).
        fields: Optional subset of fields to include.
        criteria: Filtering criteria (UserFilter/UserFilterCriteria/dict).
        validators: Optional validators applied if a UserStore is built internally.
        case_sensitive: Applies to filtering.
        logger: Optional logger instance.
    """

    log = _get_logger(logger)

    # Normalize users to an iterable; if not a UserStore, we may wrap one to enable efficient lookups and validation
    internal_store: Optional[UserStore] = None
    if isinstance(users, UserStore):
        iterable: Iterable[Mapping[str, Any]] = users
    else:
        # Build an internal store to leverage validation and consistent behavior
        internal_store = UserStore(users, validators=validators, logger=log)
        iterable = internal_store

    # Prepare filter
    filt: Optional[UserFilter] = None
    if criteria is not None:
        if isinstance(criteria, UserFilter):
            filt = criteria
        else:
            # enforce case sensitivity setting
            if isinstance(criteria, Mapping):
                crit_dict = dict(criteria)
                crit_dict.setdefault("case_sensitive", case_sensitive)
                criteria = crit_dict
            elif isinstance(criteria, UserFilterCriteria):
                # replace with new instance with case_sensitive if overridden
                criteria = UserFilterCriteria(
                    role=criteria.role,
                    status=criteria.status,
                    name_contains=criteria.name_contains,
                    role_prefix=criteria.role_prefix,
                    case_sensitive=case_sensitive if case_sensitive is not None else criteria.case_sensitive,
                    extra=criteria.extra,
                )
            filt = UserFilter.from_criteria(criteria)

    lines: List[str] = []
    processed_count = 0

    for user in iterable:
        if filt is not None and not filt.matches(user):
            continue
        if verbose:
            uid = _safe_get(user, "id", "<no-id>")
            print(f"Processing user {uid}...")
            log.info("%s processing user %s", LOG_MARKER_INFO, uid)
        try:
            formatted = format_user(user, profile=profile, fields=fields)
            lines.append(formatted)
            processed_count += 1
        except Exception as exc:
            log.error("%s failed to format user %s: %s", LOG_MARKER_ERROR, user, exc)
            # continue processing other users

    if show_all:
        lines.append(f"\n[INFO] Processed {processed_count} users.")

    return "\n".join(lines)


def get_user_by_id(
    users: Union[Iterable[Mapping[str, Any]], UserStore],
    user_id: Any,
) -> Optional[Mapping[str, Any]]:
    """Fast lookup by ID when using UserStore; falls back to linear search.

    Args:
        users: Iterable or UserStore.
        user_id: The ID to search for.
    Returns:
        Matching user mapping or None.
    """
    if isinstance(users, UserStore):
        return users.get_user_by_id(user_id)

    # Fallback: build a transient index for one-off lookup
    try:
        return next((u for u in users if _safe_get(u, "id") == user_id), None)
    except TypeError:
        # users may be a generator; iterate explicitly
        for u in users:
            if _safe_get(u, "id") == user_id:
                return u
    return None


def filter_users(
    users: Union[Iterable[Mapping[str, Any]], UserStore],
    criteria: Optional[Union[UserFilter, UserFilterCriteria, Mapping[str, Any]]] = None,
) -> List[Mapping[str, Any]]:
    """Filter users with composable criteria; returns a list (legacy behavior)."""
    if isinstance(users, UserStore):
        iterable = users.filter(criteria)
    else:
        if isinstance(criteria, UserFilter):
            filt = criteria
        else:
            filt = UserFilter.from_criteria(criteria or {}) if criteria else None
        iterable = (u for u in users if (filt.matches(u) if filt else True))
    return list(iterable)


def export_users_to_string(
    users: Union[Iterable[Mapping[str, Any]], UserStore],
    profile: str = "verbose",
    fields: Optional[Sequence[str]] = None,
    criteria: Optional[Union[UserFilter, UserFilterCriteria, Mapping[str, Any]]] = None,
    logger: Optional[logging.Logger] = None,
) -> str:
    """Export users to string efficiently with minimal temporary allocations."""

    log = _get_logger(logger)

    iterable: Iterable[Mapping[str, Any]]
    if isinstance(users, UserStore):
        iterable = users.filter(criteria)
    else:
        if isinstance(criteria, UserFilter):
            filt = criteria
        else:
            filt = UserFilter.from_criteria(criteria or {}) if criteria else None
        iterable = (u for u in users if (filt.matches(u) if filt else True))

    parts: List[str] = []
    parts.append("USER_EXPORT_START")
    parts.append("=" * 80)

    for user in iterable:
        try:
            formatted = format_user(user, profile=profile, fields=fields)
            if profile == "verbose":
                parts.append(f"User ID: {_safe_get(user, 'id', '<missing>')}")
                parts.append(formatted)
                parts.append("-" * 80)
            else:
                parts.append(formatted)
        except Exception as exc:
            log.error("%s failed to export user %s: %s", LOG_MARKER_ERROR, user, exc)

    parts.append("USER_EXPORT_END")
    return "\n".join(parts)


# Sample data for quick manual checks
sample_users = [
    {
        "id": 1,
        "name": "John Doe",
        "email": "john@example.com",
        "role": "Admin",
        "status": "Active",
        "join_date": "2023-01-15",
        "last_login": "2025-11-26",
    },
    {
        "id": 2,
        "name": "Jane Smith",
        "email": "jane@example.com",
        "role": "User",
        "status": "Inactive",
        "join_date": "2023-06-20",
        "last_login": "2025-11-20",
    },
]


if __name__ == "__main__":  # pragma: no cover - manual usage demonstration
    logging.basicConfig(level=logging.INFO)
    store = UserStore(sample_users)
    print(display_users(store, verbose=True))
    print(export_users_to_string(store, profile="json"))
