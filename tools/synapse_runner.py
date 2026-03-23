"""
The Weaver - MCP Server v1.2
Espone gli strumenti di memoria ibrida (Strato Sinapsi) a LM Studio.

MIGLIORAMENTI v1.2:
- Auto-scan degli ultimi 7 giorni di log all'avvio
- Parser flessibile: indicizza ogni paragrafo, non solo keyword rigide
- Deduplicazione: non reindicizza contenuti già presenti
"""

import os
import sys
import json
import sqlite3
import re
import asyncio
import requests
from typing import Any
from pathlib import Path
from datetime import datetime, timedelta

# Aggiungi il percorso del core al sys.path
# Configurazioni Percorsi (Portabili)
NEBULA_HOME = os.getenv("NEBULA_HOME", str(Path(__file__).parent.parent.absolute()))
sys.path.insert(0, os.path.join(NEBULA_HOME, "core"))

import mcp.server.stdio
import mcp.types as types
from mcp.server import Server, NotificationOptions
from mcp.server.models import InitializationOptions

# Carica modulo core - Importante: dopo sys.path.insert
try:
    from search_agent import LocalLLMSearchAgent
    SEARCH_AGENT_READY = True
except ImportError:
    SEARCH_AGENT_READY = False

# --- Estensioni Semantiche (Free & Local) ---
try:
    import sqlite_vec
    from fastembed import TextEmbedding
    # Caricamento leggero del modello (384 dim, ottimo per italiano)
    embedding_model = TextEmbedding(model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
    SEMANTIC_READY = True
except ImportError:
    SEMANTIC_READY = False

# --- LIGM Engine v3.0 (Neural Active Memory) ---
try:
    import torch
    import torch.nn.functional as F
    from lora_engine import LIGMEngine
    LORA_READY = True
except ImportError:
    LORA_READY = False

# ---- Percorsi configurazione ----
# ---- Percorsi configurazione ----
# Fallback dinamico su cartella 'memory' nella home dell'utente corrente
USER_MEMORY_PATH = os.getenv("USER_MEMORY_PATH", str(Path.home() / "memory"))
DATABASE_PATH = os.path.join(NEBULA_HOME, "synapse_index.db")
LOG_DIR = os.path.join(NEBULA_HOME, "logs")
CONFIG_PATH = os.path.join(NEBULA_HOME, "config", "analyzer_rules.json")
WEEKLY_MEMORY_FILE = os.path.join(USER_MEMORY_PATH, "MEMORY_WEEKLY.md")

# ---- Profilo Cognitivo (Personalità della Memoria) ----
MEMORY_PROFILES = {
    "archivista": {"decay_rate": 0.01, "min_strength": 0.2, "desc": "Ricorda dettagli minimi, Oblio lentissimo."},
    "creativo": {"decay_rate": 0.1, "min_strength": 0.6, "desc": "Sfoltisce velocemente i dettagli per favorire le grandi idee."},
    "focus": {"decay_rate": 0.05, "min_strength": 0.8, "desc": "Silos iper-focalizzato: dimentica subito ciò che non usi."},
    "equilibrato": {"decay_rate": 0.05, "min_strength": 0.5, "desc": "Bilanciamento naturale."}
}
CURRENT_PROFILE = "equilibrato"

# ---- Configurazione LM Studio ----
LM_STUDIO_API_URL = "http://localhost:1234/v1/chat/completions"
DEFAULT_MODEL = "" # Lasciare vuoto per usare il modello attualmente caricato
AUTONOMOUS_LLM_ENABLED = True # Se False, disattiva chiamate LLM in background
HEARTBEAT_ENABLED = False # Stato iniziale del battito cardiaco
heartbeat_event = asyncio.Event() # Evento per il controllo fluido del battito

os.makedirs(LOG_DIR, exist_ok=True)
os.makedirs(USER_MEMORY_PATH, exist_ok=True)

STARTUP_LOG = os.path.join(LOG_DIR, "synapse_runner.log")
LORA_WEIGHTS_PATH = os.path.join(NEBULA_HOME, "core", "synapse_lora_weights.pth")

# Inizializzazione Motore LoRA
lora_engine = None
if LORA_READY:
    lora_engine = LIGMEngine(LORA_WEIGHTS_PATH)


def _log(msg: str):
    """Scrive su file di log e su stderr (visibile nei log LM Studio)."""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, file=sys.stderr, flush=True)
    try:
        with open(STARTUP_LOG, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


# ---- Database ----

def _get_db_connection() -> sqlite3.Connection:
    """Crea connessione SQLite, carica sqlite-vec e prepara le tabelle."""
    conn = sqlite3.connect(DATABASE_PATH)
    
    # Carica estensione sqlite-vec se disponibile
    if SEMANTIC_READY:
        try:
            conn.execute('PRAGMA journal_mode=WAL') # Migliore concorrenza
            conn.execute('PRAGMA busy_timeout=5000') # 5 secondi di attesa se lockato
            conn.enable_load_extension(True)
            sqlite_vec.load(conn)
            conn.enable_load_extension(False)
        except Exception as e:
            _log(f"⚠️  Impossibile caricare sqlite-vec: {e}")

    conn.execute('''
        CREATE TABLE IF NOT EXISTS knowledge_atoms (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content TEXT NOT NULL,
            category TEXT NOT NULL,
            source_file TEXT NOT NULL,
            extracted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            content_hash TEXT,
            access_count INTEGER DEFAULT 0,
            last_accessed TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            importance_weight FLOAT DEFAULT 1.0,
            meta_checked BOOLEAN DEFAULT 0 -- Flag per il Curator
        )
    ''')
    
    # Migrazione: Aggiunta colonna meta_checked se mancante
    try:
        conn.execute('ALTER TABLE knowledge_atoms ADD COLUMN meta_checked BOOLEAN DEFAULT 0')
    except sqlite3.OperationalError:
        pass # Colonna già esistente
    
    # Tabella virtuale per ricerca vettoriale (384 dimensioni per MiniLM-L12)
    if SEMANTIC_READY:
        conn.execute('''
            CREATE VIRTUAL TABLE IF NOT EXISTS vec_knowledge_atoms USING vec0(
                atom_id INTEGER PRIMARY KEY,
                embedding FLOAT[384]
            )
        ''')

    # NUOVA TABELLA: Link Sinaptici tra atomi
    conn.execute('''
        CREATE TABLE IF NOT EXISTS synaptic_links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_id INTEGER,
            target_id INTEGER,
            link_type TEXT, -- 'similarity', 'dependency', 'contradiction'
            strength FLOAT,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(source_id) REFERENCES knowledge_atoms(id),
            FOREIGN KEY(target_id) REFERENCES knowledge_atoms(id),
            UNIQUE(source_id, target_id, link_type)
        )
    ''')

    conn.execute('''
        CREATE TABLE IF NOT EXISTS source_files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_path TEXT UNIQUE NOT NULL,
            last_modified TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            total_atoms INTEGER DEFAULT 0
        )
    ''')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_category ON knowledge_atoms(category)')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_hash ON knowledge_atoms(content_hash)')
    conn.commit()
    return conn


def _content_hash(text: str) -> str:
    """Hash leggero per deduplicazione."""
    import hashlib
    return hashlib.md5(text.strip().lower().encode()).hexdigest()


# ---- Parser flessibile ----

def _infer_category(text: str) -> str:
    """Inferisce la categoria del testo."""
    t = text.lower()
    if any(w in t for w in ['preferisco', 'amo', 'non mi piace', 'voglio', 'prefer', 'uso sempre', 'uso spesso']):
        return 'preference'
    if any(w in t for w in ['vincolo', 'limitazione', 'deve', 'non deve', 'vietato', 'obbligatorio', 'constraint', 'requisito']):
        return 'constraint'
    if any(w in t for w in ['milestone', 'completato', 'fatto', 'finito', 'rilasciato', 'done', 'deployed']):
        return 'milestone'
    if any(w in t for w in ['bug', 'errore', 'error', 'crash', 'fix', 'problema', 'issue']):
        return 'bug_fix'
    if any(w in t for w in ['idea', 'proposta', 'potremmo', 'sarebbe bello', 'futuro', 'piano', 'pianificato']):
        return 'idea'
    if any(w in t for w in ['progetto', 'project', 'tool', 'strumento', 'sistema', 'architettura']):
        return 'project_info'
    return 'general_fact'


