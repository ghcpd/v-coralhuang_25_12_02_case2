"""Comprehensive test suite for user_display module.

Tests cover:
- Normal operations and edge cases
- Missing keys and malformed entries
- New formatting modes
- Multi-criteria filtering
- Error handling and logging
- Performance validation for large datasets
"""

import sys
import time
import logging
from io import StringIO
from typing import List, Dict, Any

import pytest

# Import both modules for comparison
sys.path.insert(0, '../')
import user_display_original
import user_display_optimized
from user_display_optimized import (
    UserStore, FilterCriteria, FormatProfile,
    display_users, get_user_by_id, filter_users,
    export_users_to_string
)


# Test fixtures
@pytest.fixture
def sample_users() -> List[Dict[str, Any]]:
    """Provide standard test user data."""
    return [
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
    ]


@pytest.fixture
def malformed_users() -> List[Dict[str, Any]]:
    """Provide user data with missing/malformed fields."""
    return [
        {'id': 1, 'name': 'Valid User', 'email': 'valid@example.com'},  # Missing fields
        {'name': 'No ID User', 'email': 'noid@example.com', 'role': 'User'},  # No ID
        {},  # Empty dict
        {'id': 4, 'name': None, 'email': None},  # None values
        {'id': 5, 'name': 'Partial', 'status': 'Active'},  # Some fields
    ]


@pytest.fixture
def large_dataset() -> List[Dict[str, Any]]:
    """Generate large dataset for performance testing."""
    return [
        {
            'id': i,
            'name': f'User{i}',
            'email': f'user{i}@example.com',
            'role': 'Admin' if i % 10 == 0 else 'User',
            'status': 'Active' if i % 2 == 0 else 'Inactive',
            'join_date': f'2024-{(i % 12) + 1:02d}-01',
            'last_login': f'2025-11-{(i % 28) + 1:02d}'
        }
        for i in range(1, 1001)
    ]


# ===== UserStore Tests =====

class TestUserStore:
    """Test suite for UserStore class."""
    
    def test_userstore_initialization(self, sample_users):
        """Test UserStore can be initialized with users."""
        store = UserStore(users=sample_users)
        assert len(store) == 3
        assert len(store._id_index) == 3
    
    def test_userstore_empty_initialization(self):
        """Test UserStore can be initialized empty."""
        store = UserStore()
        assert len(store) == 0
        assert len(store._id_index) == 0
    
    def test_userstore_o1_lookup(self, sample_users):
        """Test O(1) lookup by ID."""
        store = UserStore(users=sample_users)
        
        user = store.get_by_id(2)
        assert user is not None
        assert user['name'] == 'Jane Smith'
        
        user = store.get_by_id(999)
        assert user is None
    
    def test_userstore_add_user(self):
        """Test adding users dynamically."""
        store = UserStore()
        user = {'id': 1, 'name': 'Test User', 'email': 'test@example.com'}
        
        store.add_user(user)
        assert len(store) == 1
        assert store.get_by_id(1) == user
    
    def test_userstore_snapshot(self, sample_users):
        """Test deep copy snapshot functionality."""
        store = UserStore(users=sample_users)
        snapshot = store.snapshot()
        
        # Verify it's a separate instance
        assert snapshot is not store
        assert len(snapshot) == len(store)
        
        # Modify original and ensure snapshot unchanged
        store.users[0]['name'] = 'Modified'
        assert snapshot.users[0]['name'] == 'John Doe'
    
    def test_userstore_iteration(self, sample_users):
        """Test iteration over users."""
        store = UserStore(users=sample_users)
        count = 0
        for user in store:
            assert 'id' in user
            count += 1
        assert count == 3
    
    def test_userstore_malformed_users(self, malformed_users, caplog):
        """Test UserStore handles malformed users gracefully."""
        with caplog.at_level(logging.WARNING):
            store = UserStore(users=malformed_users)
            
            # Should not crash, but may log warnings
            assert len(store) == 5
            
            # Users with valid IDs should be indexed
            assert store.get_by_id(1) is not None
            assert store.get_by_id(4) is not None


# ===== Display Tests =====

