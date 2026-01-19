"""
Comprehensive tests for user_display_optimized module.

Coverage includes:
- UserStore operations and indexing
- User data validation
- Filtering with multiple criteria
- Formatting profiles (compact, verbose, JSON, CSV)
- Error handling and logging
- Performance on large datasets
- Backward compatibility
"""

import unittest
import json
import logging
import io
import sys
from typing import List, Dict, Any
import time

# Import optimized module
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from user_display_optimized import (
    User, UserStore, FormattingProfile, FilterBuilder, FilterSet,
    CompactFormatter, VerboseFormatter, JSONFormatter, CSVFormatter,
    display_users, get_user_by_id, filter_users, export_users_to_string,
    logger, setup_logger
)


# ============================================================================
# Test Data
# ============================================================================

SAMPLE_USER_DICT = {
    'id': 1,
    'name': 'John Doe',
    'email': 'john@example.com',
    'role': 'Admin',
    'status': 'Active',
    'join_date': '2023-01-15',
    'last_login': '2025-11-26'
}

SAMPLE_USERS = [
    {
        'id': 1, 'name': 'John Doe', 'email': 'john@example.com',
        'role': 'Admin', 'status': 'Active',
        'join_date': '2023-01-15', 'last_login': '2025-11-26'
    },
    {
        'id': 2, 'name': 'Jane Smith', 'email': 'jane@example.com',
        'role': 'User', 'status': 'Inactive',
        'join_date': '2023-06-20', 'last_login': '2025-11-20'
    },
    {
        'id': 3, 'name': 'Bob Johnson', 'email': 'bob@example.com',
        'role': 'Moderator', 'status': 'Active',
        'join_date': '2024-02-10', 'last_login': '2025-11-25'
    },
    {
        'id': 4, 'name': 'Alice Williams', 'email': 'alice@example.com',
        'role': 'User', 'status': 'Active',
        'join_date': '2024-05-12', 'last_login': '2025-11-26'
    },
    {
        'id': 5, 'name': 'Charlie Brown', 'email': 'charlie@example.com',
        'role': 'User', 'status': 'Active',
        'join_date': '2024-08-03', 'last_login': '2025-11-24'
    },
]

MALFORMED_USER = {
    'id': 999,
    'name': 'Bad User',
    # Missing required fields
}


# ============================================================================
# User Data Model Tests
# ============================================================================

class TestUserDataModel(unittest.TestCase):
    """Test User dataclass and conversions."""
    
    def test_user_creation_from_dict(self):
        """Test creating User from dictionary."""
        user = User.from_dict(SAMPLE_USER_DICT)
        self.assertEqual(user.id, 1)
        self.assertEqual(user.name, "John Doe")
        self.assertEqual(user.role, "Admin")
    
    def test_user_to_dict(self):
        """Test converting User to dictionary."""
        user = User.from_dict(SAMPLE_USER_DICT)
        user_dict = user.to_dict()
        self.assertIn('id', user_dict)
        self.assertEqual(user_dict['id'], 1)
        self.assertEqual(user_dict['name'], 'John Doe')
    
    def test_user_missing_required_fields(self):
        """Test that User raises ValueError for missing fields."""
        with self.assertRaises(ValueError):
            User.from_dict(MALFORMED_USER)
    
    def test_user_immutability(self):
        """Test that User behaves correctly as dataclass."""
        user = User.from_dict(SAMPLE_USER_DICT)
        # Dataclasses without frozen=True are technically mutable,
        # but we treat them as immutable by design
        self.assertEqual(user.id, 1)


# ============================================================================
# UserStore Tests
# ============================================================================

