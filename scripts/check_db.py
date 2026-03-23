import sqlite3
import os

DATABASE_PATH = r"C:\mcp_projects\tool_nebula\synapse_index.db"

def check_db():
    if not os.path.exists(DATABASE_PATH):
        print(f"Error: {DATABASE_PATH} does not exist.")
        return

    conn = sqlite3.connect(DATABASE_PATH)
    try:
        cursor = conn.cursor()
        
        print("--- Tables ---")
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        for table in cursor.fetchall():
            print(f"- {table[0]}")
            
        print("\n--- Recent Atoms ---")
        cursor.execute("SELECT id, content, category, source_file FROM knowledge_atoms ORDER BY id DESC LIMIT 5;")
        for row in cursor.fetchall():
            print(f"ID: {row[0]}")
            print(f"Content: {row[1][:100]}...")
            print(f"Category: {row[2]}")
            print(f"Source: {row[3]}")
            print("-" * 20)
            
        print("\n--- Source Files ---")
        cursor.execute("SELECT * FROM source_files;")
        for row in cursor.fetchall():
            print(row)
            
    finally:
        conn.close()

if __name__ == "__main__":
    check_db()