class TestDisplayUsers:
    """Test suite for display_users function."""
    
    def test_display_compact_format(self, sample_users):
        """Test compact format output."""
        output = display_users(sample_users, format_profile=FormatProfile.COMPACT)
        
        assert 'ID:1' in output
        assert 'Name:John Doe' in output
        assert 'Email:john@example.com' in output
        assert 'Processed 3 users' in output
    
    def test_display_verbose_format(self, sample_users):
        """Test verbose format output."""
        output = display_users(sample_users, format_profile=FormatProfile.VERBOSE)
        
        assert 'User Details:' in output
        assert '  Name: John Doe' in output
        assert '---' in output
    
    def test_display_json_like_format(self, sample_users):
        """Test JSON-like format output."""
        output = display_users(sample_users, format_profile=FormatProfile.JSON_LIKE)
        
        assert '"id": "1"' in output
        assert '"name": "John Doe"' in output
        assert '{' in output and '}' in output
    
    def test_display_minimal_format(self, sample_users):
        """Test minimal format output."""
        output = display_users(sample_users, format_profile=FormatProfile.MINIMAL)
        
        assert '1: John Doe' in output
        assert '2: Jane Smith' in output
    
    def test_display_field_selection(self, sample_users):
        """Test display with field selection."""
        output = display_users(
            sample_users,
            format_profile=FormatProfile.COMPACT,
            fields={'id', 'name'}
        )
        
        assert 'ID:1' in output
        assert 'Name:John Doe' in output
        assert 'Email:' not in output
        assert 'Role:' not in output
    
    def test_display_show_all_flag(self, sample_users):
        """Test show_all flag controls summary."""
        output_with = display_users(sample_users, show_all=True)
        output_without = display_users(sample_users, show_all=False)
        
        assert 'Processed 3 users' in output_with
        assert 'Processed' not in output_without
    
    def test_display_malformed_entries(self, malformed_users, caplog):
        """Test display handles malformed entries without crashing."""
        with caplog.at_level(logging.WARNING):
            output = display_users(malformed_users)
            
            # Should not crash
            assert output is not None
            assert 'N/A' in output  # Default values used
    
    def test_display_empty_list(self):
        """Test display with empty user list."""
        output = display_users([])
        assert 'Processed 0 users' in output
    
    def test_display_verbose_logging(self, sample_users, caplog):
        """Test verbose logging during display."""
        with caplog.at_level(logging.INFO):
            display_users(sample_users, verbose=True)
            
            # Check that processing messages were logged
            assert '[MARKER] Processing user' in caplog.text


# ===== Lookup Tests =====

class TestGetUserById:
    """Test suite for get_user_by_id function."""
    
    def test_get_user_by_id_found(self, sample_users):
        """Test finding existing user by ID."""
        user = get_user_by_id(sample_users, 2)
        assert user is not None
        assert user['name'] == 'Jane Smith'
    
    def test_get_user_by_id_not_found(self, sample_users):
        """Test searching for non-existent user."""
        user = get_user_by_id(sample_users, 999)
        assert user is None
    
    def test_get_user_by_id_empty_list(self):
        """Test lookup in empty list."""
        user = get_user_by_id([], 1)
        assert user is None
    
    def test_get_user_by_id_malformed(self, malformed_users, caplog):
        """Test lookup with malformed data doesn't crash."""
        with caplog.at_level(logging.WARNING):
            user = get_user_by_id(malformed_users, 1)
            # Should return user if found, or None
            assert user is None or isinstance(user, dict)


# ===== Filter Tests =====

