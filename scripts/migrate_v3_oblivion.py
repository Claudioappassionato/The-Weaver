import sqlite3
import os

DATABASE_PATH = r"C:\mcp_projects\tool_nebula\synapse_index.db"

def migrate():
    if not os.path.exists(DATABASE_PATH):
        print(f"Errore: Database non trovato in {DATABASE_PATH}")
        return

    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    print("Inizio migrazione Bio-Dinamica...")
    
    columns_to_add = [
        ("access_count", "INTEGER DEFAULT 0"),
        ("last_accessed", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
        ("importance_weight", "FLOAT DEFAULT 1.0")
    ]
    
    for col_name, col_type in columns_to_add:
        try:
            cursor.execute(f"ALTER TABLE knowledge_atoms ADD COLUMN {col_name} {col_type}")
            print(f"✅ Colonna {col_name} aggiunta con successo.")
        except sqlite3.OperationalError:
            print(f"ℹ️  La colonna {col_name} esiste già, salto.")
            
    conn.commit()
    conn.close()
    print("Migrazione completata! Ora il Weaver può 'sentire' il tempo e l'importanza.")

if __name__ == "__main__":
    migrate()
