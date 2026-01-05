import sqlite3

def migrate():
    print("Migrating database schema...")
    conn = sqlite3.connect('poly.db')
    cursor = conn.cursor()
    
    try:
        # Check if column exists
        cursor.execute("PRAGMA table_info(events)")
        columns = [info[1] for info in cursor.fetchall()]
        
        if 'clob_token_id' not in columns:
            print("Adding 'clob_token_id' column to 'events' table...")
            cursor.execute("ALTER TABLE events ADD COLUMN clob_token_id VARCHAR")
            conn.commit()
            print("Migration successful.")
        else:
            print("Column 'clob_token_id' already exists.")
            
    except Exception as e:
        print(f"Migration failed: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    migrate()
