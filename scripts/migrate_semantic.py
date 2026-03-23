import sqlite3
import os
import sys
from pathlib import Path
from tqdm import tqdm

# Aggiungi il percorso del progetto
NEBULA_HOME = r"C:\mcp_projects\tool_nebula"
sys.path.insert(0, NEBULA_HOME)

# Importa i componenti dal runner
try:
    import sqlite_vec
    from fastembed import TextEmbedding
    embedding_model = TextEmbedding(model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
    DATABASE_PATH = os.path.join(NEBULA_HOME, "synapse_index.db")
except ImportError as e:
    print(f"Errore: Assicurati di aver installato sqlite-vec e fastembed. {e}")
    sys.exit(1)

def migrate():
    print(f"Connessione al database: {DATABASE_PATH}")
    conn = sqlite3.connect(DATABASE_PATH)
    
    # Carica sqlite-vec
    conn.enable_load_extension(True)
    sqlite_vec.load(conn)
    conn.enable_load_extension(False)

    # Crea tabella virtuale se non esiste
    conn.execute('''
        CREATE VIRTUAL TABLE IF NOT EXISTS vec_knowledge_atoms USING vec0(
            atom_id INTEGER PRIMARY KEY,
            embedding FLOAT[384]
        )
    ''')
    
    # Trova atomi senza embedding
    rows = conn.execute('''
        SELECT id, content FROM knowledge_atoms 
        WHERE id NOT IN (SELECT atom_id FROM vec_knowledge_atoms)
    ''').fetchall()
    
    if not rows:
        print("Tutti gli atomi hanno già un embedding.")
        return

    print(f"Generazione embedding per {len(rows)} atomi...")
    
    # Processa in batch per velocità
    batch_size = 50
    for i in tqdm(range(0, len(rows), batch_size)):
        batch = rows[i:i+batch_size]
        ids = [r[0] for r in batch]
        contents = [r[1] for r in batch]
        
        try:
            embeddings = list(embedding_model.embed(contents))
            
            for atom_id, vector in zip(ids, embeddings):
                # Importante: trasforma la lista in blob float32 per sqlite-vec
                vector_blob = sqlite_vec.serialize_float32(vector)
                
                conn.execute('''
                    INSERT INTO vec_knowledge_atoms(atom_id, embedding)
                    VALUES (?, ?)
                ''', (atom_id, vector_blob))
            
            conn.commit()
        except Exception as e:
            print(f"Errore nel batch {i}: {e}")

    print("Migrazione completata con successo!")
    conn.close()

if __name__ == "__main__":
    migrate()
