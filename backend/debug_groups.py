import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "expenses.db"

def debug_groups_for_user(auth_user_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    print(f"=== DEBUG FOR USER {auth_user_id} ===")
    
    # Check if user exists
    c.execute("SELECT auth_user_id, username FROM auth_users WHERE auth_user_id = ?", (auth_user_id,))
    user = c.fetchone()
    if not user:
        print(f"User {auth_user_id} not found")
        return
    print(f"User found: {user}")
    
    # Test the exact query from get_groups
    print("\n=== TESTING GET_GROUPS QUERY ===")
    c.execute("""
        SELECT g.*
        FROM groups g 
        JOIN group_members gm ON g.group_id = gm.group_id
        WHERE gm.auth_user_id = ?
    """, (auth_user_id,))
    groups = c.fetchall()
    print(f"Groups found: {len(groups)}")
    for group in groups:
        print(f"  Group: {group}")
    
    # Test with different user IDs
    for test_id in [1, 2, 3]:
        print(f"\n=== TESTING USER {test_id} ===")
        c.execute("""
            SELECT g.*
            FROM groups g 
            JOIN group_members gm ON g.group_id = gm.group_id
            WHERE gm.auth_user_id = ?
        """, (test_id,))
        test_groups = c.fetchall()
        print(f"Groups for user {test_id}: {len(test_groups)}")
        for group in test_groups:
            print(f"  Group: {group}")
    
    conn.close()

if __name__ == "__main__":
    # Test for all users
    for user_id in [1, 2, 3]:
        debug_groups_for_user(user_id)
        print("\n" + "="*50 + "\n")