class TestFilterUsers:
    """Test suite for filter_users function."""
    
    def test_filter_by_role(self, sample_users):
        """Test filtering by exact role match."""
        criteria = FilterCriteria(role='Admin')
        filtered = filter_users(sample_users, criteria=criteria)
        
        assert len(filtered) == 1
        assert filtered[0]['name'] == 'John Doe'
    
    def test_filter_by_status(self, sample_users):
        """Test filtering by status."""
        criteria = FilterCriteria(status='Active')
        filtered = filter_users(sample_users, criteria=criteria)
        
        assert len(filtered) == 2
        assert all(u['status'] == 'Active' for u in filtered)
    
    def test_filter_by_name_contains(self, sample_users):
        """Test partial name matching."""
        criteria = FilterCriteria(name_contains='john')
        filtered = filter_users(sample_users, criteria=criteria)
        
        assert len(filtered) == 2  # John Doe and Bob Johnson
    
    def test_filter_case_sensitive(self, sample_users):
        """Test case-sensitive name filtering."""
        criteria_insensitive = FilterCriteria(name_contains='JOHN', case_sensitive=False)
        criteria_sensitive = FilterCriteria(name_contains='JOHN', case_sensitive=True)
        
        filtered_insensitive = filter_users(sample_users, criteria=criteria_insensitive)
        filtered_sensitive = filter_users(sample_users, criteria=criteria_sensitive)
        
        assert len(filtered_insensitive) == 2
        assert len(filtered_sensitive) == 0
    
    def test_filter_by_role_prefix(self, sample_users):
        """Test role prefix matching."""
        criteria = FilterCriteria(role_prefix='Mod')
        filtered = filter_users(sample_users, criteria=criteria)
        
        assert len(filtered) == 1
        assert filtered[0]['role'] == 'Moderator'
    
    def test_filter_multiple_criteria(self, sample_users):
        """Test combining multiple filter criteria."""
        criteria = FilterCriteria(role='User', status='Active')
        filtered = filter_users(sample_users, criteria=criteria)
        
        # Should find users who are both 'User' role AND 'Active' status
        assert all(u['role'] == 'User' and u['status'] == 'Active' for u in filtered)
    
    def test_filter_custom_function(self, sample_users):
        """Test custom filter function."""
        # Filter users whose ID is even
        criteria = FilterCriteria(custom_filter=lambda u: u.get('id', 0) % 2 == 0)
        filtered = filter_users(sample_users, criteria=criteria)
        
        assert len(filtered) == 1
        assert filtered[0]['id'] == 2
    
    def test_filter_legacy_criteria(self, sample_users):
        """Test backward compatibility with legacy dict criteria."""
        filtered = filter_users(sample_users, legacy_criteria={'role': 'Admin'})
        
        assert len(filtered) == 1
        assert filtered[0]['role'] == 'Admin'
    
    def test_filter_no_criteria(self, sample_users):
        """Test filtering with no criteria returns all users."""
        filtered = filter_users(sample_users)
        assert len(filtered) == len(sample_users)
    
    def test_filter_malformed_users(self, malformed_users, caplog):
        """Test filtering malformed users doesn't crash."""
        with caplog.at_level(logging.WARNING):
            criteria = FilterCriteria(role='User')
            filtered = filter_users(malformed_users, criteria=criteria)
            
            # Should not crash
            assert isinstance(filtered, list)


# ===== Export Tests =====

class TestExportUsers:
    """Test suite for export_users_to_string function."""
    
    def test_export_basic(self, sample_users):
        """Test basic export functionality."""
        output = export_users_to_string(sample_users)
        
        assert 'USER_EXPORT_START' in output
        assert 'USER_EXPORT_END' in output
        assert 'User ID: 1' in output
        assert 'Name: John Doe' in output
        assert '=' * 100 in output
    
    def test_export_field_selection(self, sample_users):
        """Test export with field selection."""
        output = export_users_to_string(sample_users, fields={'id', 'name'})
        
        assert 'User ID: 1' in output
        assert 'Name: John Doe' in output
        assert 'Email:' not in output
        assert 'Role:' not in output
    
    def test_export_empty_list(self):
        """Test exporting empty list."""
        output = export_users_to_string([])
        
        assert 'USER_EXPORT_START' in output
        assert 'USER_EXPORT_END' in output
    
    def test_export_malformed_users(self, malformed_users, caplog):
        """Test export handles malformed users gracefully."""
        with caplog.at_level(logging.ERROR):
            output = export_users_to_string(malformed_users)
            
            # Should not crash
            assert output is not None
            assert 'USER_EXPORT_START' in output


# ===== Performance Tests =====

class TestPerformance:
    """Test suite for performance validation."""
    
    def test_display_1000_users_performance(self, large_dataset):
        """Test displaying 1,000 users meets < 100ms target."""
        start = time.perf_counter()
        output = display_users(large_dataset, show_all=False)
        elapsed = (time.perf_counter() - start) * 1000  # Convert to ms
        
        assert output is not None
        assert elapsed < 100, f"Display took {elapsed:.2f}ms, expected < 100ms"
    
    def test_filter_1000_users_performance(self, large_dataset):
        """Test filtering 1,000 users meets < 10ms target."""
        criteria = FilterCriteria(role='Admin', status='Active')
        
        start = time.perf_counter()
        filtered = filter_users(large_dataset, criteria=criteria)
        elapsed = (time.perf_counter() - start) * 1000
        
        assert len(filtered) > 0
        assert elapsed < 10, f"Filter took {elapsed:.2f}ms, expected < 10ms"
    
    def test_userstore_lookup_performance(self, large_dataset):
        """Test UserStore lookup meets < 1ms target."""
        store = UserStore(users=large_dataset)
        
        start = time.perf_counter()
        user = store.get_by_id(500)
        elapsed = (time.perf_counter() - start) * 1000
        
        assert user is not None
        assert elapsed < 1, f"Lookup took {elapsed:.2f}ms, expected < 1ms"
    
    def test_performance_comparison_display(self, large_dataset):
        """Compare optimized vs original display performance."""
        # Optimized version (no sleep)
        start_opt = time.perf_counter()
        output_opt = display_users(large_dataset[:100], show_all=False)
        time_opt = (time.perf_counter() - start_opt) * 1000
        
        # Original version (with sleep)
        start_orig = time.perf_counter()
        output_orig = user_display_original.display_users(large_dataset[:100], show_all=False)
        time_orig = (time.perf_counter() - start_orig) * 1000
        
        # Optimized should be significantly faster (at least 10x due to sleep removal)
        speedup = time_orig / time_opt if time_opt > 0 else float('inf')
        assert speedup > 10, f"Speedup was only {speedup:.1f}x, expected > 10x"
    
    def test_performance_comparison_lookup(self, large_dataset):
        """Compare UserStore O(1) vs linear O(n) lookup."""
        store = UserStore(users=large_dataset)
        
        # O(1) lookup
        start_o1 = time.perf_counter()
        user1 = store.get_by_id(999)
        time_o1 = (time.perf_counter() - start_o1) * 1000
        
        # O(n) lookup
        start_on = time.perf_counter()
        user2 = get_user_by_id(large_dataset, 999)
        time_on = (time.perf_counter() - start_on) * 1000
        
        assert user1 == user2
        # O(1) should be faster for large datasets
        assert time_o1 < time_on or time_o1 < 1  # Either faster or under 1ms


