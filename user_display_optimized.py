"""Optimized user display implementation with high performance and extensibility.

This module provides a complete rewrite of the baseline user display system with:
- O(1) user lookups via indexed UserStore
- Zero artificial delays
- Efficient string assembly using buffers
- Configurable formatting profiles
- Flexible multi-criteria filtering
- Robust error handling and structured logging
- Full type hints and comprehensive docstrings
"""

import logging
import copy
from typing import Dict, List, Optional, Set, Callable, Iterator, Any, Literal
from io import StringIO
from dataclasses import dataclass, field
from enum import Enum


# Configure structured logging with [MARKER] patterns
logging.basicConfig(
    level=logging.INFO,
    format='[%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)


class FormatProfile(Enum):
    """Output formatting profiles for user display."""
    COMPACT = "compact"
    VERBOSE = "verbose"
    JSON_LIKE = "json_like"
    MINIMAL = "minimal"


@dataclass
class FilterCriteria:
    """Encapsulates filtering criteria with flexible matching rules.
    
    Attributes:
        role: Exact role match (if specified)
        status: Exact status match (if specified)
        name_contains: Partial name match (substring search)
        role_prefix: Role starts with this prefix
        case_sensitive: Whether string comparisons are case-sensitive
        custom_filter: Optional custom validation function
    """
    role: Optional[str] = None
    status: Optional[str] = None
    name_contains: Optional[str] = None
    role_prefix: Optional[str] = None
    case_sensitive: bool = False
    custom_filter: Optional[Callable[[Dict[str, Any]], bool]] = None


@dataclass
class UserStore:
    """In-memory indexed user store with O(1) lookups and efficient operations.
    
    This class provides:
    - Indexed lookups by user ID
    - Deep copying and snapshotting
    - Efficient iteration
    - Automatic index maintenance
    
    Attributes:
        users: List of user dictionaries
        _id_index: Internal mapping from user ID to user dict
    """
    users: List[Dict[str, Any]] = field(default_factory=list)
    _id_index: Dict[int, Dict[str, Any]] = field(default_factory=dict, init=False, repr=False)
    
    def __post_init__(self):
        """Build the index after initialization."""
        self._rebuild_index()
    
    def _rebuild_index(self) -> None:
        """Rebuild the ID index from current users list."""
        self._id_index.clear()
        for user in self.users:
            try:
                user_id = user.get('id')
                if user_id is not None:
                    self._id_index[user_id] = user
                else:
                    logger.warning("[MARKER] User missing 'id' field, skipping index entry")
            except Exception as e:
                logger.error(f"[MARKER] Error indexing user: {e}")
    
    def add_user(self, user: Dict[str, Any]) -> None:
        """Add a user to the store and update index.
        
        Args:
            user: User dictionary to add
        """
        self.users.append(user)
        try:
            user_id = user.get('id')
            if user_id is not None:
                self._id_index[user_id] = user
        except Exception as e:
            logger.error(f"[MARKER] Error adding user to index: {e}")
    
    def get_by_id(self, user_id: int) -> Optional[Dict[str, Any]]:
        """O(1) lookup of user by ID.
        
        Args:
            user_id: The user ID to search for
            
        Returns:
            User dictionary if found, None otherwise
        """
        return self._id_index.get(user_id)
    
    def snapshot(self) -> 'UserStore':
        """Create a deep copy of the entire store.
        
        Returns:
            A new UserStore with deep-copied user data
        """
        return UserStore(users=copy.deepcopy(self.users))
    
    def __iter__(self) -> Iterator[Dict[str, Any]]:
        """Enable efficient iteration over users."""
        return iter(self.users)
    
    def __len__(self) -> int:
        """Return the number of users in the store."""
        return len(self.users)


def _get_user_field(user: Dict[str, Any], field: str, default: str = "N/A") -> str:
    """Safely extract a field from user dict with error handling.
    
    Args:
        user: User dictionary
        field: Field name to extract
        default: Default value if field is missing
        
    Returns:
        Field value as string, or default if missing/error
    """
    try:
        value = user.get(field, default)
        return str(value) if value is not None else default
    except Exception as e:
        logger.warning(f"[MARKER] Error extracting field '{field}': {e}")
        return default


def display_users(
    users: List[Dict[str, Any]],
    show_all: bool = True,
    verbose: bool = False,
    format_profile: FormatProfile = FormatProfile.COMPACT,
    fields: Optional[Set[str]] = None
) -> str:
    """Display users with optimized string assembly and configurable formatting.
    
    This function uses efficient buffered string construction and eliminates
    all artificial delays. Supports multiple output formats and field selection.
    
    Args:
        users: List of user dictionaries to display
        show_all: Whether to include summary information
        verbose: Enable verbose logging during processing
        format_profile: Output formatting style
        fields: Optional set of fields to include (None = all fields)
        
    Returns:
        Formatted string representation of users
        
    Examples:
        >>> users = [{'id': 1, 'name': 'John', 'email': 'john@example.com', ...}]
        >>> output = display_users(users, format_profile=FormatProfile.VERBOSE)
        >>> print(output)
    """
    buffer = StringIO()
    processed_count = 0
    error_count = 0
    
    # Default fields if none specified
    all_fields = {'id', 'name', 'email', 'role', 'status', 'join_date', 'last_login'}
    selected_fields = fields if fields is not None else all_fields
    
    for user in users:
        try:
            if verbose:
                user_id = _get_user_field(user, 'id', 'unknown')
                logger.info(f"[MARKER] Processing user {user_id}")
            
            # Format based on profile
            if format_profile == FormatProfile.COMPACT:
                _write_compact_format(buffer, user, selected_fields)
            elif format_profile == FormatProfile.VERBOSE:
                _write_verbose_format(buffer, user, selected_fields)
            elif format_profile == FormatProfile.JSON_LIKE:
                _write_json_like_format(buffer, user, selected_fields)
            elif format_profile == FormatProfile.MINIMAL:
                _write_minimal_format(buffer, user, selected_fields)
            
            processed_count += 1
            
        except Exception as e:
            error_count += 1
            logger.error(f"[MARKER] Error processing user: {e}")
            # Continue processing remaining users
    
    # Add summary if requested
    if show_all:
        buffer.write(f"\n[INFO] Processed {processed_count} users")
        if error_count > 0:
            buffer.write(f" ({error_count} errors)")
        buffer.write(".\n")
    
    return buffer.getvalue()


def _write_compact_format(buffer: StringIO, user: Dict[str, Any], fields: Set[str]) -> None:
    """Write user in compact pipe-separated format.
    
    Args:
        buffer: String buffer to write to
        user: User dictionary
        fields: Fields to include
    """
    parts = []
    if 'id' in fields:
        parts.append(f"ID:{_get_user_field(user, 'id')}")
    if 'name' in fields:
        parts.append(f"Name:{_get_user_field(user, 'name')}")
    if 'email' in fields:
        parts.append(f"Email:{_get_user_field(user, 'email')}")
    if 'role' in fields:
        parts.append(f"Role:{_get_user_field(user, 'role')}")
    if 'status' in fields:
        parts.append(f"Status:{_get_user_field(user, 'status')}")
    if 'join_date' in fields:
        parts.append(f"JoinDate:{_get_user_field(user, 'join_date')}")
    if 'last_login' in fields:
        parts.append(f"LastLogin:{_get_user_field(user, 'last_login')}")
    
    buffer.write("|".join(parts))
    buffer.write("\n")


def _write_verbose_format(buffer: StringIO, user: Dict[str, Any], fields: Set[str]) -> None:
    """Write user in verbose multi-line format.
    
    Args:
        buffer: String buffer to write to
        user: User dictionary
        fields: Fields to include
    """
    buffer.write("User Details:\n")
    if 'id' in fields:
        buffer.write(f"  ID: {_get_user_field(user, 'id')}\n")
    if 'name' in fields:
        buffer.write(f"  Name: {_get_user_field(user, 'name')}\n")
    if 'email' in fields:
        buffer.write(f"  Email: {_get_user_field(user, 'email')}\n")
    if 'role' in fields:
        buffer.write(f"  Role: {_get_user_field(user, 'role')}\n")
    if 'status' in fields:
        buffer.write(f"  Status: {_get_user_field(user, 'status')}\n")
    if 'join_date' in fields:
        buffer.write(f"  Join Date: {_get_user_field(user, 'join_date')}\n")
    if 'last_login' in fields:
        buffer.write(f"  Last Login: {_get_user_field(user, 'last_login')}\n")
    buffer.write("-" * 60 + "\n")


def _write_json_like_format(buffer: StringIO, user: Dict[str, Any], fields: Set[str]) -> None:
    """Write user in JSON-like format.
    
    Args:
        buffer: String buffer to write to
        user: User dictionary
        fields: Fields to include
    """
    buffer.write("{\n")
    field_list = []
    if 'id' in fields:
        field_list.append(f'  "id": "{_get_user_field(user, "id")}"')
    if 'name' in fields:
        field_list.append(f'  "name": "{_get_user_field(user, "name")}"')
    if 'email' in fields:
        field_list.append(f'  "email": "{_get_user_field(user, "email")}"')
    if 'role' in fields:
        field_list.append(f'  "role": "{_get_user_field(user, "role")}"')
    if 'status' in fields:
        field_list.append(f'  "status": "{_get_user_field(user, "status")}"')
    if 'join_date' in fields:
        field_list.append(f'  "join_date": "{_get_user_field(user, "join_date")}"')
    if 'last_login' in fields:
        field_list.append(f'  "last_login": "{_get_user_field(user, "last_login")}"')
    
    buffer.write(",\n".join(field_list))
    buffer.write("\n}\n")


def _write_minimal_format(buffer: StringIO, user: Dict[str, Any], fields: Set[str]) -> None:
    """Write user in minimal format (ID and name only).
    
    Args:
        buffer: String buffer to write to
        user: User dictionary
        fields: Fields to include (only id and name respected)
    """
    user_id = _get_user_field(user, 'id') if 'id' in fields else ''
    name = _get_user_field(user, 'name') if 'name' in fields else ''
    
    if user_id and name:
        buffer.write(f"{user_id}: {name}\n")
    elif user_id:
        buffer.write(f"{user_id}\n")
    elif name:
        buffer.write(f"{name}\n")


def get_user_by_id(users: List[Dict[str, Any]], user_id: int) -> Optional[Dict[str, Any]]:
    """Backward-compatible O(n) user lookup by ID (use UserStore for O(1)).
    
    Note: This function maintains compatibility with the baseline implementation
    but performs linear search. For high performance, use UserStore.get_by_id().
    
    Args:
        users: List of user dictionaries
        user_id: User ID to search for
        
    Returns:
        User dictionary if found, None otherwise
    """
    for user in users:
        try:
            if user.get('id') == user_id:
                return user
        except Exception as e:
            logger.warning(f"[MARKER] Error comparing user ID: {e}")
    return None


def filter_users(
    users: List[Dict[str, Any]],
    criteria: Optional[FilterCriteria] = None,
    legacy_criteria: Optional[Dict[str, Any]] = None
) -> List[Dict[str, Any]]:
    """Filter users with flexible multi-criteria matching.
    
    Supports both new FilterCriteria objects and legacy dict-based criteria
    for backward compatibility. The filtering logic is clear and extensible.
    
    Args:
        users: List of user dictionaries to filter
        criteria: Modern FilterCriteria object with advanced options
        legacy_criteria: Legacy dict-based criteria (for backward compatibility)
        
    Returns:
        List of users matching all specified criteria
        
    Examples:
        >>> # Modern approach
        >>> criteria = FilterCriteria(role='Admin', status='Active')
        >>> admins = filter_users(users, criteria=criteria)
        
        >>> # Legacy approach (backward compatible)
        >>> admins = filter_users(users, legacy_criteria={'role': 'Admin'})
    """
    # Handle legacy criteria format
    if legacy_criteria is not None and criteria is None:
        criteria = FilterCriteria(
            role=legacy_criteria.get('role'),
            status=legacy_criteria.get('status'),
            name_contains=legacy_criteria.get('name')
        )
    
    # No filtering if no criteria provided
    if criteria is None:
        return users.copy()
    
    filtered = []
    for user in users:
        try:
            if _matches_criteria(user, criteria):
                filtered.append(user)
        except Exception as e:
            logger.warning(f"[MARKER] Error filtering user: {e}")
    
    return filtered


def _matches_criteria(user: Dict[str, Any], criteria: FilterCriteria) -> bool:
    """Check if a user matches all specified criteria.
    
    Args:
        user: User dictionary to check
        criteria: Filtering criteria
        
    Returns:
        True if user matches all criteria, False otherwise
    """
    # Role exact match
    if criteria.role is not None:
        user_role = _get_user_field(user, 'role', '')
        if user_role != criteria.role:
            return False
    
    # Status exact match
    if criteria.status is not None:
        user_status = _get_user_field(user, 'status', '')
        if user_status != criteria.status:
            return False
    
    # Name substring match
    if criteria.name_contains is not None:
        user_name = _get_user_field(user, 'name', '')
        search_str = criteria.name_contains
        
        if not criteria.case_sensitive:
            user_name = user_name.lower()
            search_str = search_str.lower()
        
        if search_str not in user_name:
            return False
    
    # Role prefix match
    if criteria.role_prefix is not None:
        user_role = _get_user_field(user, 'role', '')
        prefix = criteria.role_prefix
        
        if not criteria.case_sensitive:
            user_role = user_role.lower()
            prefix = prefix.lower()
        
        if not user_role.startswith(prefix):
            return False
    
    # Custom filter function
    if criteria.custom_filter is not None:
        if not criteria.custom_filter(user):
            return False
    
    return True


def export_users_to_string(
    users: List[Dict[str, Any]],
    fields: Optional[Set[str]] = None
) -> str:
    """Export users to string format with optimized buffered construction.
    
    This function eliminates temporary string allocations and uses efficient
    buffered writing for minimal memory overhead.
    
    Args:
        users: List of user dictionaries to export
        fields: Optional set of fields to include (None = all fields)
        
    Returns:
        Formatted export string
    """
    buffer = StringIO()
    all_fields = {'id', 'name', 'email', 'role', 'status', 'join_date', 'last_login'}
    selected_fields = fields if fields is not None else all_fields
    
    buffer.write("USER_EXPORT_START\n")
    buffer.write("=" * 100 + "\n")
    
    for user in users:
        try:
            if 'id' in selected_fields:
                buffer.write(f"User ID: {_get_user_field(user, 'id')}\n")
            if 'name' in selected_fields:
                buffer.write(f"  Name: {_get_user_field(user, 'name')}\n")
            if 'email' in selected_fields:
                buffer.write(f"  Email: {_get_user_field(user, 'email')}\n")
            if 'role' in selected_fields:
                buffer.write(f"  Role: {_get_user_field(user, 'role')}\n")
            if 'status' in selected_fields:
                buffer.write(f"  Status: {_get_user_field(user, 'status')}\n")
            if 'join_date' in selected_fields:
                buffer.write(f"  Join Date: {_get_user_field(user, 'join_date')}\n")
            if 'last_login' in selected_fields:
                buffer.write(f"  Last Login: {_get_user_field(user, 'last_login')}\n")
            
            buffer.write("-" * 100 + "\n")
        except Exception as e:
            logger.error(f"[MARKER] Error exporting user: {e}")
    
    buffer.write("USER_EXPORT_END\n")
    return buffer.getvalue()


# Sample data for testing
sample_users = [
    {
        'id': 1,
        'name': 'John Doe',
        'email': 'john@example.com',
        'role': 'Admin',
        'status': 'Active',
        'join_date': '2023-01-15',
        'last_login': '2025-11-26'
    },
    {
        'id': 2,
        'name': 'Jane Smith',
        'email': 'jane@example.com',
        'role': 'User',
        'status': 'Inactive',
        'join_date': '2023-06-20',
        'last_login': '2025-11-20'
    },
    {
        'id': 3,
        'name': 'Bob Johnson',
        'email': 'bob@example.com',
        'role': 'Moderator',
        'status': 'Active',
        'join_date': '2024-02-10',
        'last_login': '2025-11-25'
    },
    {
        'id': 4,
        'name': 'Alice Williams',
        'email': 'alice@example.com',
        'role': 'User',
        'status': 'Active',
        'join_date': '2024-05-12',
        'last_login': '2025-11-26'
    },
    {
        'id': 5,
        'name': 'Charlie Brown',
        'email': 'charlie@example.com',
        'role': 'User',
        'status': 'Active',
        'join_date': '2024-08-03',
        'last_login': '2025-11-24'
    },
]


if __name__ == "__main__":
    print("Optimized Implementation Demo:")
    print("=" * 100)
    
    # Demo 1: Basic display with compact format
    print("\n1. Compact Format:")
    print(display_users(sample_users, format_profile=FormatProfile.COMPACT))
    
    # Demo 2: UserStore with O(1) lookup
    print("\n2. UserStore O(1) Lookup:")
    store = UserStore(users=sample_users)
    user = store.get_by_id(3)
    print(f"Found user: {user['name']}" if user else "User not found")
    
    # Demo 3: Advanced filtering
    print("\n3. Advanced Filtering (Active Admins):")
    criteria = FilterCriteria(role='Admin', status='Active')
    filtered = filter_users(sample_users, criteria=criteria)
    print(display_users(filtered, show_all=False, format_profile=FormatProfile.MINIMAL))
    
    # Demo 4: Field selection
    print("\n4. Field Selection (Name and Status only):")
    print(display_users(sample_users, fields={'name', 'status'}))