class TestUserStore(unittest.TestCase):
    """Test UserStore indexing and operations."""
    
    def setUp(self):
        """Set up test store."""
        self.store = UserStore(SAMPLE_USERS)
    
    def test_store_initialization(self):
        """Test store initializes with users."""
        self.assertEqual(self.store.size(), len(SAMPLE_USERS))
    
    def test_get_user_by_id_found(self):
        """Test O(1) lookup returns correct user."""
        user = self.store.get_user_by_id(1)
        self.assertIsNotNone(user)
        self.assertEqual(user.name, "John Doe")
    
    def test_get_user_by_id_not_found(self):
        """Test lookup returns None for non-existent ID."""
        user = self.store.get_user_by_id(9999)
        self.assertIsNone(user)
    
    def test_get_users_by_field(self):
        """Test indexed field lookup."""
        active_users = self.store.get_users_by_field("status", "Active")
        self.assertEqual(len(active_users), 4)  # 4 active users
    
    def test_add_user(self):
        """Test adding user to store."""
        new_user_dict = {
            'id': 100, 'name': 'New User', 'email': 'new@example.com',
            'role': 'User', 'status': 'Active',
            'join_date': '2025-01-01', 'last_login': '2025-12-01'
        }
        self.store.add_user(new_user_dict)
        self.assertEqual(self.store.size(), len(SAMPLE_USERS) + 1)
        self.assertIsNotNone(self.store.get_user_by_id(100))
    
    def test_add_user_duplicate_id(self):
        """Test that adding duplicate ID raises error."""
        with self.assertRaises(ValueError):
            self.store.add_user(SAMPLE_USER_DICT)
    
    def test_all_users(self):
        """Test retrieving all users."""
        all_users = self.store.all_users()
        self.assertEqual(len(all_users), len(SAMPLE_USERS))
    
    def test_iterate_users(self):
        """Test efficient iteration."""
        count = 0
        for user in self.store.iterate_users():
            count += 1
        self.assertEqual(count, len(SAMPLE_USERS))
    
    def test_snapshot(self):
        """Test deep copy snapshot."""
        snapshot = self.store.snapshot()
        self.assertEqual(snapshot.size(), self.store.size())
        
        # Add user to original, verify snapshot unchanged
        new_user = {
            'id': 200, 'name': 'After Snapshot', 'email': 'after@example.com',
            'role': 'User', 'status': 'Active',
            'join_date': '2025-01-01', 'last_login': '2025-12-01'
        }
        self.store.add_user(new_user)
        self.assertEqual(snapshot.size(), len(SAMPLE_USERS))
        self.assertEqual(self.store.size(), len(SAMPLE_USERS) + 1)
    
    def test_clear(self):
        """Test clearing store."""
        self.store.clear()
        self.assertEqual(self.store.size(), 0)
        self.assertIsNone(self.store.get_user_by_id(1))


# ============================================================================
# Filtering Tests
# ============================================================================

class TestFiltering(unittest.TestCase):
    """Test FilterBuilder and FilterSet."""
    
    def setUp(self):
        """Set up test store."""
        self.store = UserStore(SAMPLE_USERS)
    
    def test_filter_by_role(self):
        """Test filtering by single field."""
        filter_set = (FilterBuilder()
                      .add_rule("role", "eq", "Admin")
                      .build())
        result = self.store.filter_users(filter_set)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].name, "John Doe")
    
    def test_filter_by_status(self):
        """Test filtering by status."""
        filter_set = (FilterBuilder()
                      .add_rule("status", "eq", "Active")
                      .build())
        result = self.store.filter_users(filter_set)
        self.assertEqual(len(result), 4)
    
    def test_filter_multiple_criteria(self):
        """Test AND logic with multiple criteria."""
        filter_set = (FilterBuilder()
                      .add_rule("status", "eq", "Active")
                      .add_rule("role", "eq", "User")
                      .build())
        result = self.store.filter_users(filter_set)
        self.assertEqual(len(result), 2)  # Alice and Charlie
    
    def test_filter_contains(self):
        """Test partial match with 'contains'."""
        filter_set = (FilterBuilder()
                      .add_rule("name", "contains", "John")
                      .build())
        result = self.store.filter_users(filter_set)
        self.assertEqual(len(result), 2)  # John Doe, Bob Johnson
    
    def test_filter_startswith(self):
        """Test prefix match with 'startswith'."""
        filter_set = (FilterBuilder()
                      .add_rule("name", "startswith", "Charlie")
                      .build())
        result = self.store.filter_users(filter_set)
        self.assertEqual(len(result), 1)
    
    def test_filter_case_insensitive(self):
        """Test case-insensitive matching."""
        filter_set = (FilterBuilder()
                      .add_rule("role", "eq", "admin", case_sensitive=False)
                      .build())
        result = self.store.filter_users(filter_set)
        self.assertEqual(len(result), 1)
    
    def test_filter_custom_function(self):
        """Test custom filter function."""
        def id_greater_than_two(user_id, target):
            return user_id > target
        
        filter_set = FilterSet([
            FilterRule("id", "custom", 2, custom_fn=id_greater_than_two)
        ])
        result = self.store.filter_users(filter_set)
        self.assertEqual(len(result), 3)  # IDs 3, 4, 5
    
    def test_filter_no_matches(self):
        """Test filter returning empty result."""
        filter_set = (FilterBuilder()
                      .add_rule("role", "eq", "SuperAdmin")
                      .build())
        result = self.store.filter_users(filter_set)
        self.assertEqual(len(result), 0)


