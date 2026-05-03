# Step 1: Create the group and COMMIT FIRST
            c.execute("INSERT INTO groups (name, created_by, created_at) VALUES (?, ?, ?)", 
                     (name, me[0], datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
            gid = c.lastrowid
            conn.commit()  # MUST COMMIT FIRST
            
            print(f"DEBUG: Group created with ID: {gid}, name: '{name}' by user {me[0]}")
            
            # Step 2: Add creator as member
            c.execute("INSERT INTO group_members (group_id, auth_user_id, joined_at) VALUES (?, ?, ?)", 
                     (gid, me[0], datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
            print(f"DEBUG: Added creator {me[0]} as member of group {gid}")
