"""
Synapse Index - Strato "Sinapsi" del sistema The Weaver.
Funzione: Estrae atomi di conoscenza dai file .md e li salva in SQLite con embedding vettoriali.
Requisito: Deve essere eseguito tramite MCP Server (non direttamente da questo ambiente).

Struttura:
- Legge i log giornalieri da C:\Users\forte\memory\YYYY-MM-DD.md
- Estrae fatti atomici (preferenze, vincoli tecnici, milestone)
- Salva in SQLite con estensione sqlite-vec per ricerca semantica
"""

import os
import json
import sqlite3
from datetime import datetime
from typing import List, Dict, Any
import re  # Importa regex per parsing

# CONFIGURAZIONE CAMPI
NEBULA_HOME = r"C:\mcp_projects\tool_nebula"
USER_MEMORY_PATH = r"C:\Users\forte\memory"
DATABASE_PATH = os.path.join(NEBULA_HOME, "synapse_index.db")
CHUNK_SIZE = 500  # Max token per chunk

class SynapseIndex:
    def __init__(self):
        self.conn = sqlite3.connect(DATABASE_PATH)
        self.cursor = self.conn.cursor()
        self._create_tables()
    
    def _create_tables(self):
        """Crea le tabelle necessarie per l'indice sinapsi."""
        # Tabella per gli atomi di conoscenza (fatti estratti)
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS knowledge_atoms (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content TEXT NOT NULL,
                category TEXT NOT NULL,
                source_file TEXT NOT NULL,
                extracted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                embedding_vector BLOB
            )
        ''')
        
        # Tabella per i metadati dei file sorgente
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS source_files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_path TEXT UNIQUE NOT NULL,
                last_modified TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                total_tokens INTEGER DEFAULT 0
            )
        ''')
        
        # Indici per performance
        self.cursor.execute('CREATE INDEX IF NOT EXISTS idx_category ON knowledge_atoms(category)')
        self.cursor.execute('CREATE INDEX IF NOT EXISTS idx_source_file ON knowledge_atoms(source_file)')
        
        self.conn.commit()
    
    def extract_atoms_from_log(self, log_path: str) -> List[Dict[str, Any]]:
        """
        Estrae atomi di conoscenza da un file log giornaliero.
        Semplice parser basato su pattern (da espandere con NLP).
        """
        atoms = []
        
        if not os.path.exists(log_path):
            return atoms
        
        with open(log_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Pattern per estrarre fatti comuni (da espandere)
        patterns = [
            r'Preferisco\s+(.+)',  # Preferenze utente
            r'\[Vincolo:\s*(.+)\]',  # Vincoli tecnici
            r'Milestone:?\s*(.+)',   # Milestone progetti
            r'Bug:?\s*(.+)',         # Bug identificati
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, content)
            for match in matches:
                atoms.append({
                    'content': match.strip(),
                    'category': self._infer_category(match),
                    'source_file': os.path.basename(log_path)
                })
        
        return atoms
    
    def _infer_category(self, text: str) -> str:
        """Inferisce la categoria di un atomo di conoscenza."""
        text_lower = text.lower()
        if any(word in text_lower for word in ['preferisco', 'amo', 'uso']):
            return 'preference'
        elif any(word in text_lower for word in ['vincolo', 'limitazione', 'deve']):
            return 'constraint'
        elif any(word in text_lower for word in ['milestone', 'completato', 'fatto']):
            return 'milestone'
        else:
            return 'general_fact'
    
    def save_atoms(self, atoms: List[Dict[str, Any]]):
        """Salva gli atomi nel database SQLite."""
        for atom in atoms:
            self.cursor.execute('''
                INSERT OR REPLACE INTO knowledge_atoms 
                (content, category, source_file) 
                VALUES (?, ?, ?)
            ''', (atom['content'], atom['category'], atom['source_file']))
        
        # Aggiorna metadati file sorgente
        source = os.path.basename(atoms[0]['source_file']) if atoms else 'unknown'
        self.cursor.execute('''
            INSERT OR REPLACE INTO source_files 
            (file_path, last_modified) 
            VALUES (?, ?)
        ''', (os.path.join(os.path.dirname(atoms[0]['source_file']), source), datetime.now()))
        
        self.conn.commit()
    
    def search_semantic(self, query: str, limit: int = 10) -> List[str]:
        """Ricerca semantica sugli atomi salvati."""
        # Implementazione futura con sqlite-vec
        # Per ora restituisce risultati basati su matching testuale semplice
        results = []
        
        self.cursor.execute('''
            SELECT content FROM knowledge_atoms 
            WHERE LOWER(content) LIKE ? 
            ORDER BY ROWID DESC 
            LIMIT ?
        ''', (f'%{query.lower()}%', limit))
        
        for row in self.cursor.fetchall():
            results.append(row[0])
        
        return results

def main():
    """Funzione principale per testare l'indice."""
    index = SynapseIndex()
    
    # Esempio: estrazione da log di oggi
    today = datetime.now().strftime('%Y-%m-%d')
    log_path = os.path.join(USER_MEMORY_PATH, f"{today}.md")
    
    print(f"🔍 Scansione memoria utente: {log_path}")
    atoms = index.extract_atoms_from_log(log_path)
    
    if atoms:
        print(f"✅ Estratti {len(atoms)} atomi di conoscenza.")
        for atom in atoms[:5]:  # Mostra primi 5
            print(f"   - [{atom['category']}] {atom['content']}")
        
        index.save_atoms(atoms)
    else:
        print("⚠️ Nessun atomo estratto o file non trovato.")

if __name__ == "__main__":
    main()