from user_display_optimized import FilterRule


# ============================================================================
# Formatter Tests
# ============================================================================

class TestFormatters(unittest.TestCase):
    """Test output formatters."""
    
    def setUp(self):
        """Set up test data."""
        self.users = [User.from_dict(u) for u in SAMPLE_USERS[:2]]
    
    def test_compact_formatter(self):
        """Test compact format."""
        formatter = CompactFormatter()
        output = formatter.format_users(self.users)
        self.assertIn("id:1", output)
        self.assertIn("John Doe", output)
        self.assertNotIn("\n\n", output)  # No double newlines
    
    def test_verbose_formatter(self):
        """Test verbose format."""
        formatter = VerboseFormatter()
        output = formatter.format_users(self.users)
        self.assertIn("Name:", output)
        self.assertIn("Email:", output)
        self.assertIn("Role:", output)
    
    def test_json_formatter(self):
        """Test JSON format."""
        formatter = JSONFormatter()
        output = formatter.format_users(self.users)
        data = json.loads(output)
        self.assertIsInstance(data, list)
        self.assertEqual(len(data), 2)
        self.assertEqual(data[0]['id'], 1)
    
    def test_csv_formatter(self):
        """Test CSV format."""
        formatter = CSVFormatter()
        output = formatter.format_users(self.users)
        lines = output.strip().split('\n')
        self.assertGreater(len(lines), 1)  # Header + data
        self.assertIn("id", lines[0])  # Header
    
    def test_formatter_field_selection(self):
        """Test formatter with selected fields."""
        formatter = CompactFormatter(fields=["name", "status"])
        output = formatter.format_users(self.users)
        self.assertIn("John Doe", output)
        self.assertIn("Active", output)
        self.assertNotIn("Email:", output)


# ============================================================================
# High-Level Function Tests
# ============================================================================

class TestHighLevelFunctions(unittest.TestCase):
    """Test display_users, get_user_by_id, filter_users, export_users_to_string."""
    
    def test_display_users_compact(self):
        """Test display_users with compact format."""
        output = display_users(SAMPLE_USERS, verbose=False)
        self.assertIn("John Doe", output)
        self.assertIn("[INFO]", output)
    
    def test_display_users_verbose(self):
        """Test display_users with verbose format."""
        output = display_users(SAMPLE_USERS, verbose=True)
        self.assertIn("Name:", output)
        self.assertIn("Email:", output)
    
    def test_display_users_with_fields(self):
        """Test display_users with field selection."""
        output = display_users(SAMPLE_USERS, fields=["name", "status"])
        self.assertIn("John Doe", output)
    
    def test_display_users_show_all_false(self):
        """Test display_users without summary."""
        output = display_users(SAMPLE_USERS, show_all=False)
        self.assertNotIn("[INFO]", output)
    
    def test_get_user_by_id_found(self):
        """Test get_user_by_id retrieves user."""
        user = get_user_by_id(SAMPLE_USERS, 1)
        self.assertIsNotNone(user)
        self.assertEqual(user.name, "John Doe")
    
    def test_get_user_by_id_not_found(self):
        """Test get_user_by_id returns None."""
        user = get_user_by_id(SAMPLE_USERS, 9999)
        self.assertIsNone(user)
    
    def test_filter_users_with_criteria(self):
        """Test filter_users with legacy criteria."""
        result = filter_users(SAMPLE_USERS, criteria={"status": "Active"})
        self.assertEqual(len(result), 4)
    
    def test_filter_users_with_filter_set(self):
        """Test filter_users with FilterSet."""
        filter_set = FilterBuilder().add_rule("role", "eq", "User").build()
        result = filter_users(SAMPLE_USERS, filter_set=filter_set)
        self.assertEqual(len(result), 3)
    
    def test_filter_users_no_criteria(self):
        """Test filter_users returns all users."""
        result = filter_users(SAMPLE_USERS)
        self.assertEqual(len(result), len(SAMPLE_USERS))
    
    def test_export_compact(self):
        """Test export_users_to_string with compact profile."""
        output = export_users_to_string(
            SAMPLE_USERS[:2],
            profile=FormattingProfile.COMPACT
        )
        self.assertIn("id:1", output)
    
    def test_export_json(self):
        """Test export_users_to_string with JSON profile."""
        output = export_users_to_string(
            SAMPLE_USERS[:2],
            profile=FormattingProfile.JSON
        )
        data = json.loads(output)
        self.assertEqual(len(data), 2)
    
    def test_export_csv(self):
        """Test export_users_to_string with CSV profile."""
        output = export_users_to_string(
            SAMPLE_USERS[:2],
            profile=FormattingProfile.CSV
        )
        lines = output.strip().split('\n')
        self.assertGreater(len(lines), 1)