def _extract_atoms_from_markdown(content: str, source_filename: str) -> list[dict]:
    """
    Parser flessibile: estrae atomi da QUALSIASI file .md.

    Strategia:
    1. Estrae blocchi strutturati (bullet points, sezioni con titolo)
    2. Come fallback, usa i paragrafi interi
    Filtra righe troppo corto o rumore puro.
    """
    atoms = []
    seen_hashes = set()

    def add_atom(text: str, category: str = None):
        text = text.strip()
        if len(text) < 20:   # troppo corto per essere utile
            return
        if len(text) > 1000:  # tronca blocchi enormi
            text = text[:1000] + "..."
        h = _content_hash(text)
        if h in seen_hashes:
            return
        seen_hashes.add(h)
        atoms.append({
            'content': text,
            'category': category or _infer_category(text),
            'source_file': source_filename,
            'content_hash': h
        })

    lines = content.split('\n')
    current_section = ""
    current_block = []

    for line in lines:
        stripped = line.strip()

        # Titoli markdown → nuova sezione
        if re.match(r'^#{1,4}\s+.+', stripped):
            # Salva blocco precedente
            if current_block:
                block_text = ' '.join(current_block).strip()
                if current_section:
                    block_text = f"[{current_section}] {block_text}"
                add_atom(block_text)
                current_block = []
            current_section = re.sub(r'^#+\s+', '', stripped)
            continue

        # Bullet points (-, *, •, numeri)
        bullet_match = re.match(r'^[-*•]\s+(.+)', stripped) or re.match(r'^\d+\.\s+(.+)', stripped)
        if bullet_match:
            item = bullet_match.group(1).strip()
            if current_section:
                add_atom(f"[{current_section}] {item}")
            else:
                add_atom(item)
            continue

        # Coppie chiave: valore
        kv_match = re.match(r'^([A-Za-zÀ-ÿ\s]{3,30}):\s+(.{15,})', stripped)
        if kv_match:
            add_atom(f"{kv_match.group(1).strip()}: {kv_match.group(2).strip()}")
            continue

        # Righe normali → accumulale in un blocco paragrafo
        if stripped and not stripped.startswith('```') and not stripped.startswith('---'):
            current_block.append(stripped)
        else:
            # Fine paragrafo
            if current_block:
                block_text = ' '.join(current_block).strip()
                if current_section:
                    block_text = f"[{current_section}] {block_text}"
                add_atom(block_text)
                current_block = []

    # Blocco finale
    if current_block:
        block_text = ' '.join(current_block).strip()
        if current_section:
            block_text = f"[{current_section}] {block_text}"
        add_atom(block_text)

    return atoms


# ---- Core: scan singolo file ----

def _scan_file(file_path: str, conn: sqlite3.Connection, force: bool = False) -> dict:
    """Indicizza un singolo file .md. Salta se già indicizzato (a meno di force=True)."""
    filename = os.path.basename(file_path)

    # Controlla se già indicizzato con stesso timestamp
    if not force:
        mtime = datetime.fromtimestamp(os.path.getmtime(file_path)).isoformat()
        row = conn.execute(
            'SELECT last_modified FROM source_files WHERE file_path = ?', (file_path,)
        ).fetchone()
        if row and row[0] >= mtime:
            return {"file": filename, "skipped": True, "reason": "già indicizzato"}

    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()

    if not content.strip():
        return {"file": filename, "skipped": True, "reason": "file vuoto"}

    atoms = _extract_atoms_from_markdown(content, filename)
    new_count = 0

    for atom in atoms:
        content = atom['content']
        category = atom['category']
        file_path_obj = Path(file_path)
        c_hash = atom['content_hash']

        # Deduplicazione globale: non inserire se hash già presente
        existing = conn.execute(
            'SELECT id FROM knowledge_atoms WHERE content_hash = ?',
            (c_hash,)
        ).fetchone()
        if not existing:
            # Inserimento atomo
            cursor = conn.execute('''
                INSERT INTO knowledge_atoms (content, category, source_file, content_hash)
                VALUES (?, ?, ?, ?)
            ''', (content, category, file_path_obj.name, c_hash))
            
            # Generazione embedding semantico
            if SEMANTIC_READY:
                atom_id = cursor.lastrowid
                try:
                    # Genera vettore (fastembed)
                    embeddings = list(embedding_model.embed([content]))
                    vector = embeddings[0] 
                    
                    # Fondamentale: Serializza il vettore in un blob di float32 per sqlite-vec
                    vector_blob = sqlite_vec.serialize_float32(vector)
                    
                    conn.execute('''
                        INSERT INTO vec_knowledge_atoms(atom_id, embedding)
                        VALUES (?, ?)
                    ''', (atom_id, vector_blob))
                except Exception as e:
                    _log(f"⚠️  Errore embedding per atomo {atom_id}: {e}")

            new_count += 1

    mtime_now = datetime.fromtimestamp(os.path.getmtime(file_path)).isoformat()
    conn.execute(
        'INSERT OR REPLACE INTO source_files (file_path, last_modified, total_atoms) VALUES (?, ?, ?)',
        (file_path, mtime_now, new_count)
    )
    conn.commit()

    return {"file": filename, "skipped": False, "atoms_extracted": len(atoms), "atoms_new": new_count}


# ---- Startup: auto-scan ultimi N giorni ----

def startup_autoscan(days: int = 7) -> dict:
    """
    Eseguito all'avvio del server.
    Scansiona i file .md degli ultimi `days` giorni che non sono ancora stati indicizzati.
    """
    _log(f"🚀 Avvio auto-scan ultimi {days} giorni...")

    if not os.path.exists(USER_MEMORY_PATH):
        _log(f"⚠️  Directory memoria non trovata: {USER_MEMORY_PATH}")
        return {"status": "skipped", "reason": "directory memoria assente"}

    conn = _get_db_connection()
    results = []
    today = datetime.now()

    # Cerca tutti i file .md modificati negli ultimi N giorni
    for fname in os.listdir(USER_MEMORY_PATH):
        if not fname.endswith('.md') or fname == "MEMORY_WEEKLY.md":
            continue
        
        file_path = os.path.join(USER_MEMORY_PATH, fname)
        try:
            mtime = datetime.fromtimestamp(os.path.getmtime(file_path))
            
            # Se il file è stato modificato nell'intervallo richiesto
            if mtime > (today - timedelta(days=days)):
                result = _scan_file(file_path, conn, force=False)
                results.append(result)
                if not result.get('skipped'):
                    _log(f"   ✅ {fname}: {result['atoms_new']} nuovi atomi")
        except Exception: 
            continue

    conn.close()

    total_new = sum(r.get('atoms_new', 0) for r in results if not r.get('skipped'))
    _log(f"✅ Auto-scan completato: {total_new} nuovi atomi indicizzati da {len(results)} file")

    return {
        "status": "done",
        "days_scanned": days,
        "files_processed": len(results),
        "total_new_atoms": total_new,
        "details": results
    }


# ---- Tool functions ----

def run_synapse_scan(target: str = None, force: bool = False) -> dict:
    """Scansiona un file memoria specifico (per data o percorso) e indicizza gli atomi."""
    # Se target è None, usa la data di oggi
    if not target:
        target = datetime.now().strftime('%Y-%m-%d')
    
    # Se il target sembra un percorso (ha separatori o estensione .md)
    if os.path.isabs(target) or "/" in target or "\\" in target or target.endswith('.md'):
        file_path = target
        # Fallback alla cartella memory se non è assoluto
        if not os.path.isabs(file_path):
            file_path = os.path.join(USER_MEMORY_PATH, file_path)
    else:
        # Default: tenta di trovare il file che contiene la data nel nome (es. CHATS_SYNC_YYYY-MM-DD.md)
        file_path = os.path.join(USER_MEMORY_PATH, f"{target}.md") # Fallback
        for fname in os.listdir(USER_MEMORY_PATH):
            if target in fname and fname.endswith('.md'):
                file_path = os.path.join(USER_MEMORY_PATH, fname)
                break

    if not os.path.exists(file_path):
        return {
            "status": "not_found",
            "path": target,
            "message": f"Nessun file memoria trovato: {file_path}",
            "tip": f"Verifica il percorso o crea il file in {USER_MEMORY_PATH}"
        }

    conn = _get_db_connection()
    try:
        # Esecuzione della scansione file (sincrona)
        result = _scan_file(file_path, conn, force=force)
    finally:
        conn.close()

    return {"status": "success", "date": target, **result}


