import os
import json
import sqlite3
from pathlib import Path
from datetime import datetime
import re
import sys

# Configurazione Percorsi
USER_HOME = os.path.expanduser("~")
LM_STUDIO_CONVERSATIONS = Path(USER_HOME) / ".cache" / "lm-studio" / "conversations"
MEMORY_DIR = Path(r"C:\Users\forte\memory")
NEBULA_HOME = Path(r"C:\mcp_projects\tool_nebula")
DATABASE_PATH = NEBULA_HOME / "synapse_index.db"
LOG_DIR = NEBULA_HOME / "logs"

# Assicurati che le cartelle esistano
MEMORY_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)

SYNC_LOG = LOG_DIR / "bridge_sync.log"

def _log(msg: str):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, file=sys.stderr, flush=True)
    with open(SYNC_LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")

def extract_text_from_json(conv_path: Path) -> str:
    """Estrae i messaggi USER e ASSISTANT da un file JSON di LM Studio."""
    try:
        with open(conv_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        messages = data.get('messages', [])
        formatted_content = []
        
        # Nome della conversazione per contesto
        conv_name = data.get('name', 'Conversazione Senza Titolo')
        formatted_content.append(f"### 💬 Conversazione: {conv_name}")
        formatted_content.append(f"ID: {conv_path.stem}\n")

        for msg_record in messages:
            versions = msg_record.get('versions', [])
            if not versions: continue
            
            # Prendi l'ultima versione selezionata o la prima disponibile
            curr_idx = msg_record.get('currentlySelected', 0)
            if curr_idx >= len(versions): curr_idx = 0
            
            msg = versions[curr_idx]
            role = msg.get('role', 'unknown').upper()
            
            # Gestione diversi tipi di step (singleStep o multiStep)
            content_parts = []
            
            # Caso standard (singleStep)
            if 'content' in msg:
                for part in msg['content']:
                    if part.get('type') == 'text':
                        content_parts.append(part.get('text', ''))
            
            # Caso multiStep (con tool calls)
            if 'steps' in msg:
                for step in msg['steps']:
                    if step.get('type') == 'contentBlock':
                        for part in step.get('content', []):
                            if part.get('type') == 'text':
                                content_parts.append(part.get('text', ''))
                            elif part.get('type') == 'toolCallRequest':
                                tool_name = part.get('name')
                                params = json.dumps(part.get('parameters', {}))
                                content_parts.append(f"*[CHIAMATA TOOL: {tool_name} {params}]*")

            text = ' '.join(content_parts).strip()
            if text:
                formatted_content.append(f"**{role}**: {text}\n")
        
        return '\n'.join(formatted_content)
    except Exception as e:
        _log(f"Errore parsing {conv_path.name}: {e}")
        return ""

def sync_conversations():
    """Sincronizza le chat di LM Studio nella memoria Nebula."""
    _log("Inizio sincronizzazione Bridge LM Studio -> Sinapsi...")
    
    if not LM_STUDIO_CONVERSATIONS.exists():
        _log(f"Directory conversazioni non trovata: {LM_STUDIO_CONVERSATIONS}")
        return
    
    # Carica ID già processati (per non duplicare file .md inutilmente)
    processed_ids = set()
    sync_metadata_file = LOG_DIR / "processed_conversations.json"
    if sync_metadata_file.exists():
        try:
            with open(sync_metadata_file, 'r') as f:
                processed_ids = set(json.load(f))
        except: pass

    new_chats = 0
    today_str = datetime.now().strftime("%Y-%m-%d")
    sync_file = MEMORY_DIR / f"CHATS_SYNC_{today_str}.md"
    
    # Trova file .json ordinati per data creazione
    chat_files = sorted(LM_STUDIO_CONVERSATIONS.glob("*.conversation.json"), key=os.path.getmtime, reverse=True)
    
    # Processiamo solo le chat modificate nelle ultime 24 ore o le ultime 5
    to_process = []
    for cf in chat_files[:10]: # Limite ragionevole per sessione
        if cf.stem not in processed_ids:
            to_process.append(cf)
    
    if not to_process:
        _log("Nessuna nuova chat da sincronizzare.")
        return 0

    with open(sync_file, 'a', encoding='utf-8') as f:
        f.write(f"\n# 🔄 Sync Session: {datetime.now().strftime('%H:%M:%S')}\n")
        for cf in to_process:
            text = extract_text_from_json(cf)
            if text:
                f.write("\n---\n")
                f.write(text)
                processed_ids.add(cf.stem)
                new_chats += 1
                _log(f"Sincronizzata chat: {cf.name}")

    # Salva nuovi ID processati
    with open(sync_metadata_file, 'w') as f:
        json.dump(list(processed_ids), f)
        
    _log(f"Fine sync. {new_chats} chat aggiunte a {sync_file.name}")
    return new_chats

if __name__ == "__main__":
    sync_conversations()