# ===== Edge Cases and Robustness Tests =====

class TestEdgeCases:
    """Test suite for edge cases and error handling."""
    
    def test_missing_id_field(self):
        """Test handling users without ID field."""
        users = [{'name': 'No ID', 'email': 'test@example.com'}]
        output = display_users(users)
        
        assert 'N/A' in output or 'No ID' in output
    
    def test_none_values(self):
        """Test handling None values in fields."""
        users = [{'id': 1, 'name': None, 'email': None}]
        output = display_users(users)
        
        assert output is not None
    
    def test_unicode_characters(self):
        """Test handling unicode characters in names."""
        users = [
            {'id': 1, 'name': 'José García', 'email': 'jose@example.com',
             'role': 'User', 'status': 'Active', 'join_date': '2024-01-01',
             'last_login': '2025-11-26'}
        ]
        output = display_users(users)
        
        assert 'José García' in output
    
    def test_empty_strings(self):
        """Test handling empty string values."""
        users = [
            {'id': 1, 'name': '', 'email': '', 'role': '',
             'status': '', 'join_date': '', 'last_login': ''}
        ]
        output = display_users(users)
        
        assert output is not None
    
    def test_very_long_names(self):
        """Test handling very long field values."""
        users = [
            {'id': 1, 'name': 'A' * 1000, 'email': 'test@example.com',
             'role': 'User', 'status': 'Active', 'join_date': '2024-01-01',
             'last_login': '2025-11-26'}
        ]
        output = display_users(users)
        
        assert 'A' * 100 in output  # Should contain at least part of the name
    
    def test_special_characters_in_fields(self):
        """Test handling special characters."""
        users = [
            {'id': 1, 'name': 'Test|User', 'email': 'test@example.com',
             'role': 'Admin', 'status': 'Active', 'join_date': '2024-01-01',
             'last_login': '2025-11-26'}
        ]
        output = display_users(users, format_profile=FormatProfile.COMPACT)
        
        assert 'Test|User' in output


# ===== Backward Compatibility Tests =====

class TestBackwardCompatibility:
    """Test suite for backward compatibility with original implementation."""
    
    def test_display_users_signature_compatible(self, sample_users):
        """Test display_users maintains backward compatible signature."""
        # Original signature: display_users(users, show_all=True, verbose=False)
        output1 = display_users(sample_users)
        output2 = display_users(sample_users, show_all=True)
        output3 = display_users(sample_users, show_all=False, verbose=True)
        
        assert all(output is not None for output in [output1, output2, output3])
    
    def test_get_user_by_id_signature_compatible(self, sample_users):
        """Test get_user_by_id maintains backward compatible signature."""
        user = get_user_by_id(sample_users, 1)
        assert user is not None
        assert user['name'] == 'John Doe'
    
    def test_filter_users_legacy_dict_compatible(self, sample_users):
        """Test filter_users works with legacy dict criteria."""
        filtered = filter_users(sample_users, legacy_criteria={'role': 'Admin', 'status': 'Active'})
        
        assert len(filtered) == 1
        assert filtered[0]['role'] == 'Admin'
    
    def test_export_users_signature_compatible(self, sample_users):
        """Test export_users_to_string maintains compatible signature."""
        output = export_users_to_string(sample_users)
        
        assert 'USER_EXPORT_START' in output
        assert 'USER_EXPORT_END' in output


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
