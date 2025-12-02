"""Current inefficient user display implementation."""

import time


def display_users(users, show_all=True, verbose=False):
    """Display all users in a compact format - HARD TO READ and INEFFICIENT."""
    result = ""
    processed_count = 0
    
    # Inefficient: Multiple string concatenations in loop
    for user in users:
        if verbose:
            print(f"Processing user {user['id']}...")
        
        # Redundant data fetching
        user_id = user['id']
        user_name = user['name']
        user_email = user['email']
        user_role = user['role']
        user_status = user['status']
        user_join = user['join_date']
        user_login = user['last_login']
        
        # Poor formatting - inconsistent spacing
        line = f"ID:{user_id}|Name:{user_name}|Email:{user_email}|Role:{user_role}|Status:{user_status}|JoinDate:{user_join}|LastLogin:{user_login}"
        result += line + "\n"
        processed_count += 1
        
        # Artificial delay simulating slow processing
        time.sleep(0.01)
    
    # No error handling - crashes on missing keys
    if show_all:
        result += f"\n[INFO] Processed {processed_count} users.\n"
    
    return result


def get_user_by_id(users, user_id):
    """Search for user by ID - LINEAR SEARCH, NO OPTIMIZATION."""
    for user in users:
        if user['id'] == user_id:
            return user
    return None


def filter_users(users, criteria):
    """Filter users with complex nested logic - HARD TO MAINTAIN."""
    filtered = []
    for user in users:
        if 'role' in criteria:
            if user['role'] != criteria['role']:
                continue
        if 'status' in criteria:
            if user['status'] != criteria['status']:
                continue
        if 'name' in criteria:
            if criteria['name'].lower() not in user['name'].lower():
                continue
        filtered.append(user)
    return filtered


def export_users_to_string(users):
    """Export users to string format - MEMORY INEFFICIENT."""
    # Creates multiple temporary strings
    output = "USER_EXPORT_START\n"
    output += "=" * 100 + "\n"
    
    for user in users:
        temp = f"User ID: {user['id']}\n"
        temp += f"  Name: {user['name']}\n"
        temp += f"  Email: {user['email']}\n"
        temp += f"  Role: {user['role']}\n"
        temp += f"  Status: {user['status']}\n"
        temp += f"  Join Date: {user['join_date']}\n"
        temp += f"  Last Login: {user['last_login']}\n"
        temp += "-" * 100 + "\n"
        output += temp
    
    output += "USER_EXPORT_END\n"
    return output
# Sample data
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
    print("Current Implementation Output:")
    print("=" * 100)
    output = display_users(sample_users)
    print(output)