def run_memory_search(query: str, limit: int = 10, category: str = None) -> dict:
    """Esegue ricerca ibrida (Testo + Semantica) nel database."""
    conn = _get_db_connection()
    results = []
    
    try:
        if SEMANTIC_READY and query:
            # --- RICERCA SEMANTICA (Hybrid) ---
            query_vector = list(embedding_model.embed([query]))[0]
            
            # --- APPLICAZIONE LORA (LIGM Active Memory) ---
            if LORA_READY and lora_engine and lora_engine.initialized:
                try:
                    query_tensor = torch.tensor(query_vector)
                    transformed_tensor = lora_engine.transform(query_tensor)
                    # Converti da tensor a numpy per sqlite-vec
                    query_vector = transformed_tensor.squeeze(0).detach().numpy()
                except Exception as e:
                    _log(f"⚠️ Errore trasformazione LoRA: {e}")

            sql = '''
                SELECT 
                    a.id, a.content, a.category, a.source_file, a.extracted_at,
                    v.distance as semantic_distance
                FROM vec_knowledge_atoms v
                JOIN knowledge_atoms a ON v.atom_id = a.id
                WHERE v.embedding MATCH ? AND k = ?
            '''
            params = [sqlite_vec.serialize_float32(query_vector), limit * 2] # Prendiamo più risultati per filtrare
            
            if category:
                sql += ' AND a.category = ?'
                params.append(category)
                
            cursor = conn.execute(sql, params)
        else:
            # --- RICERCA TESTUALE CLASSICA ---
            sql = '''
                SELECT id, content, category, source_file, extracted_at, 100 as semantic_distance
                FROM knowledge_atoms 
                WHERE (content LIKE ? OR source_file LIKE ?)
            '''
            params = [f'%{query}%', f'%{query}%']
            
            if category:
                sql += ' AND category = ?'
                params.append(category)
                
            sql += ' ORDER BY extracted_at DESC LIMIT ?'
            params.append(limit)
            cursor = conn.execute(sql, params)

        for row in cursor.fetchall():
            dist = row[5]
            # Normalizzazione dello score in 0..1 (più alto = più simile)
            # In L2, 0 è identico, cresce con la differenza.
            score = round(1.0 / (1.0 + dist), 3) if SEMANTIC_READY and query else 0
            
            # --- CONTROLLO NODI DI TENSIONE (v1.3) ---
            tension = conn.execute('SELECT notes FROM synaptic_links WHERE (source_id = ? OR target_id = ?) AND link_type = ?', 
                                 (row[0], row[0], 'contradiction')).fetchone()
            
            res_item = {
                "id": row[0],
                "content": row[1],
                "category": row[2],
                "source_file": row[3],
                "date": row[4],
                "semantic_score": score,
                "access_count": row[0] # Segnaposto momentaneo per debug
            }
            if tension:
                res_item["tension"] = f"⚠️ Tensione rilevata: {tension[0]}"
                
            results.append(res_item)
            
        # --- AGGIORNAMENTO DINAMICO (Attivazione Bio-Ispirata) ---
        if results:
            try:
                # Prendi solo i top 3 risultati per l'attivazione
                top_ids = [r['id'] for r in results[:3]]
                placeholders = ','.join(['?'] * len(top_ids))
                conn.execute(f'''
                    UPDATE knowledge_atoms 
                    SET access_count = access_count + 1, 
                        last_accessed = CURRENT_TIMESTAMP,
                        importance_weight = importance_weight + 0.1
                    WHERE id IN ({placeholders})
                ''', top_ids)
                conn.commit()
            except Exception as e:
                _log(f"⚠️ Errore attivazione atomi: {e}")
            
        # Ordina per rilevanza se semantico
        if SEMANTIC_READY:
            results.sort(key=lambda x: x['semantic_score'], reverse=True)
            results = results[:limit]

    except Exception as e:
        _log(f"Errore ricerca: {e}")
        return {"error": str(e)}
    finally:
        conn.close()

    return {
        "query": query,
        "semantic_enabled": SEMANTIC_READY,
        "results_count": len(results),
        "results": results,
        "tip": "Usa synapse_scan per aggiornare la memoria." if not results else None,
        "lora_active": LORA_READY and lora_engine.initialized if lora_engine else False
    }


def run_find_similar_atoms(atom_id: int, limit: int = 5) -> dict:
    """Trova atomi concettualmente simili a quello specificato via ID (Ricordo Associativo)."""
    if not SEMANTIC_READY:
        return {"error": "Motore semantico non attivo."}
        
    conn = _get_db_connection()
    try:
        # Prendi il vettore dell'atomo target
        row = conn.execute('SELECT embedding FROM vec_knowledge_atoms WHERE atom_id = ?', (atom_id,)).fetchone()
        if not row:
            return {"error": f"Vettore non trovato per atomo {atom_id}. Prova a rieseguire la migrazione."}
            
        target_vector_blob = row[0]
        
        # Cerca i più vicini eccetto se stesso
        sql = '''
            SELECT 
                a.id, a.content, a.category, a.source_file, a.extracted_at,
                v.distance
            FROM vec_knowledge_atoms v
            JOIN knowledge_atoms a ON v.atom_id = a.id
            WHERE v.embedding MATCH ? AND k = ? AND a.id != ?
        '''
        cursor = conn.execute(sql, [target_vector_blob, limit + 1, atom_id])
        
        results = []
        for r in cursor.fetchall():
            results.append({
                "id": r[0],
                "content": r[1],
                "category": r[2],
                "source_file": r[3],
                "date": r[4],
                "similarity_score": round(1.0 / (1.0 + r[5]), 3)
            })
            
        return {
            "target_id": atom_id,
            "similar_atoms_found": len(results),
            "results": results
        }
    except Exception as e:
        _log(f"Errore ricerca associativa: {e}")
        return {"error": str(e)}
    finally:
        conn.close()



# ---- AGENTI AUTONOMI (Ecosistema Sinapsi v2.0) ----

def run_proactive_curation(limit: int = 5) -> dict:
    """Agent: Curator. Trova link associativi tra gli atomi non ancora verificati."""
    if not SEMANTIC_READY:
        return {"status": "error", "message": "Motore semantico non pronto."}
    
    conn = _get_db_connection()
    try:
        # 1. Prendi atomi che non sono stati 'curati' recentemente
        atoms = conn.execute('''
            SELECT id, content FROM knowledge_atoms 
            WHERE meta_checked = 0 
            ORDER BY importance_weight DESC LIMIT ?
        ''', (limit,)).fetchall()
        
        links_created = 0
        for aid, content in atoms:
            # Trova simili (logic simile a run_find_similar_atoms)
            row = conn.execute('SELECT embedding FROM vec_knowledge_atoms WHERE atom_id = ?', (aid,)).fetchone()
            if not row: continue
            
            target_vector = row[0]
            # Cerca i top 3 più simili (escluso se stesso)
            cursor = conn.execute('''
                SELECT a.id, v.distance 
                FROM vec_knowledge_atoms v
                JOIN knowledge_atoms a ON v.atom_id = a.id
                WHERE v.embedding MATCH ? AND k = 4 AND a.id != ?
            ''', [target_vector, aid])
            
            for sim_id, dist in cursor.fetchall():
                score = round(1.0 / (1.0 + dist), 3)
                if score > 0.7: # Soglia di affinità
                    conn.execute('''
                        INSERT OR IGNORE INTO synaptic_links (source_id, target_id, link_type, strength)
                        VALUES (?, ?, 'similarity', ?)
                    ''', (aid, sim_id, score))
                    links_created += 1
            
            # Segna come controllato
            conn.execute('UPDATE knowledge_atoms SET meta_checked = 1 WHERE id = ?', (aid,))
        
        conn.commit()
        return {"status": "success", "agent": "Curator", "links_created": links_created}
    except Exception as e:
        _log(f"⚠️ Errore Curator: {e}")
        return {"status": "error", "message": str(e)}
    finally:
        conn.close()


def run_self_healing() -> dict:
    """Agent: Instructor/Healer. Verifica contraddizioni tra atomi della stessa categoria."""
    conn = _get_db_connection()
    issues_found = []
    try:
        # Prendi categorie 'sensibili'
        for cat in ['constraint', 'preference', 'project_info']:
            atoms = conn.execute('SELECT id, content FROM knowledge_atoms WHERE category = ? ORDER BY id DESC LIMIT 20', (cat,)).fetchall()
            if len(atoms) < 2: continue
            
            # Preparazione prompt per LLM per rilevare conflitti
            context = "\n".join([f"ID {a[0]}: {a[1]}" for a in atoms])
            prompt = f"""
            Analizza questi atomi di conoscenza nella categoria '{cat}'.
            Rileva se ci sono CONTRADDIZIONI (es. versioni diverse, requisiti opposti).
            Rispondi SOLAMENTE con un JSON array di coppie di ID che confliggono, o un array vuoto [].
            Esempio: [ {{"id1": 10, "id2": 25, "reason": "Conflitto versione Python"}} ]
            
            CONTESTO:
            {context}
            """
            
            res = _call_local_llm(prompt)
            if "{" in res or "[" in res:
                try:
                    # Pulizia minima
                    json_str = re.search(r'(\[.*\])', res.replace('\n', ' '), re.DOTALL).group(1)
                    conflicts = json.loads(json_str)
                    for c in conflicts:
                        # Crea un link di tipo 'contradiction'
                        conn.execute('''
                            INSERT OR IGNORE INTO synaptic_links (source_id, target_id, link_type, notes)
                            VALUES (?, ?, 'contradiction', ?)
                        ''', (c['id1'], c['id2'], c['reason']))
                        issues_found.append(c)
                except: pass
        
        conn.commit()
        return {"status": "success", "agent": "SelfHealer", "conflicts_detected": len(issues_found), "details": issues_found}
    except Exception as e:
        _log(f"⚠️ Errore SelfHealer: {e}")
        return {"status": "error", "message": str(e)}
    finally:
        conn.close()


