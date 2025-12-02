import json
import os
import sys

# Ensure test runner can import module from repo root
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import time
import logging

import pytest

from user_display_optimized import (
    UserStore,
    display_users,
    export_users_to_string,
    RoleEquals,
    StatusEquals,
    NameContains,
    AndCriteria,
    filter_users_iter,
)


SAMPLE_USERS = [
    {"id": 1, "name": "John Doe", "email": "john@example.com", "role": "Admin", "status": "Active", "join_date": "2023-01-15", "last_login": "2025-11-26"},
    {"id": 2, "name": "Jane Smith", "email": "jane@example.com", "role": "User", "status": "Inactive", "join_date": "2023-06-20", "last_login": "2025-11-20"},
    {"id": 3, "name": "Bob Johnson", "email": "bob@example.com", "role": "Moderator", "status": "Active", "join_date": "2024-02-10", "last_login": "2025-11-25"},
    {"id": 4, "name": "Alice Williams", "email": "alice@example.com", "role": "User", "status": "Active", "join_date": "2024-05-12", "last_login": "2025-11-26"},
    {"id": 5, "name": "Charlie Brown", "email": "charlie@example.com", "role": "User", "status": "Active", "join_date": "2024-08-03", "last_login": "2025-11-24"},
]


def test_userstore_basic_usage():
    store = UserStore(SAMPLE_USERS)
    assert len(store) == 5
    u = store.get_user_by_id(3)
    assert u is not None
    assert u["name"] == "Bob Johnson"


def test_snapshot_and_iteration():
    store = UserStore(SAMPLE_USERS)
    snap = store.snapshot()
    assert isinstance(snap, UserStore)
    assert len(snap) == len(store)
    # iterator yields dicts
    ids = [u["id"] for u in store]
    assert ids == [1, 2, 3, 4, 5]


def test_display_modes_and_field_selection(caplog):
    caplog.set_level(logging.WARNING)
    store = UserStore(SAMPLE_USERS)

    compact = display_users(store, profile="compact", fields=["id", "name"])
    assert "ID" not in compact  # compact uses lowercase field names
    assert "id:1" in compact

    verbose = display_users(store, profile="verbose", fields=["id", "name"])
    assert "User ID:" in verbose

    j = display_users(store, profile="json", fields=["id", "name"])
    # Ensure json-ish output (lines containing json objects)
    lines = j.splitlines()
    parsed = [json.loads(l) for l in lines if l.strip() and l.startswith('{')]
    assert parsed[0]["id"] == 1


def test_filtering_composition():
    store = UserStore(SAMPLE_USERS)
    criteria = AndCriteria([RoleEquals("User"), StatusEquals("Active")])
    got = list(filter_users_iter(store, criteria))
    # from SAMPLE_USERS, ids 4 and 5 match
    assert [u["id"] for u in got] == [4, 5]


def test_name_contains_case_insensitive():
    store = UserStore(SAMPLE_USERS)
    crit = NameContains("john")
    got = list(filter_users_iter(store, crit))
    assert {u["id"] for u in got} == {1, 3}


def test_export_users_to_string_and_missing_keys(caplog):
    caplog.set_level(logging.WARNING)
    malformed = [{"id": 10, "name": "X"}, {"name": "NoId"}, {"id": 11, "name": "Y"}]
    store = UserStore(malformed)
    s = export_users_to_string(store)
    # Should include both valid items and an export header
    assert "USER_EXPORT_START" in s
    assert "User ID: 10" in s
    assert "NoId" not in s  # entry without id should be skipped


def make_users(n):
    for i in range(1, n + 1):
        yield {"id": i, "name": f"User{i}", "email": f"user{i}@example.com", "role": "User", "status": "Active", "join_date": "2020-01-01", "last_login": "2025-01-01"}


@pytest.mark.skipif(False, reason="Performance test — may be heavy on some runners")
def test_performance_sanity():
    # sanity checks on medium datasets — should roughly meet targets on modern hardware
    store = UserStore(make_users(2000))

    # get_user_by_id should be fast
    t0 = time.perf_counter()
    _ = store.get_user_by_id(1500)
    t1 = time.perf_counter()
    assert (t1 - t0) * 1000 < 10  # < 10ms (very generous)

    # display 1000 users
    subset = list(make_users(1000))
    t0 = time.perf_counter()
    display_users(subset, profile="compact", fields=["id", "name", "status"], show_all=False)
    t1 = time.perf_counter()
    assert (t1 - t0) < 0.5  # under 500ms

    # filter 1000 users
    criteria = NameContains("User")
    t0 = time.perf_counter()
    got = list(filter_users_iter(subset, criteria))
    t1 = time.perf_counter()
    assert len(got) == 1000
    assert (t1 - t0) < 0.2  # under 200ms
