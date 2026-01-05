import sqlite3

def migrate():
    print("Migrating database schema (Momentum)...")
    conn = sqlite3.connect('poly.db')
    cursor = conn.cursor()
    
    try:
        # Check if column exists
        cursor.execute("PRAGMA table_info(events)")
        columns = [info[1] for info in cursor.fetchall()]
        
        if 'momentum_24h' not in columns:
            print("Adding 'momentum_24h' column to 'events' table...")
            cursor.execute("ALTER TABLE events ADD COLUMN momentum_24h FLOAT")
            conn.commit()
            print("Migration successful.")
        else:
            print("Column 'momentum_24h' already exists.")
            
    except Exception as e:
        print(f"Migration failed: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    migrate()