def run_dream_sequence() -> dict:
    """Agent: Dreamer. Fa una 'passeggiata casuale' (random walk) tra gli atomi e distilla nuove associazioni."""
    if not SEMANTIC_READY:
        return {"status": "error", "message": "Motore semantico non attivo, il sogno richiede embedding vettoriali."}
        
    conn = _get_db_connection()
    try:
        # Prendi un atomo saliente a caso come punto di partenza
        start_atom = conn.execute('SELECT id, content FROM knowledge_atoms WHERE importance_weight > 1.2 ORDER BY RANDOM() LIMIT 1').fetchone()
        if not start_atom:
            return {"status": "skipped", "message": "Nessun atomo interessante (peso > 1.2) da cui far partire il sogno."}
            
        current_id, current_content = start_atom
        path = [current_content]
        
        # Facciamo 3 salti associativi casuali usando il motore semantico
        for _ in range(3):
            # Cerca vettori simili (saltiamo noi stessi e i già visti se possibile)
            row = conn.execute('SELECT embedding FROM vec_knowledge_atoms WHERE atom_id = ?', (current_id,)).fetchone()
            if not row: break
            
            # Ordina random tra i top 10 risultati vicini per aggiungere "caos creativo" guidato
            cursor = conn.execute('''
                SELECT a.id, a.content
                FROM vec_knowledge_atoms v
                JOIN knowledge_atoms a ON v.atom_id = a.id
                WHERE v.embedding MATCH ? AND k = 10 AND a.id != ?
                ORDER BY RANDOM() LIMIT 1
            ''', [row[0], current_id])
            
            next_atom = cursor.fetchone()
            if next_atom and next_atom[1] not in path:
                current_id, current_content = next_atom
                path.append(current_content)
            else:
                break
                
        if len(path) < 2:
            return {"status": "skipped", "message": "Sogno troppo breve, la mente si è interrotta."}
            
        # Preparazione del prompt per far "sognare" l'LLM
        narrative = "\n-> ".join(path)
        prompt = f"""
        Sei il subconscio del sistema. Analizza questa catena di ricordi/frammenti scollegati tra loro:
        {narrative}
        
        Trova una metafora, un'associazione filosofica o un'idea creativa che li unisca e dia all'utente una nuova prospettiva. 
        Scrivi un breve pensiero (massimo 3 frasi) ispirante, come se fosse un'intuizione avuta in sogno. Inizia con le parole "Nel sogno che ho fatto..." 
        Rispondi SOLAMENTE in formato JSON con la chiave "dream_insight".
        """
        
        res = _call_local_llm(prompt)
        insight = "Sogno frammentato e incomprensibile."
        if "{" in res:
            try:
                json_str = re.search(r'(\{.*\})', res.replace('\n', ' '), re.DOTALL).group(1)
                data = json.loads(json_str)
                insight = data.get("dream_insight", str(data))
            except: 
                pass
                
        # Salva il sogno come un nuovo atomo
        c_hash = _content_hash(f"dream_{insight}")
        existing = conn.execute('SELECT id FROM knowledge_atoms WHERE content_hash = ?', (c_hash,)).fetchone()
        if not existing:
            conn.execute('''
                INSERT INTO knowledge_atoms (content, category, source_file, content_hash, importance_weight)
                VALUES (?, 'idea', 'DREAM_SEQUENCE', ?, 2.5)
            ''', (insight, c_hash))
            conn.commit()
            
        return {"status": "success", "agent": "Dreamer", "path_length": len(path), "insight": insight}
        
    except Exception as e:
        _log(f"⚠️ Errore Dreamer: {e}")
        return {"status": "error", "message": str(e)}
    finally:
        conn.close()


def run_github_scout() -> dict:
    """Agent: Researcher/Scout. Scansiona la struttura del progetto locale per aggiornare la visione d'insieme."""
    try:
        files = []
        for root, dirs, filenames in os.walk(NEBULA_HOME):
            # Escludi cartelle pesanti
            dirs[:] = [d for d in dirs if d not in ['.git', '__pycache__', 'node_modules', 'venv']]
            for f in filenames:
                if f.endswith(('.py', '.md', '.json')):
                    files.append(os.path.relpath(os.path.join(root, f), NEBULA_HOME))
        
        summary = f"Progetto Nebula: {len(files)} file rilevati. Struttura principale: " + ", ".join(files[:15])
        c_hash = _content_hash(f"scout_{summary}")
        
        conn = _get_db_connection()
        existing = conn.execute('SELECT id FROM knowledge_atoms WHERE content_hash = ?', (c_hash,)).fetchone()
        if not existing:
            conn.execute('''
                INSERT INTO knowledge_atoms (content, category, source_file, content_hash, importance_weight)
                VALUES (?, 'project_info', 'PROJECT_STRUCTURE', ?, 2.0)
            ''', (summary, c_hash))
            conn.commit()
            status = "new_data"
        else:
            status = "up_to_date"
        conn.close()
        
        return {"status": "success", "agent": "Scout", "result": status, "files_found": len(files)}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def run_static_analysis(file_path: str) -> dict:
    """Analisi statica di un file Python."""
    if not os.path.exists(file_path):
        return {"error": f"File non trovato: {file_path}"}

    import ast
    issues = []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            source_code = f.read()

        ast.parse(source_code, filename=file_path)  # Verifica sintassi
        lines = source_code.split('\n')

        patterns = []
        if os.path.exists(CONFIG_PATH):
            with open(CONFIG_PATH, 'r', encoding='utf-8') as cf:
                config = json.load(cf)
            for rule_data in config.get('analysis_patterns', {}).values():
                if rule_data.get('enabled') and rule_data.get('regex_pattern'):
                    patterns.append((
                        rule_data['regex_pattern'],
                        rule_data.get('severity', 'info'),
                        rule_data.get('description', '')
                    ))

        for line_num, line in enumerate(lines, 1):
            for pattern, severity, desc in patterns:
                if pattern in line:
                    issues.append({'line': line_num, 'severity': severity,
                                   'message': desc, 'snippet': line.strip()[:100]})

    except SyntaxError as e:
        issues.append({'line': e.lineno, 'severity': 'error',
                       'message': f'Syntax error: {e.msg}', 'snippet': ''})
    except Exception as e:
        return {"error": str(e)}

    return {"file": os.path.basename(file_path), "total_issues": len(issues), "issues": issues[:50]}


def list_memory_files() -> dict:
    """Elenca i file di memoria disponibili."""
    if not os.path.exists(USER_MEMORY_PATH):
        return {"files": [], "message": "Directory memoria non trovata",
                "tip": f"Crea la cartella: {USER_MEMORY_PATH}"}

    files = sorted([f for f in os.listdir(USER_MEMORY_PATH) if f.endswith('.md')], reverse=True)

    conn = _get_db_connection()
    indexed = {row[0] for row in conn.execute('SELECT file_path FROM source_files').fetchall()}
    conn.close()

    file_info = []
    for fname in files[:20]:
        fp = os.path.join(USER_MEMORY_PATH, fname)
        file_info.append({
            "name": fname,
            "size_kb": round(os.path.getsize(fp) / 1024, 1),
            "indexed": fp in indexed
        })

    return {
        "memory_dir": USER_MEMORY_PATH,
        "total_files": len(files),
        "files": file_info
    }


def get_synapse_stats() -> dict:
    """Statistiche complete del database Sinapsi inclusa la parte semantica."""
    conn = _get_db_connection()
    try:
        total = conn.execute('SELECT COUNT(*) FROM knowledge_atoms').fetchone()[0]
        
        # Statistiche vettoriali
        total_vectors = 0
        if SEMANTIC_READY:
            try:
                total_vectors = conn.execute('SELECT COUNT(*) FROM vec_knowledge_atoms').fetchone()[0]
            except: pass

        by_cat = conn.execute(
            'SELECT category, COUNT(*) FROM knowledge_atoms GROUP BY category ORDER BY COUNT(*) DESC'
        ).fetchall()
        recent = conn.execute(
            'SELECT content, category, source_file FROM knowledge_atoms ORDER BY id DESC LIMIT 5'
        ).fetchall()
        sources = conn.execute('SELECT COUNT(*) FROM source_files').fetchone()[0]
        oldest = conn.execute('SELECT MIN(extracted_at) FROM knowledge_atoms').fetchone()[0]
        newest = conn.execute('SELECT MAX(extracted_at) FROM knowledge_atoms').fetchone()[0]
    finally:
        conn.close()

    return {
        "status": "online",
        "semantic_engine": "ACTIVE (sqlite-vec + fastembed)" if SEMANTIC_READY else "DISABLED",
        "total_atoms": total,
        "total_vectors": total_vectors,
        "indexed_sources": sources,
        "database_sync": "100%" if total == total_vectors else f"{round(total_vectors/max(1,total)*100, 1)}%",
        "oldest_entry": oldest,
        "newest_entry": newest,
        "by_category": {row[0]: row[1] for row in by_cat},
        "recent_atoms": [{"content": r[0][:100], "category": r[1], "source": r[2]} for r in recent]
    }


