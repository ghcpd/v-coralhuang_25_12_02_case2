import json
import logging
import time

import pytest

from user_display_optimized import (
    FilterCriteria,
    UserStore,
    configure_logging,
    display_users,
    export_users_to_string,
    filter_users,
    get_user_by_id,
)


SAMPLE_USERS = [
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
        "name": "Bob Johnson",
        "email": "bob@example.com",
        "role": "Moderator",
        "status": "Active",
        "join_date": "2024-02-10",
        "last_login": "2025-11-25",
    },
    {
        "id": 4,
        "name": "Alice Williams",
        "email": "alice@example.com",
        "role": "User",
        "status": "Active",
        "join_date": "2024-05-12",
        "last_login": "2025-11-26",
    },
]


def baseline_display(users):
    lines = []
    for u in users:
        lines.append(
            f"ID:{u['id']}|Name:{u['name']}|Email:{u['email']}|Role:{u['role']}|Status:{u['status']}|JoinDate:{u['join_date']}|LastLogin:{u['last_login']}"
        )
    lines.append("")
    lines.append(f"[INFO] Processed {len(users)} users.")
    lines.append("")
    return "\n".join(lines)


def test_display_users_default_matches_baseline():
    assert display_users(SAMPLE_USERS) == baseline_display(SAMPLE_USERS)


def test_filter_users_multiple_criteria():
    result = filter_users(SAMPLE_USERS, {"role": "User", "status": "Active"})
    assert [u["id"] for u in result] == [4]


def test_filter_users_partial_case_insensitive():
    result = filter_users(SAMPLE_USERS, FilterCriteria(name_contains="john", case_sensitive=False))
    assert {u["id"] for u in result} == {1, 3}


def test_filter_users_case_sensitive():
    result = filter_users(SAMPLE_USERS, FilterCriteria(name_contains="john", case_sensitive=True))
    assert result == []


def test_formatting_profiles_and_fields():
    out_verbose = display_users([SAMPLE_USERS[0]], show_all=False, profile="verbose")
    assert "User:" in out_verbose
    assert "Name:" in out_verbose

    out_json = display_users([SAMPLE_USERS[0]], show_all=False, profile="json")
    parsed = json.loads(out_json.strip())
    assert parsed["id"] == 1

    out_fields = display_users([SAMPLE_USERS[0]], show_all=False, profile="compact", fields=("name", "status"))
    first_line = out_fields.strip().split("\n")[0]
    assert first_line == "Name:John Doe|Status:Active"


def test_logging_missing_keys(caplog):
    caplog.set_level(logging.ERROR, logger="user_display")
    users = [dict(SAMPLE_USERS[0]), {"id": 99, "name": "No Email"}]
    out = display_users(users)
    assert "Email:<missing>" in out
    assert any("Missing required field 'email'" in record.message for record in caplog.records)


def test_user_store_snapshot_and_copy():
    store = UserStore(SAMPLE_USERS)
    snap = store.snapshot()
    snap[0]["name"] = "Changed"
    user = store.get_user_by_id(1)
    assert user is not None
    assert user["name"] == "John Doe"

    shallow = store.copy(deep=False)
    s_user = shallow.get_user_by_id(1)
    assert s_user is not None
    assert s_user["name"] == "John Doe"

    deep = store.copy(deep=True)
    deep_user = deep.get_user_by_id(1)
    assert deep_user is not None
    deep_user["name"] = "Other"
    orig = store.get_user_by_id(1)
    assert orig is not None
    assert orig["name"] == "John Doe"


def test_export_users_string():
    out = export_users_to_string(SAMPLE_USERS)
    assert out.startswith("USER_EXPORT_START\n")
    assert "User ID: 1" in out
    assert out.strip().endswith("USER_EXPORT_END")


def test_custom_validator_drops_invalid():
    def validator(user):
        return user.get("status") in {"Active", "Inactive"}

    users = SAMPLE_USERS + [{"id": 5, "name": "Bad", "status": "Broken", "email": "b", "role": "User", "join_date": "", "last_login": ""}]
    store = UserStore(users, validator=validator, drop_invalid=True)
    assert store.invalid_count == 1
    assert store.get_user_by_id(5) is None


# ---------------------------------------------------------------------------
# Performance sanity checks
# ---------------------------------------------------------------------------

def _make_users(n: int):
    return [
        {
            "id": i,
            "name": f"User {i}",
            "email": f"user{i}@example.com",
            "role": "Admin" if i % 5 == 0 else "User",
            "status": "Active" if i % 2 == 0 else "Inactive",
            "join_date": "2024-01-01",
            "last_login": "2025-01-01",
        }
        for i in range(n)
    ]


def test_performance_display_1000():
    users = _make_users(1000)
    t0 = time.perf_counter()
    display_users(users, show_all=False, profile="compact")
    dt = time.perf_counter() - t0
    assert dt < 0.2  # target <100ms, allow margin


def test_performance_filter_1000():
    users = _make_users(1000)
    store = UserStore(users)
    crit = {"status": "Active", "role": "User"}
    t0 = time.perf_counter()
    result = list(store.filter(crit))
    dt = time.perf_counter() - t0
    assert len(result) > 0
    assert dt < 0.05  # target <10ms, allow margin


def test_performance_get_user_by_id():
    users = _make_users(5000)
    store = UserStore(users)
    t0 = time.perf_counter()
    for i in range(20000):
        assert store.get_user_by_id(i % 5000) is not None
    dt = time.perf_counter() - t0
    avg = dt / 20000
    assert avg < 0.0007  # <0.7ms per lookup