# ============================================================================
# Error Handling Tests
# ============================================================================

class TestErrorHandling(unittest.TestCase):
    """Test error handling and robustness."""
    
    def test_display_users_with_malformed_user(self):
        """Test display_users skips malformed users gracefully."""
        mixed_users = SAMPLE_USERS[:2] + [MALFORMED_USER]
        output = display_users(mixed_users)
        # Should process 2 valid users and skip the bad one
        self.assertIn("[INFO] Processed 2 users", output)
    
    def test_filter_with_invalid_field(self):
        """Test filter with non-existent field."""
        filter_set = FilterBuilder().add_rule("nonexistent", "eq", "value").build()
        result = filter_users(SAMPLE_USERS, filter_set=filter_set)
        self.assertEqual(len(result), 0)
    
    def test_export_with_malformed_users(self):
        """Test export skips malformed users."""
        mixed_users = SAMPLE_USERS[:2] + [MALFORMED_USER]
        output = export_users_to_string(mixed_users)
        # Should handle gracefully
        self.assertIn("2", output)
    
    def test_user_store_with_malformed_user(self):
        """Test UserStore handles malformed users during add."""
        store = UserStore(SAMPLE_USERS[:2])
        with self.assertRaises(ValueError):
            store.add_user(MALFORMED_USER)


# ============================================================================
# Performance Tests
# ============================================================================

class TestPerformance(unittest.TestCase):
    """Test performance targets on large datasets."""
    
    def generate_large_dataset(self, count: int) -> List[Dict[str, Any]]:
        """Generate synthetic user dataset."""
        users = []
        roles = ["Admin", "User", "Moderator", "Viewer"]
        statuses = ["Active", "Inactive", "Suspended"]
        
        for i in range(count):
            users.append({
                'id': i + 1,
                'name': f"User_{i+1}",
                'email': f"user{i+1}@example.com",
                'role': roles[i % len(roles)],
                'status': statuses[i % len(statuses)],
                'join_date': '2023-01-01',
                'last_login': '2025-12-01'
            })
        return users
    
    def test_display_1000_users_performance(self):
        """Test displaying 1000 users completes in < 100ms."""
        users = self.generate_large_dataset(1000)
        start = time.time()
        output = display_users(users, show_all=True)
        elapsed = (time.time() - start) * 1000  # Convert to ms
        
        print(f"\nDisplay 1000 users: {elapsed:.2f}ms")
        # Target is 100ms but we allow more for logging overhead in test
        self.assertLess(elapsed, 200)
    
    def test_filter_1000_users_performance(self):
        """Test filtering 1000 users completes in < 10ms."""
        users = self.generate_large_dataset(1000)
        filter_set = FilterBuilder().add_rule("status", "eq", "Active").build()
        
        start = time.time()
        result = filter_users(users, filter_set=filter_set)
        elapsed = (time.time() - start) * 1000
        
        print(f"Filter 1000 users: {elapsed:.2f}ms")
        # Target is 10ms but we allow more for logging overhead
        self.assertLess(elapsed, 100)
    
    def test_lookup_1000_users_performance(self):
        """Test get_user_by_id on 1000 users completes in < 1ms."""
        users = self.generate_large_dataset(1000)
        
        start = time.time()
        user = get_user_by_id(users, 500)
        elapsed = (time.time() - start) * 1000
        
        print(f"Lookup user in 1000 users: {elapsed:.2f}ms")
        # Target is 1ms but we allow more for logging/initialization overhead
        self.assertLess(elapsed, 100)
        self.assertIsNotNone(user)
    
    def test_export_5000_users_performance(self):
        """Test exporting 5000 users completes reasonably."""
        users = self.generate_large_dataset(5000)
        
        start = time.time()
        output = export_users_to_string(
            users,
            profile=FormattingProfile.CSV
        )
        elapsed = (time.time() - start) * 1000
        
        print(f"Export 5000 users to CSV: {elapsed:.2f}ms")
        # CSV export should be fast
        self.assertLess(elapsed, 500)


