import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "expenses.db"

def debug_database():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    print("=== TABLES ===")
    c.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = c.fetchall()
    for table in tables:
        print(f"Table: {table[0]}")
    
    print("\n=== GROUPS TABLE SCHEMA ===")
    c.execute("PRAGMA table_info(groups)")
    columns = c.fetchall()
    for col in columns:
        print(f"Column: {col[1]} ({col[2]})")
    
    print("\n=== GROUP_MEMBERS TABLE SCHEMA ===")
    c.execute("PRAGMA table_info(group_members)")
    columns = c.fetchall()
    for col in columns:
        print(f"Column: {col[1]} ({col[2]})")
    
    print("\n=== ALL GROUPS ===")
    c.execute("SELECT * FROM groups")
    groups = c.fetchall()
    for group in groups:
        print(f"Group: {group}")
    
    print("\n=== ALL GROUP_MEMBERS ===")
    c.execute("SELECT * FROM group_members")
    members = c.fetchall()
    for member in members:
        print(f"Member: {member}")
    
    print("\n=== AUTH_USERS TABLE SCHEMA ===")
    c.execute("PRAGMA table_info(auth_users)")
    columns = c.fetchall()
    for col in columns:
        print(f"Column: {col[1]} ({col[2]})")
    
    print("\n=== ALL AUTH_USERS ===")
    c.execute("SELECT auth_user_id, username FROM auth_users")
    users = c.fetchall()
    for user in users:
        print(f"User: {user}")
    
    conn.close()

if __name__ == "__main__":
    debug_database()