def rescan_all(days: int = 30) -> dict:
    """Forza la re-indicizzazione degli ultimi N giorni sovrascrivendo i dati esistenti."""
    _log(f"🔄 Rescan forzato ultimi {days} giorni...")
    conn = _get_db_connection()
    today = datetime.now()
    results = []

    # Cerca tutti i file .md modificati negli ultimi N giorni
    for fname in os.listdir(USER_MEMORY_PATH):
        if not fname.endswith('.md'):
            continue
            
        fp = os.path.join(USER_MEMORY_PATH, fname)
        try:
            mtime = datetime.fromtimestamp(os.path.getmtime(fp))
            if mtime > (today - timedelta(days=days)):
                result = _scan_file(fp, conn, force=True)
                results.append(result)
        except Exception: continue

    conn.close()
    total_new = sum(r.get('atoms_new', 0) for r in results)
    return {"status": "done", "files_rescanned": len(results), "total_new_atoms": total_new, "details": results}


def run_synapse_oblivion(min_strength: float = None, decay_rate: float = None) -> dict:
    """Esegue l'Oblio Selettivo: calcola il decadimento e archivia atomi deboli, basandosi sulla Personalità attiva."""
    global CURRENT_PROFILE
    prof = MEMORY_PROFILES.get(CURRENT_PROFILE, MEMORY_PROFILES["equilibrato"])
    
    # Applica parametri del profilo se non specificati dal tool
    min_str = min_strength if min_strength is not None else prof["min_strength"]
    decay = decay_rate if decay_rate is not None else prof["decay_rate"]
    
    archived_count = 0
    conn = _get_db_connection()
    archive_file = os.path.join(USER_MEMORY_PATH, "MEMORY_ARCHIVE.md")
    
    try:
        # 1. Carica tutti gli atomi con le loro metriche di vita
        atoms = conn.execute('''
            SELECT id, content, category, importance_weight, access_count, last_accessed, extracted_at 
            FROM knowledge_atoms
        ''').fetchall()
        
        now = datetime.now()
        ids_to_archive = []
        archive_entries = []
        
        for atom in atoms:
            aid, content, cat, weight, access, last_acc, extr = atom
            
            # Calcolo giorni di inattività (con fallback su data estrazione)
            try:
                date_str = last_acc or extr
                if not date_str:
                    dt_last = now
                else:
                    # Normalizza a stringa per evitare errori fromisoformat
                    dt_last = datetime.fromisoformat(str(date_str).replace(' ', 'T'))
            except (ValueError, TypeError):
                dt_last = now
                _log(f"⚠️ Formato data non valido per atomo {aid}: {last_acc}. Uso fallback.")

            delta = now - dt_last
            days_inactive = delta.total_seconds() / 86400.0
            
            # Algoritmo Bio-Dinamico: La forza diminuisce col tempo ma è protetta dalla rilevanza (weight)
            # Versione v1.3: Decadimento Esponenziale (Ebbinghaus-style)
            # Formula: forza = (peso * e^(-decay * giorni)) + (accessi * 0.1)
            import math
            strength = (weight * math.exp(-decay * days_inactive)) + (access * 0.1)
            
            if strength < min_str:
                ids_to_archive.append(aid)
                archive_entries.append(f"- [{cat}] {content} (ID: {aid}, Strength: {strength:.2f}, Days: {days_inactive:.1f})")

        # 2. Archivia gli atomi deboli (Oblio)
        if ids_to_archive:
            with open(archive_file, "a", encoding="utf-8") as f:
                f.write(f"\n## 🌑 Oblio Selettivo: {now.strftime('%Y-%m-%d %H:%M')}\n")
                f.write(f"Archiviati {len(ids_to_archive)} atomi deboli.\n")
                for entry in archive_entries:
                    f.write(entry + "\n")
            
            # Rimuovi dal database attivo (Sinapsi)
            placeholders = ','.join(['?'] * len(ids_to_archive))
            conn.execute(f"DELETE FROM knowledge_atoms WHERE id IN ({placeholders})", ids_to_archive)
            if SEMANTIC_READY:
                conn.execute(f"DELETE FROM vec_knowledge_atoms WHERE atom_id IN ({placeholders})", ids_to_archive)
            conn.commit()
            archived_count = len(ids_to_archive)
            
    except Exception as e:
        _log(f"⚠️ Errore durante l'oblio: {e}")
        return {"status": "error", "message": str(e)}
    finally:
        conn.close()
        
    return {
        "status": "success",
        "archived_count": archived_count,
        "archive_file": "MEMORY_ARCHIVE.md",
        "personality_used": CURRENT_PROFILE,
        "message": f"Dimenticati {archived_count} atomi con forza inferiore a {min_str} (Decadimento: {decay})."
    }


# ---- Distillazione Semantica (Selective Oblivion - Fase 3) ----

