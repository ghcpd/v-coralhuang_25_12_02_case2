"""Performance benchmark comparing original vs optimized implementations."""

import time
import sys
from typing import List, Dict, Any

import user_display_original
import user_display_optimized
from user_display_optimized import UserStore, FilterCriteria


def generate_large_dataset(size: int) -> List[Dict[str, Any]]:
    """Generate test dataset of specified size."""
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
        for i in range(1, size + 1)
    ]


def benchmark_display(users: List[Dict[str, Any]], name: str):
    """Benchmark display_users function."""
    print(f"\n{name} - Display {len(users)} users:")
    
    # Original (with sleep)
    start = time.perf_counter()
    output_orig = user_display_original.display_users(users[:100], show_all=False, verbose=False)
    time_orig = (time.perf_counter() - start) * 1000
    
    # Optimized (no sleep)
    start = time.perf_counter()
    output_opt = user_display_optimized.display_users(users, show_all=False, verbose=False)
    time_opt = (time.perf_counter() - start) * 1000
    
    speedup = time_orig / time_opt if time_opt > 0 else float('inf')
    
    print(f"  Original (100 users with sleep): {time_orig:8.2f}ms")
    print(f"  Optimized ({len(users)} users):       {time_opt:8.2f}ms")
    print(f"  Speedup:                         {speedup:8.1f}x")
    print(f"  Target: <100ms                   {'✅ PASS' if time_opt < 100 else '❌ FAIL'}")


def benchmark_lookup(users: List[Dict[str, Any]], name: str):
    """Benchmark get_user_by_id function."""
    print(f"\n{name} - User lookup:")
    
    # Original O(n)
    start = time.perf_counter()
    user_orig = user_display_original.get_user_by_id(users, len(users) - 1)
    time_orig = (time.perf_counter() - start) * 1000
    
    # Optimized O(1) with UserStore
    store = user_display_optimized.UserStore(users=users)
    start = time.perf_counter()
    user_opt = store.get_by_id(len(users) - 1)
    time_opt = (time.perf_counter() - start) * 1000
    
    speedup = time_orig / time_opt if time_opt > 0 else float('inf')
    
    print(f"  Original O(n):     {time_orig:8.3f}ms")
    print(f"  Optimized O(1):    {time_opt:8.3f}ms")
    print(f"  Speedup:           {speedup:8.1f}x")
    print(f"  Target: <1ms       {'✅ PASS' if time_opt < 1 else '❌ FAIL'}")


def benchmark_filter(users: List[Dict[str, Any]], name: str):
    """Benchmark filter_users function."""
    print(f"\n{name} - Filter users:")
    
    # Original
    start = time.perf_counter()
    filtered_orig = user_display_original.filter_users(
        users, {'role': 'Admin', 'status': 'Active'}
    )
    time_orig = (time.perf_counter() - start) * 1000
    
    # Optimized
    criteria = FilterCriteria(role='Admin', status='Active')
    start = time.perf_counter()
    filtered_opt = user_display_optimized.filter_users(users, criteria=criteria)
    time_opt = (time.perf_counter() - start) * 1000
    
    speedup = time_orig / time_opt if time_opt > 0 else float('inf')
    
    print(f"  Original:          {time_orig:8.3f}ms ({len(filtered_orig)} results)")
    print(f"  Optimized:         {time_opt:8.3f}ms ({len(filtered_opt)} results)")
    print(f"  Speedup:           {speedup:8.1f}x")
    print(f"  Target: <10ms      {'✅ PASS' if time_opt < 10 else '❌ FAIL'}")


def benchmark_export(users: List[Dict[str, Any]], name: str):
    """Benchmark export_users_to_string function."""
    print(f"\n{name} - Export users:")
    
    # Original
    start = time.perf_counter()
    export_orig = user_display_original.export_users_to_string(users[:100])
    time_orig = (time.perf_counter() - start) * 1000
    
    # Optimized
    start = time.perf_counter()
    export_opt = user_display_optimized.export_users_to_string(users)
    time_opt = (time.perf_counter() - start) * 1000
    
    speedup = time_orig / time_opt if time_opt > 0 else float('inf')
    
    print(f"  Original (100):    {time_orig:8.2f}ms")
    print(f"  Optimized ({len(users)}): {time_opt:8.2f}ms")
    print(f"  Speedup:           {speedup:8.1f}x")


if __name__ == "__main__":
    print("=" * 80)
    print("PERFORMANCE BENCHMARK: Original vs Optimized")
    print("=" * 80)
    
    # Test with 100 users
    print("\n" + "=" * 80)
    print("DATASET: 100 Users")
    print("=" * 80)
    users_100 = generate_large_dataset(100)
    benchmark_display(users_100, "100 Users")
    benchmark_lookup(users_100, "100 Users")
    benchmark_filter(users_100, "100 Users")
    benchmark_export(users_100, "100 Users")
    
    # Test with 1,000 users
    print("\n" + "=" * 80)
    print("DATASET: 1,000 Users (Performance Targets)")
    print("=" * 80)
    users_1000 = generate_large_dataset(1000)
    benchmark_display(users_1000, "1,000 Users")
    benchmark_lookup(users_1000, "1,000 Users")
    benchmark_filter(users_1000, "1,000 Users")
    benchmark_export(users_1000, "1,000 Users")
    
    # Test with 5,000 users
    print("\n" + "=" * 80)
    print("DATASET: 5,000 Users (Stress Test)")
    print("=" * 80)
    users_5000 = generate_large_dataset(5000)
    benchmark_display(users_5000, "5,000 Users")
    benchmark_lookup(users_5000, "5,000 Users")
    benchmark_filter(users_5000, "5,000 Users")
    
    print("\n" + "=" * 80)
    print("BENCHMARK COMPLETE")
    print("=" * 80)
