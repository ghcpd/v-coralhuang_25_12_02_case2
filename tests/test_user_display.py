import json
import time
from typing import List

import pytest

import user_display_original as original
import user_display_optimized as optimized


@pytest.fixture
def sample_users() -> List[dict]:
    return [
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
        {
            "id": 3,
            "name": "Alice Johnson",
            "email": "alice@example.com",
            "role": "User",
            "status": "Active",
            "join_date": "2024-02-10",
            "last_login": "2025-11-25",
        },
    ]


def test_display_users_compatibility_default(sample_users):
    out = optimized.display_users(sample_users, show_all=True)
    # Check the format resembles the baseline compact style
    assert "ID:1" in out
    assert "Name:John Doe" in out
    assert "Email:john@example.com" in out
    assert "Role:Admin" in out
    assert "Status:Active" in out
    assert "JoinDate:2023-01-15" in out
    assert "LastLogin:2025-11-26" in out
    assert "Processed 3 users" in out


def test_display_users_field_selection_and_profiles(sample_users):
    out = optimized.display_users(sample_users, fields=["name", "status"], profile="compact", show_all=False)
    lines = out.splitlines()
    assert lines[0] == "Name:John Doe|Status:Active"
    # JSON profile should be parseable
    json_out = optimized.display_users(sample_users, fields=["id", "name"], profile="json", show_all=False)
    first_obj = json.loads(json_out.splitlines()[0])
    assert first_obj == {"id": 1, "name": "John Doe"}


def test_filter_users_multiple_criteria(sample_users):
    criteria = optimized.UserFilterCriteria(role="User", status="Active", name_contains="alice", case_sensitive=False)
    filtered = optimized.filter_users(sample_users, criteria)
    assert len(filtered) == 1
    assert filtered[0]["name"] == "Alice Johnson"

    # role_prefix and case sensitivity
    criteria2 = {"role_prefix": "ad", "case_sensitive": False}
    filtered2 = optimized.filter_users(sample_users, criteria2)
    assert len(filtered2) == 1
    assert filtered2[0]["role"] == "Admin"


def test_userstore_snapshot_independent(sample_users):
    store = optimized.UserStore(sample_users)
    snap = store.snapshot(deep=True)
    # mutate original
    store.add({"id": 99, "name": "Temp"})
    assert len(store) == len(sample_users) + 1
    assert len(snap) == len(sample_users)



def test_missing_keys_handled(caplog):
    users = [
        {"id": 1, "name": "No Email", "role": "User"},  # missing email etc.
        {"name": "No ID", "email": "noid@example.com", "role": "User"},  # missing id
    ]
    caplog.set_level("WARNING", logger=optimized.logger.name)
    out = optimized.display_users(users, show_all=False)
    assert "Email:<missing>" in out
    assert "ID:<missing>" in out
    # warning for missing id
    warnings = [r for r in caplog.records if "missing 'id'" in r.getMessage()]
    assert warnings, "Expected warning for missing id"



def test_export_users_profiles(sample_users):
    out_verbose = optimized.export_users_to_string(sample_users, profile="verbose")
    assert "USER_EXPORT_START" in out_verbose
    assert "User ID: 1" in out_verbose
    assert "Name: John Doe" in out_verbose
    assert "USER_EXPORT_END" in out_verbose

    out_json = optimized.export_users_to_string(sample_users, profile="json")
    first = json.loads(out_json.splitlines()[2])  # start, line of =========, then JSON line
    assert first["id"] == 1



def test_logging_marker_present(caplog):
    def validator(user):
        return "name" in user

    caplog.set_level("WARNING", logger=optimized.logger.name)
    store = optimized.UserStore(validators=[validator])
    store.add({"id": 1})  # missing name
    assert any("[USER-WARN]" in rec.getMessage() for rec in caplog.records)


@pytest.mark.parametrize("n", [2000])
def test_performance_display_and_filter(n):
    users = [
        {
            "id": i,
            "name": f"User {i}",
            "email": f"user{i}@example.com",
            "role": "Admin" if i % 5 == 0 else "User",
            "status": "Active" if i % 2 == 0 else "Inactive",
            "join_date": "2023-01-01",
            "last_login": "2025-12-01",
        }
        for i in range(n)
    ]
    store = optimized.UserStore(users)

    t0 = time.perf_counter()
    out = optimized.display_users(store, show_all=False)
    t1 = time.perf_counter()
    duration_display = t1 - t0
    assert duration_display < 0.5, f"display too slow: {duration_display:.3f}s"
    assert len(out.splitlines()) == n

    t0 = time.perf_counter()
    filtered = list(store.filter({"role": "Admin", "status": "Active"}))
    t1 = time.perf_counter()
    duration_filter = t1 - t0
    assert duration_filter < 0.2, f"filter too slow: {duration_filter:.3f}s"
    # sanity: number of admins active
    expected = len([u for u in users if u["role"] == "Admin" and u["status"] == "Active"])
    assert len(filtered) == expected

    # lookup performance
    target_id = n - 1
    t0 = time.perf_counter()
    u = store.get_user_by_id(target_id)
    t1 = time.perf_counter()
    assert u and u["id"] == target_id
    assert (t1 - t0) < 0.005


@pytest.mark.parametrize("n", [5000])
def test_get_user_by_id_vs_linear(n):
    users = [
        {
            "id": i,
            "name": f"User {i}",
            "email": f"user{i}@example.com",
            "role": "User",
            "status": "Active",
            "join_date": "2023-01-01",
            "last_login": "2025-12-01",
        }
        for i in range(n)
    ]
    store = optimized.UserStore(users)
    target_id = n - 1

    t0 = time.perf_counter()
    for _ in range(1000):
        store.get_user_by_id(target_id)
    t1 = time.perf_counter()
    store_time = t1 - t0

    t0 = time.perf_counter()
    for _ in range(1000):
        original.get_user_by_id(users, target_id)
    t1 = time.perf_counter()
    list_time = t1 - t0

    assert store_time < list_time


# Baseline behavior sanity (patched sleep to zero for speed)
def test_baseline_no_sleep(monkeypatch, sample_users):
    monkeypatch.setattr(original.time, "sleep", lambda x: None)
    out = original.display_users(sample_users, show_all=True)
    assert "Processed 3 users" in out