def _call_local_llm(prompt: str, model: str = None) -> str:
    """Chiama l'API locale di LM Studio. Se model è None, usa quello corrente."""
    m_name = model or DEFAULT_MODEL
    
    payload = {
        "messages": [
            {"role": "system", "content": "Sei un analista esperto. Rispondi SOLO in JSON."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.1,
        "max_tokens": 1500 # Aumentato per gestire distillazioni complete
    }
    
    # Se abbiamo un nome modello specifico, lo aggiungiamo
    if m_name:
        payload["model"] = m_name
    
    try:
        _log(f"   📡 Richiesta LLM ({'modello corrente' if not m_name else m_name})...")
        response = requests.post(LM_STUDIO_API_URL, json=payload, timeout=300)
        response.raise_for_status()
        data = response.json()
        return data['choices'][0]['message']['content']
    except Exception as e:
        _log(f"⚠️ Errore LLM: {e}")
        return ""


def run_distill_weekly(days: int = 7) -> dict:
    """
    Strato 'Oblio Selettivo':
    1. Raccoglie i log degli ultimi N giorni.
    2. Chiede a LM Studio di distillare pattern di conoscenza significativi.
    3. Salva i nuovi atomi in SQLite e aggiorna MEMORY_WEEKLY.md.
    """
    _log(f"🧠 Avvio distillazione settimanale (ultimi {days} giorni)...")
    
    today = datetime.now()
    logs_data = []
    
    # Cerca tutti i file .md modificati negli ultimi N giorni
    for fname in os.listdir(USER_MEMORY_PATH):
        if not fname.endswith('.md') or fname == "MEMORY_WEEKLY.md":
            continue
            
        fp = os.path.join(USER_MEMORY_PATH, fname)
        mtime = datetime.fromtimestamp(os.path.getmtime(fp))
        
        # Se il file è stato modificato nell'intervallo richiesto
        if mtime > (today - timedelta(days=days)):
            try:
                with open(fp, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                    if content.strip():
                        _log(f"   📂 Inclusione file: {fname}")
                        logs_data.append(f"--- FILE: {fname} (Data: {mtime.strftime('%Y-%m-%d')}) ---\n{content}")
            except Exception as e:
                _log(f"   ⚠️ Errore lettura {fname}: {e}")

    if not logs_data:
        return {"status": "error", "message": "Nessun log trovato per il periodo specificato. Verifica la cartella memory."}

    # Uniamo i log e limitiamo a un numero ragionevole di caratteri
    full_logs = "\n\n".join(logs_data)
    if len(full_logs) > 4000:
        full_logs = full_logs[-4000:] # Prendi la fine, più recente
        _log("   ⚠️ Log estesi: troncamento a 4.000 caratteri per velocità massima.")

    prompt = f"""
    Analizza i log tecnici seguenti e distilla la conoscenza in JSON.
    Sii sintetico: estrai MASSIMO 8 punti chiave (atomi).
    Recupera preferenze utente, vincoli tecnici e traguardi.
    
    FORMATO JSON RICHIESTO:
    {{
      "distilled_atoms": [
        {{ "category": "preference|constraint|milestone|core_fact", "content": "...", "importance": 1-10 }}
      ],
      "weekly_summary": "Breve riassunto narrativo"
    }}
    
    LOG:
    {full_logs}
    """

    response_text = _call_local_llm(prompt)
    if not response_text:
        return {"status": "error", "message": "LM Studio non ha restituito alcun contenuto."}
    
    try:
        # Pulizia risposta per estrarre JSON se il modello aggiunge testo extra
        clean_response = response_text.replace('\n', ' ').strip()
        json_match = re.search(r'(\{.*\})', clean_response, re.DOTALL)
        
        if json_match:
            clean_json = json_match.group(1)
            try:
                distillation = json.loads(clean_json)
            except json.JSONDecodeError as je:
                # Tentativo di recupero se il JSON è troncato ma recuperabile (opzionale)
                # In questo caso lanciamo un errore più chiaro
                _log(f"⚠️ JSON troncato o malformato: {clean_json[:100]}...")
                raise je
        else:
            distillation = json.loads(response_text)
            
        new_atoms = distillation.get('distilled_atoms', [])
        summary = distillation.get('weekly_summary', 'Riassunto non generato.')
        
        # 1. Scrittura su Database
        conn = _get_db_connection()
        atoms_count = 0
        for atom in new_atoms:
            content = f"[WEEKLY DISTILLATION] {atom['content']}"
            category = atom.get('category', 'general_fact')
            c_hash = _content_hash(f"distill_{content}")
            
            # Verifica se già presente (deduplicazione)
            existing = conn.execute('SELECT id FROM knowledge_atoms WHERE content_hash = ?', (c_hash,)).fetchone()
            if not existing:
                cursor = conn.execute('''
                    INSERT INTO knowledge_atoms (content, category, source_file, content_hash)
                    VALUES (?, ?, ?, ?)
                ''', (content, category, "MEMORY_WEEKLY.md", c_hash))
                
                if SEMANTIC_READY:
                    atom_id = cursor.lastrowid
                    try:
                        vector = list(embedding_model.embed([content]))[0]
                        conn.execute('INSERT INTO vec_knowledge_atoms(atom_id, embedding) VALUES (?, ?)', 
                                   (atom_id, sqlite_vec.serialize_float32(vector)))
                    except: pass
                atoms_count += 1
        
        conn.commit()
        conn.close()
        
        # 2. Aggiornamento MEMORY_WEEKLY.md
        ts = datetime.now().strftime("%Y-%m-%d %H:%M")
        with open(WEEKLY_MEMORY_FILE, "a", encoding="utf-8") as f:
            f.write(f"\n\n## 🗓️ Report Distillazione: {ts}\n")
            f.write(f"**Riassunto:** {summary}\n\n")
            f.write("**Nuovi Atomi di Conoscenza:**\n")
            for atom in new_atoms:
                f.write(f"- [{atom['category'].upper()}] {atom['content']} (Imp: {atom.get('importance', 5)})\n")
        
        _log(f"✅ Distillazione completata: {atoms_count} nuovi atomi creati.")
        return {
            "status": "success",
            "date": ts,
            "new_atoms_count": atoms_count,
            "summary": summary,
            "file_updated": "MEMORY_WEEKLY.md"
        }
    except Exception as e:
        _log(f"⚠️ Errore parsing risposta distillazione: {e}")
        return {"status": "error", "message": f"Errore parsing JSON: {str(e)}", "raw_response": response_text[:200]}


    return res


def run_smart_search(query: str, max_retries: int = 3) -> dict:
    """Esegue una ricerca web intelligente con sanitizzazione e limite loop."""
    if not SEARCH_AGENT_READY:
        return {"error": "Modulo search_agent non caricato correttamente."}
    
    _log(f"🔎 Avvio Smart Search Agent: {query} (max {max_retries} tentativi)")
    agent = LocalLLMSearchAgent(max_retries=max_retries)
    
    # Per ora usiamo una ricerca simulata via DuckDuckGo o placeholder
    res = agent.execute_web_query(query)
    if res['status'] == 'success':
        clened_data = agent.sanitize_html(res['data'])
        return {
            "status": "success",
            "query": query,
            "agent_state": f"Retry {agent.current_retry}/{max_retries}",
            "findings": clened_data,
            "tip": "FORMATO RISPOSTA: Usare FINAL_ANSWER se l'info è sufficiente, altrimenti SEARCH con nuovi termini."
        }
    return res


def run_get_proactive_context(query: str, limit: int = 5) -> dict:
    """Aggregatore di contesto: estrae cronologia, semantica e 'pilastri' di importanza."""
    conn = _get_db_connection()
    context = []
    
    try:
        # 1. Ricerca Semantica per la query attuale
        semantic_res = run_memory_search(query, limit=3)
        if "results" in semantic_res:
            for r in semantic_res["results"]:
                context.append({
                    "type": "semantic_match",
                    "content": r["content"],
                    "category": r["category"],
                    "score": r["semantic_score"]
                })
        
        # 2. Ultime 5 entrate (Recenza cronologica)
        recent = conn.execute('''
            SELECT content, category, extracted_at FROM knowledge_atoms 
            ORDER BY id DESC LIMIT 5
        ''').fetchall()
        for r in recent:
            context.append({
                "type": "recent_memory",
                "content": r[0],
                "category": r[1],
                "date": r[2]
            })
            
        # 3. I Pilastri (Alta importanza > 1.8)
        pillars = conn.execute('''
            SELECT content, category FROM knowledge_atoms 
            WHERE importance_weight > 1.8 ORDER BY RANDOM() LIMIT 3
        ''').fetchall()
        for r in pillars:
            context.append({
                "type": "core_pillar",
                "content": r[0],
                "category": r[1]
            })

        # 4. Sintesi del Mood (Basata sulla categoria prevalente recente)
        mood_map = {}
        for r in recent:
            mood_map[r[1]] = mood_map.get(r[1], 0) + 1
        top_mood = max(mood_map, key=mood_map.get) if mood_map else "neutral"

        # Deduplicazione base (ID simulato hash)
        seen = set()
        final_context = []
        for c in context:
            h = _content_hash(c["content"])
            if h not in seen:
                seen.add(h)
                final_context.append(c)

        return {
            "query": query,
            "detected_mood": top_mood,
            "context_size": len(final_context),
            "memories": final_context,
            "formatting_tip": "Includi questi riferimenti nella tua risposta per apparire più consapevole e coerente."
        }
    except Exception as e:
        _log(f"⚠️ Errore Brain Connector: {e}")
        return {"error": str(e)}
    finally:
        conn.close()


# ---- MCP Server ----

app = Server("the-weaver")


@app.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="synapse_scan",
            description="Scansiona un file memoria .md e indicizza i contenuti nel database Sinapsi. Supporta 'date' o 'path'.",
            inputSchema={
                "type": "object",
                "properties": {
                    "date": {"type": "string", "description": "Data YYYY-MM-DD (default: oggi)"},
                    "path": {"type": "string", "description": "Percorso al file (alias per data se contiene data)"},
                    "force": {"type": "boolean", "description": "Se true, re-indicizza anche se già presente (default: false)"}
                }
            }
        ),
        types.Tool(
            name="memory_search",
            description="Cerca negli atomi di conoscenza indicizzati. Supporta filtro per categoria.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Testo da cercare"},
                    "limit": {"type": "integer", "description": "Max risultati (default: 10)", "default": 10},
                    "category": {"type": "string", "description": "Filtra per categoria (opzionale)"}
                },
                "required": ["query"]
            }
        ),
        types.Tool(
            name="analyze_python_file",
            description="Analisi statica di un file Python. Supporta 'file_path' o 'path'.",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "Percorso assoluto al file .py"},
                    "path": {"type": "string", "description": "Alias per file_path"}
                }
            }
        ),
        types.Tool(
            name="list_memory_files",
            description="Elenca i file .md nella cartella memoria, con stato di indicizzazione per ciascuno.",
            inputSchema={"type": "object", "properties": {}}
        ),
        types.Tool(
            name="read_file",
            description="Legge il contenuto di un file dal filesystem. Accetta 'path' o 'filename'.",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Percorso completo del file."},
                    "filename": {"type": "string", "description": "Alias per path."}
                }
            }
        ),
        types.Tool(
            name="write_file",
            description="Scrive contenuto in un file. Accetta 'path' o 'filename'.",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Percorso completo del file."},
                    "filename": {"type": "string", "description": "Alias per path."},
                    "content": {"type": "string", "description": "Contenuto da scrivere."}
                },
                "required": ["content"]
            }
        ),
        types.Tool(
            name="synapse_stats",
            description="Statistiche complete del database Sinapsi: atomi totali, categorie, fonti indicizzate, atomi recenti.",
            inputSchema={"type": "object", "properties": {}}
        ),
        types.Tool(
            name="synapse_deep_learn",
            description="Allena lo strato LoRA neurale sugli atomi di conoscenza per 'interiorizzare' i pattern.",
            inputSchema={
                "type": "object",
                "properties": {
                    "iterations": {"type": "integer", "description": "Cicli di training (default 5)", "default": 5}
                }
            }
        ),
        types.Tool(
            name="list_files",
            description="Elenca file e cartelle in un percorso specificato.",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Percorso della directory."},
                    "filename": {"type": "string", "description": "Alias per path."}
                }
            }
        ),
        types.Tool(
            name="create_folder",
            description="Crea una nuova cartella.",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Percorso della cartella da creare."},
                    "filename": {"type": "string", "description": "Alias per path."}
                }
            }
        ),
        types.Tool(
            name="rescan_all",
            description="Forza la re-indicizzazione completa degli ultimi N giorni di file memoria. Utile dopo aver modificato file già scansionati.",
            inputSchema={
                "type": "object",
                "properties": {
                    "days": {"type": "integer", "description": "Quanti giorni passati rescansionare (default: 30)", "default": 30}
                }
            }
        ),
        types.Tool(
            name="sync_conversations",
            description="Sincronizza le chat di LM Studio nella memoria Sinapsi (Bridge).",
            inputSchema={"type": "object", "properties": {}}
        ),
        types.Tool(
            name="find_similar_atoms",
            description="Ricordo associativo: trova atomi concettualmente simili a un atomo specifico (tramite ID).",
            inputSchema={
                "type": "object",
                "properties": {
                    "atom_id": {"type": "integer", "description": "L'ID dell'atomo di riferimento."},
                    "limit": {"type": "integer", "description": "Numero di ricordi simili da trovare (default: 5)", "default": 5}
                },
                "required": ["atom_id"]
            }
        ),
        types.Tool(
            name="distill_weekly",
            description="Strato 'Oblio Selettivo': Analizza i log degli ultimi N giorni e distilla la conoscenza in un riassunto semantico salvato nel database e in MEMORY_WEEKLY.md.",
            inputSchema={
                "type": "object",
                "properties": {
                    "days": {"type": "integer", "description": "Numero di giorni passati da analizzare (default: 7)", "default": 7}
                }
            }
        ),
        types.Tool(
            name="web_search_smart",
            description="Ricerca web avanzata per LLM locali: include sanitizzazione HTML, protezione dai loop e troncamento contesto automatico.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Query di ricerca."},
                    "max_retries": {"type": "integer", "description": "Limite tentativi (default: 3)", "default": 3}
                },
                "required": ["query"]
            }
        ),
        types.Tool(
            name="synapse_oblivion",
            description="L'Oblio Selettivo: Esegue il decadimento bio-dinamico della memoria e archivia gli atomi obsoleti/deboli.",
            inputSchema={
                "type": "object",
                "properties": {
                    "min_strength": {"type": "number", "description": "Soglia minima di sopravvivenza (default: 0.5)", "default": 0.5},
                    "decay_rate": {"type": "number", "description": "Velocità di decadimento giornaliero (default: 0.05)", "default": 0.05}
                }
            }
        ),
        types.Tool(
            name="synapse_proactive_curation",
            description="Agent 'Curator': Trova e registra link associativi/semantici tra gli atomi di conoscenza.",
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "description": "Numero di atomi da curare in questa sessione (default: 5)", "default": 5}
                }
            }
        ),
        types.Tool(
            name="synapse_self_heal",
            description="Agent 'Instructor': Rileva contraddizioni logiche tra gli atomi della memoria e suggerisce correzioni.",
            inputSchema={"type": "object", "properties": {}}
        ),
        types.Tool(
            name="synapse_scout",
            description="Agent 'Researcher': Scansiona la struttura esterna dei progetti per aggiornare la visione d'insieme.",
            inputSchema={"type": "object", "properties": {}}
        ),
        types.Tool(
            name="synapse_dream",
            description="Agent 'Dreamer': Esegue una passeggiata aleatoria (random walk) tra i ricordi sfruttando lo strato semantico, e distilla nuove idee o associazioni creative usando l'LLM.",
            inputSchema={"type": "object", "properties": {}}
        ),
        types.Tool(
            name="synapse_get_context",
            description="Brain Connector: Recupera un pacchetto completo di ricordi semantici, recenti e pilastri di importanza per generare risposte coerenti.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "L'argomento della conversazione attuale."},
                    "limit": {"type": "integer", "description": "Numero di ricordi semantici da includere (default 3)", "default": 3}
                },
                "required": ["query"]
            }
        ),
        types.Tool(
            name="synapse_toggle_heartbeat",
            description="Attiva o disattiva il battito cardiaco (manutenzione autonoma in background).",
            inputSchema={
                "type": "object",
                "properties": {
                    "enabled": {"type": "boolean", "description": "True per attivare, False per spegnere."}
                },
                "required": ["enabled"]
            }
        ),
        types.Tool(
            name="synapse_set_personality",
            description="Modifica il profilo della memoria per l'oblio e la preservazione dei ricordi.",
            inputSchema={
                "type": "object",
                "properties": {
                    "profile_name": {
                        "type": "string", 
                        "description": "Può essere: 'archivista', 'creativo', 'focus', o 'equilibrato'."
                    }
                },
                "required": ["profile_name"]
            }
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    loop = asyncio.get_event_loop()
    try:
        if name == "synapse_scan":
            target = arguments.get("date") or arguments.get("path")
            result = await loop.run_in_executor(None, run_synapse_scan, target, arguments.get("force", False))
        elif name == "memory_search":
            result = await loop.run_in_executor(None, run_memory_search, arguments["query"], arguments.get("limit", 10), arguments.get("category"))
        elif name == "analyze_python_file":
            p = arguments.get("file_path") or arguments.get("path")
            if not p:
                result = {"error": "Parametro 'file_path' o 'path' mancante"}
            else:
                result = await loop.run_in_executor(None, run_static_analysis, p)
        elif name == "list_memory_files":
            result = await loop.run_in_executor(None, list_memory_files)
        elif name == "find_similar_atoms":
            result = await loop.run_in_executor(None, run_find_similar_atoms, int(arguments["atom_id"]), arguments.get("limit", 5))
        elif name == "distill_weekly":
            result = await loop.run_in_executor(None, run_distill_weekly, int(arguments.get("days", 7)))
        elif name == "web_search_smart":
            result = await loop.run_in_executor(None, run_smart_search, arguments["query"], int(arguments.get("max_retries", 3)))
        elif name == "synapse_proactive_curation":
            result = await loop.run_in_executor(None, run_proactive_curation, int(arguments.get("limit", 5)))
        elif name == "synapse_self_heal":
            result = await loop.run_in_executor(None, run_self_healing)
        elif name == "synapse_scout":
            result = await loop.run_in_executor(None, run_github_scout)
        elif name == "synapse_dream":
            result = await loop.run_in_executor(None, run_dream_sequence)
        elif name == "synapse_get_context":
            result = await loop.run_in_executor(None, run_get_proactive_context, arguments["query"], arguments.get("limit", 3))
        elif name == "synapse_toggle_heartbeat":
            global HEARTBEAT_ENABLED
            HEARTBEAT_ENABLED = arguments.get("enabled", False)
            if HEARTBEAT_ENABLED:
                heartbeat_event.set()
                status_msg = "🧬 Heartbeat Ecosystem: ATTIVATO"
            else:
                heartbeat_event.clear()
                status_msg = "🧬 Heartbeat Ecosystem: STOP (in attesa di segnale)"
            _log(f"⚡ User command: {status_msg}")
            result = {"status": "success", "heartbeat_enabled": HEARTBEAT_ENABLED, "message": status_msg}

        elif name == "synapse_set_personality":
            global CURRENT_PROFILE
            p_name = arguments.get("profile_name", "equilibrato").lower()
            if p_name in MEMORY_PROFILES:
                CURRENT_PROFILE = p_name
                prof = MEMORY_PROFILES[p_name]
                msg = f"🧠 Personalità Cognitiva cambiata in: [{CURRENT_PROFILE.upper()}] - {prof['desc']}"
                _log(msg)
                result = {"status": "success", "profile": CURRENT_PROFILE, "parameters": prof, "message": msg}
            else:
                result = {"status": "error", "message": f"Profilo sconosciuto: {p_name}. Scegli tra: {list(MEMORY_PROFILES.keys())}"}

        elif name == "read_file":
            path = arguments.get("path") or arguments.get("filename")
            if not path:
                result = {"error": "Parametro 'path' o 'filename' obbligatorio."}
            else:
                try:
                    p = Path(path)
                    if p.exists() and p.is_file():
                        result = {"content": p.read_text(encoding='utf-8')}
                    else:
                        result = {"error": f"File non trovato: {path}"}
                except Exception as e:
                    result = {"error": str(e)}

        elif name == "write_file":
            path = arguments.get("path") or arguments.get("filename")
            content = arguments.get("content", "")
            if not path:
                result = {"error": "Parametro 'path' o 'filename' obbligatorio."}
            else:
                try:
                    p = Path(path)
                    p.parent.mkdir(parents=True, exist_ok=True)
                    p.write_text(content, encoding='utf-8')
                    result = {"status": "success", "message": f"File scritto: {path}"}
                except Exception as e:
                    result = {"error": str(e)}

        elif name == "list_files":
            path = arguments.get("path") or arguments.get("filename") or "."
            try:
                p = Path(path)
                if p.exists() and p.is_dir():
                    items = []
                    for item in p.iterdir():
                        type_str = "DIR" if item.is_dir() else "FILE"
                        items.append(f"[{type_str}] {item.name}")
                    result = {"path": str(p.absolute()), "items": sorted(items)}
                else:
                    result = {"error": f"Directory non trovata: {path}"}
            except Exception as e:
                result = {"error": str(e)}

        elif name == "create_folder":
            path = arguments.get("path") or arguments.get("filename")
            if not path:
                result = {"error": "Parametro 'path' o 'filename' obbligatorio."}
            else:
                try:
                    p = Path(path)
                    p.mkdir(parents=True, exist_ok=True)
                    result = {"status": "success", "message": f"Cartella creata: {path}"}
                except Exception as e:
                    result = {"error": str(e)}
        elif name == "synapse_stats":
            result = get_synapse_stats()

        elif name == "synapse_deep_learn":
            iterations = arguments.get("iterations", 5)
            if not LORA_READY or not lora_engine:
                 return [types.TextContent(type="text", text=json.dumps({"status": "error", "message": "Motore neurale non pronto (manca torch o lora_engine.py)."}))]
            
            # 1. Recupera gli ultimi 100 atomi dal DB
            conn = _get_db_connection()
            atoms = conn.execute('SELECT content FROM knowledge_atoms ORDER BY id DESC LIMIT 100').fetchall()
            conn.close()
            
            if not atoms or not SEMANTIC_READY:
                result = {"status": "error", "message": "Nessun atomo o motore semantico assente."}
            else:
                # 2. Training Loop veloce
                texts = [a[0] for a in atoms]
                embeddings = list(embedding_model.embed(texts))
                data_tensor = torch.tensor(embeddings)
                
                # Setup optimizer sui parametri dei modelli dentro lora_engine
                optimizer = torch.optim.Adam(
                    list(lora_engine.model_mem.parameters()) + 
                    list(lora_engine.model_gate.parameters()), 
                    lr=1e-3
                )
                
                lora_engine.model_mem.train()
                lora_engine.model_gate.train()
                
                final_loss = 0.0
                for _ in range(iterations):
                    optimizer.zero_grad()
                    w = lora_engine.model_gate(data_tensor)
                    delta = lora_engine.model_mem(data_tensor, w)
                    # Loss di auto-regolazione: cerca di minimizzare la proiezione ma con gating attivo
                    loss = F.mse_loss(data_tensor + delta, data_tensor) 
                    loss.backward()
                    optimizer.step()
                    final_loss = loss.item()
                
                # 3. Salvataggio
                lora_engine.save_weights(final_loss)
                result = {
                    "status": "success", 
                    "loss": f"{final_loss:.8f}", 
                    "message": f"Pesi neurali aggiornati usando {len(atoms)} atomi."
                }
        elif name == "rescan_all":
            result = await loop.run_in_executor(None, rescan_all, arguments.get("days", 30))
        elif name == "sync_conversations":
            bridge_script = os.path.join(NEBULA_HOME, "scripts", "bridge_lmstudio_memory.py")
            try:
                # Usa asyncio per evitare di bloccare il loop ed evitare timeout
                proc = await asyncio.create_subprocess_exec(
                    sys.executable, bridge_script,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout, stderr = await proc.communicate()
                
                if proc.returncode == 0:
                    # Eseguiamo lo scan e la curatura immediata post-sync
                    sync_res = await loop.run_in_executor(None, startup_autoscan, 1)
                    cur_res = await loop.run_in_executor(None, run_proactive_curation, 10)
                    result = {
                        "status": "success", 
                        "message": "Conversazioni sincronizzate e indicizzate.", 
                        "atoms_added": sync_res.get('total_new_atoms', 0),
                        "links_created": cur_res.get('links_created', 0),
                        "details": stdout.decode()
                    }
                else:
                    result = {"status": "error", "message": f"Errore Bridge (code {proc.returncode}): {stderr.decode()}"}
            except Exception as e:
                result = {"status": "error", "message": str(e)}

        elif name == "synapse_oblivion":
            min_strength = float(arguments.get("min_strength", 0.5))
            decay_rate = float(arguments.get("decay_rate", 0.05))
            result = await loop.run_in_executor(None, run_synapse_oblivion, min_strength, decay_rate)

        else:
            result = {"error": f"Tool sconosciuto: {name}"}
    except Exception as e:
        result = {"error": f"Errore in '{name}': {type(e).__name__}: {str(e)}"}

    return [types.TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]


# ---- Background Heartbeat (Autonomia L3) ----

async def heartbeat_ecosystem():
    """Compito in background che anima l'ecosistema attivando gli agenti periodicamente."""
    _log("💓 Heartbeat: Ecosistema Sinapsi Online. In attesa di segnale di attivazione...")
    
    loop = asyncio.get_event_loop()
    while True:
        try:
            # Attendi il segnale dell'evento (senza consumare CPU nel mentre)
            await heartbeat_event.wait()
            
            if not HEARTBEAT_ENABLED:
                # Caso in cui è stato spento appena prima del set()
                heartbeat_event.clear()
                continue
                
            _log("🧬 Agent Cycle: Avvio routine di manutenzione autonoma...")
            
            # 1. Curator: Collega atomi isolati
            res_c = await loop.run_in_executor(None, run_proactive_curation, 10)
            _log(f"   [Curator] Link creati: {res_c.get('links_created', 0)}")
            
            # 2. Scout: Aggiorna visione progetto
            res_s = await loop.run_in_executor(None, run_github_scout)
            _log(f"   [Scout] Stato: {res_s.get('result', 'error')}")
            
            # 3. Healer & Dreamer: Funzioni Intensive tramite LLM
            if AUTONOMOUS_LLM_ENABLED:
                res_h = await loop.run_in_executor(None, run_self_healing)
                _log(f"   [Healer] Conflitti rilevati: {res_h.get('conflicts_detected', 0)}")
                
                # 4. Dreamer: Modalità Onirica Associativa
                res_d = await loop.run_in_executor(None, run_dream_sequence)
                if res_d.get("status") == "success":
                    insight_str = str(res_d.get('insight', ''))
                    short_insight = insight_str[:80] + "..." if len(insight_str) > 80 else insight_str
                    _log(f"   [Dreamer] Nuova intuizione elaborata: {short_insight}")
                else:
                    _log(f"   [Dreamer] Sogno interrotto: {res_d.get('message', '')}")
            else:
                _log("   [Healer & Dreamer] Saltati (AUTONOMOUS_LLM_ENABLED=False)")
            
            _log("😴 Agent Cycle: Routine completata. Prossima attivazione tra 1 ora o al prossimo toggle.")
            
            # Attende 1 ora O finché HEARTBEAT_ENABLED non viene resettato manualmente
            try:
                # wait_for con timeout simula lo sleep ma può essere interrotto se enabled cambia
                # (anche se qui il comportamento standard basta)
                await asyncio.sleep(3600)
            except asyncio.CancelledError:
                break
            
        except Exception as e:
            _log(f"⚠️ Errore Heartbeat: {e}")
            await asyncio.sleep(600) # Riprova tra 10 minuti in caso di errore


# ---- Entry point ----

async def main():
    # Auto-scan all'avvio — non blocca il server anche se fallisce
    _log("=" * 50)
    _log("The Weaver MCP Server v1.2 - avvio")
    _log("=" * 50)
    try:
        # Sincronizza le chat di LM Studio (Bridge) asincrono
        bridge_script = os.path.join(NEBULA_HOME, "scripts", "bridge_lmstudio_memory.py")
        proc = await asyncio.create_subprocess_exec(
            sys.executable, bridge_script,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL
        )
        await proc.wait() # Attendiamo che finisca prima di fare lo scan
        
        scan_result = startup_autoscan(days=7)
        _log(f"Auto-scan: {scan_result['total_new_atoms']} nuovi atomi da {scan_result['files_processed']} file")
        
        # Avvia Heartbeat in background
        asyncio.create_task(heartbeat_ecosystem())
        
    except Exception as e:
        _log(f"⚠️  Auto-scan/Sync fallito: {e}")

    _log("✅ Server pronto — in ascolto su stdio")

    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="the-weaver",
                server_version="1.2.0",
                capabilities=app.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={}
                )
            )
        )


if __name__ == "__main__":
    asyncio.run(main())
