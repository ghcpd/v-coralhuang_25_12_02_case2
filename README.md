# User Display — Refactor & Optimized Implementation

This repository contains a refactored and optimized user display module meant to replace the baseline `user_display_original.py`.

Overview
- Baseline (unchanged) is in `user_display_original.py` — purposely preserved for comparison.
- New high-performance, maintainable implementation in `user_display_optimized.py`.
- Tests in `tests/test_user_display.py` exercise correctness, robustness, and performance sanity checks.

Key weaknesses in the baseline
- Inefficient string concatenation in loops and unnecessary temporary allocations
- Artificial processing delays (time.sleep) limiting throughput
- Linear search by id (O(n)) and duplicated field access
- Fragile filtering logic with nested conditionals and no composability
- No structured logging or error handling (missing keys can crash)

Design and refactoring strategy
- Provide an indexed in-memory `UserStore` with O(1) lookups and iterator/streaming support
- Implement composable filter `Criterion` classes (AND, partial matches, prefixes)
- Provide configurable formatting profiles (compact, verbose, json) with field selection
- Centralize logging using a consistent `[%s]` marker and avoid failing on malformed entries
- Optimize string assembly with buffered writes and minimal temporary allocations

New features
- UserStore: indexing, snapshotting (deep copy), iterators
- Extensible filtering primitives: NameContains, RoleEquals, RolePrefix, StatusEquals and combinators
- Flexible formatting: compact, verbose, JSON-like export, selectable fields
- Robust validation and logging hooks — malformed users are skipped with warnings

Performance
- Goals: display 1k users under ~100ms, filtering 1k users under ~10ms (sanity checks included in tests)
- Implementations use buffered assembly and O(1) lookups for fast performance

Usage examples
>>> from user_display_optimized import UserStore, display_users\n>>> store = UserStore([{"id":1, "name":"A"}])\n>>> print(display_users(store, profile="compact"))\n+
Testing & development
- Run tests with pytest (the repo includes tests/test_user_display.py):\n
```bash
python -m pytest -q
```

Requirements
- See `requirements.txt` for minimal pinned test dependencies.

Notes
- This module is intentionally designed to be easy to extend — add new Criterion subclasses or formatters without changing existing logic.
