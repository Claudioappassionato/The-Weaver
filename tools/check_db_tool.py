import sqlite3
import os

DATABASE_PATH = r"C:\mcp_projects\tool_nebula\synapse_index.db"

def check_db():
    conn = sqlite3.connect(DATABASE_PATH)
    try:
        cursor = conn.cursor()
        print("\n--- Top 20 Atoms ---")
        cursor.execute("SELECT id, content, category, source_file FROM knowledge_atoms ORDER BY id DESC LIMIT 20;")
        for row in cursor.fetchall():
            print(f"ID: {row[0]} | Cat: {row[2]} | Source: {row[3]}")
            print(f"Content: {row[1][:150]}...")
            print("-" * 20)
    finally:
        conn.close()

if __name__ == "__main__":
    check_db()
