# Tool Nebula - Autonomous Development Environment

> **Versione:** 1.1 | **Aggiornato:** 2026-03-19 | **Agent:** Autonomous Development System

---

## ⚠️ REGOLA CRITICA — LEGGERE PRIMA DI TUTTO ⚠️

> **Questo progetto espone strumenti a LM Studio tramite il protocollo MCP.**
> **Qualsiasi file `.py` usato come entry point MCP DEVE essere un MCP Server, NON uno script CLI.**

### ❌ ERRORE COMUNE (da NON fare)

```python
# SBAGLIATO — script CLI che esegue e termina subito
def main():
    run_something()
    print("Done")  # Il processo termina → LM Studio vede "Connection closed"

if __name__ == "__main__":
    main()
```

Quando LM Studio avvia un MCP server e il processo termina immediatamente,
genera questo errore nel log:

```
MCP error -32000: Connection closed
```

**Causa:** LM Studio si aspetta un processo che rimane attivo e parla il
protocollo JSON-RPC 2.0 via stdio. Se il processo termina, la connessione
si chiude e nessuno strumento viene caricato.

---

### ✅ STRUTTURA CORRETTA di un MCP Server

Ogni entry point MCP in questo progetto deve seguire questa struttura:

```python
import asyncio
import json
import mcp.server.stdio
import mcp.types as types
from mcp.server import Server, NotificationOptions
from mcp.server.models import InitializationOptions

# 1. Crea l'istanza del server con un nome univoco
app = Server("nome-del-server")

# 2. Definisci la lista degli strumenti disponibili
@app.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="nome_strumento",
            description="Cosa fa questo strumento",
            inputSchema={
                "type": "object",
                "properties": {
                    "parametro": {
                        "type": "string",
                        "description": "Descrizione del parametro"
                    }
                },
                "required": ["parametro"]
            }
        ),
    ]

# 3. Gestisci le chiamate agli strumenti
@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    if name == "nome_strumento":
        result = {"output": f"Ricevuto: {arguments['parametro']}"}
    else:
        result = {"error": f"Tool sconosciuto: {name}"}

    return [types.TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]

# 4. Avvia il server — questo blocca il processo e lo tiene in ascolto su stdio
async def main():
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="nome-del-server",
                server_version="1.0.0",
                capabilities=app.get_capabilities(
                    notification_options=NotificationOptions(),  # MAI None — causa AttributeError!
                    experimental_capabilities={}
                )
            )
        )

if __name__ == "__main__":
    asyncio.run(main())
```

### Punti chiave da ricordare

| Regola | Dettaglio |
|--------|-----------|
| **Il processo NON deve terminare** | `stdio_server()` blocca il processo indefinitamente — questo è corretto |
| **Comunicazione solo su stdio** | Non usare `print()` per output dati, solo `sys.stderr` per log |
| **Ogni strumento ha uno schema JSON** | `inputSchema` definisce parametri obbligatori e opzionali |
| **Risposta sempre come TextContent** | Restituire sempre `list[types.TextContent]` dalla `call_tool` |
| **Gestire le eccezioni** | Wrappare sempre `call_tool` in try/except per evitare crash |

---

## Configurazione LM Studio (`mcp.json`)

L'entry point per questo progetto è:

```json
"the-weaver": {
  "command": "python",
  "args": ["C:/mcp_projects/tool_nebula/tools/synapse_runner.py"],
  "env": {
    "PYTHONPATH": "C:/mcp_projects/tool_nebula"
  }
}
```

`PYTHONPATH` punta alla **root del progetto** (`tool_nebula/`) in modo che
gli import da `core/` e `tools/` funzionino correttamente.

---

## Struttura del Progetto

```
C:\mcp_projects\tool_nebula\
├── tools\
│   ├── synapse_runner.py            ← ENTRY POINT MCP (the-weaver server)
│   ├── synapse_index.py             ← Modulo di indicizzazione SQLite
│   └── static_analyzer_refactorer\ ← Tool di analisi statica Python
│       ├── __init__.py
│       └── main.py
├── core\
│   ├── analyzer.py                  ← Engine analisi statica
│   ├── refactorer.py                ← Engine refactoring
│   ├── memory_compressor.py         ← Compressione memoria conversazioni
│   └── autonomous_agent_rules.md   ← Regole comportamentali agente
├── config\
│   └── analyzer_rules.json          ← Regole di analisi configurabili
├── skills\                          ← Pattern appresi
├── templates\                       ← Template per nuovi tool
├── tests\                           ← Test cases
├── logs\                            ← Log di esecuzione (auto-generati)
│   ├── synapse_runner.log
│   └── synapse_execution_log.json
├── synapse_index.db                 ← Database SQLite Sinapsi (auto-generato)
└── README.md                        ← Questo file
```

---

## Strumenti Esposti dal Server MCP

Il file `tools/synapse_runner.py` espone i seguenti strumenti a LM Studio:

### `synapse_scan`
Scansiona il file memoria giornaliero (`.md`) e indicizza gli atomi di
conoscenza nel database SQLite Sinapsi.

```json
{ "date": "2026-03-19" }  // opzionale, default: oggi
```

### `memory_search`
Cerca testo negli atomi di conoscenza indicizzati.

```json
{ "query": "python", "limit": 10 }
```

### `analyze_python_file`
Analisi statica di un file Python con le regole configurate in `config/`.

```json
{ "file_path": "C:/percorso/al/file.py" }
```

### `list_memory_files`
Elenca i file `.md` presenti in `C:\Users\forte\memory`.

```json
{}
```

### `synapse_stats`
Statistiche del database Sinapsi (atomi totali, categorie, fonti).

```json
{}
```

---

## Come Aggiungere un Nuovo Strumento

Per aggiungere uno strumento al server MCP **senza rompere nulla**:

1. **Scrivi la funzione helper** (sincrona) in `synapse_runner.py`:
   ```python
   def mio_nuovo_strumento(param: str) -> dict:
       # Logica qui
       return {"result": "..."}
   ```

2. **Aggiungi il Tool alla lista** nel decoratore `@app.list_tools()`:
   ```python
   types.Tool(
       name="mio_nuovo_strumento",
       description="Descrizione chiara",
       inputSchema={"type": "object", "properties": {"param": {"type": "string"}}, "required": ["param"]}
   )
   ```

3. **Gestisci la chiamata** nel decoratore `@app.call_tool()`:
   ```python
   elif name == "mio_nuovo_strumento":
       result = mio_nuovo_strumento(arguments["param"])
   ```

4. **Riavvia** il plugin in LM Studio (non serve riavviare tutta l'app).

---

## Dipendenze

```
mcp          # Model Context Protocol SDK (già installato)
sqlite3      # Built-in Python
ast          # Built-in Python
json         # Built-in Python
```

Verifica installazione `mcp`:
```powershell
python -c "import mcp; print('mcp OK')"
```

---

## Debug e Troubleshooting

### "Connection closed" in LM Studio
→ Il processo MCP termina immediatamente. Verificare che `synapse_runner.py`
  usi `async with mcp.server.stdio.stdio_server()` e NON termini in `main()`.

### Il server non trova i moduli
→ Verificare che `PYTHONPATH` in `mcp.json` punti a `C:/mcp_projects/tool_nebula`
  (la root, non la sottocartella `tools/`).

### Errori silenziosi (nessun log)
→ Controllare `logs/synapse_runner.log`. Ogni scrittura su `sys.stderr`
  appare nei log di LM Studio sotto `[Plugin(mcp/the-weaver)] stderr:`.

---

*Maintainer: Tool Nebula Autonomous System + Human Oversight*