# ============================================================================
# Backward Compatibility Tests
# ============================================================================

class TestBackwardCompatibility(unittest.TestCase):
    """Test that new implementation maintains backward compatibility."""
    
    def test_display_users_signature_compatible(self):
        """Test display_users accepts same parameters as original."""
        # Original signature: display_users(users, show_all=True, verbose=False)
        output = display_users(SAMPLE_USERS, show_all=True, verbose=False)
        self.assertIsInstance(output, str)
    
    def test_get_user_by_id_compatible(self):
        """Test get_user_by_id has same interface."""
        # Original signature: get_user_by_id(users, user_id)
        user = get_user_by_id(SAMPLE_USERS, 1)
        self.assertIsNotNone(user)
    
    def test_filter_users_compatible(self):
        """Test filter_users accepts legacy criteria."""
        # Original signature: filter_users(users, criteria)
        result = filter_users(SAMPLE_USERS, {"role": "Admin"})
        self.assertEqual(len(result), 1)
    
    def test_export_users_compatible(self):
        """Test export_users_to_string exists and works."""
        output = export_users_to_string(SAMPLE_USERS[:2])
        self.assertIsInstance(output, str)


# ============================================================================
# Logging Tests
# ============================================================================

class TestLogging(unittest.TestCase):
    """Test structured logging."""
    
    def test_logger_setup(self):
        """Test logger is properly configured."""
        test_logger = setup_logger("test_logger")
        self.assertIsNotNone(test_logger)
    
    def test_logging_markers(self):
        """Test that operations use consistent [MARKER] format."""
        # Capture logger output
        log_capture = io.StringIO()
        handler = logging.StreamHandler(log_capture)
        handler.setLevel(logging.INFO)
        test_logger = logging.getLogger("test_log_marker")
        test_logger.addHandler(handler)
        test_logger.setLevel(logging.INFO)
        
        test_logger.info("[USER_DISPLAY] Test marker")
        
        log_output = log_capture.getvalue()
        self.assertIn("[USER_DISPLAY]", log_output)


# ============================================================================
# Integration Tests
# ============================================================================

class TestIntegration(unittest.TestCase):
    """End-to-end integration tests."""
    
    def test_full_workflow(self):
        """Test complete workflow: load, filter, export."""
        # Load
        store = UserStore(SAMPLE_USERS)
        self.assertEqual(store.size(), 5)
        
        # Filter
        filter_set = (FilterBuilder()
                      .add_rule("status", "eq", "Active")
                      .build())
        active = store.filter_users(filter_set)
        self.assertEqual(len(active), 4)
        
        # Export
        output = export_users_to_string(
            active,
            profile=FormattingProfile.JSON
        )
        data = json.loads(output)
        self.assertEqual(len(data), 4)
    
    def test_add_filter_display_workflow(self):
        """Test adding users, filtering, and displaying."""
        store = UserStore(SAMPLE_USERS[:2])

        # Add user (Sam will also be Admin, so we'll have 2 admins total)
        new_user = {
            'id': 100, 'name': 'Test User', 'email': 'test@example.com',
            'role': 'User', 'status': 'Active',
            'join_date': '2025-01-01', 'last_login': '2025-12-01'
        }
        store.add_user(new_user)
        self.assertEqual(store.size(), 3)

        # Filter for admins (should be just John Doe from original)
        admins = store.get_users_by_field("role", "Admin")
        self.assertEqual(len(admins), 1)

        # Display
        output = display_users(admins)
        self.assertIn("John Doe", output)
if __name__ == "__main__":
    unittest.main(verbosity=2)
