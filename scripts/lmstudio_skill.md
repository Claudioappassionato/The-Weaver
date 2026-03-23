# ⚙️ SKILL: LM STUDIO AUTOMATION ROUTINE
**Nome:** `execute_lmstudio_skill`  
**Descrizione:** Esegue routine di manutenzione automatica del sistema Sinapsi (pulizia, distillazione, heartbeat).  
**Trigger Utente:** "Esegui la Skill LmStudio"

---

## 🔄 FASI DA ESEGUIRE (Pipeline Obbligatoria)
Quando attivata, l'agente deve eseguire le seguenti operazioni in sequenza esatta:

### 1. Heartbeat Check & Health Scan
*   **Scopo:** Verifica lo stato del database e sincronizza i log recenti per garantire che il sistema sia "sano".
*   **Comando da Esecutare:** `synapse_stats`
*   **Parametri:** Nessuno (default).
*   **Verifica:** Confermare che il numero di atomi non sia anomalo.

### 2. Oblio Selettivo (Pulizia Notturna)
*   **Scopo:** Rimuovere gli atomi deboli o obsoleti per mantenere il database leggero e prevenire l'accumulo di dati inutili.
*   **Comando da Esecutare:** `synapse_oblivion`
*   **Parametri:**
    *   `min_strength`: 0.3 (soglia minima per la sopravvivenza dell'atomo).
    *   `decay_rate`: 0.05 (velocità di decadimento giornaliero).

### 3. Distillazione Settimanale
*   **Scopo:** Analizzare i log degli ultimi 7 giorni e generare un riassunto semantico per aggiornare la conoscenza di alto livello (`MEMORY_WEEKLY.md`).
*   **Comando da Esecutare:** `distill_weekly`
*   **Parametri:**
    *   `days`: 7

### 4. Curatura Proattiva (Collegamenti Sinaptici)
*   **Scopo:** Trovare e creare link automatici tra concetti simili per densificare il grafo di conoscenza e migliorare la reattività futura.
*   **Comando da Esecutare:** `synapse_proactive_curation`
*   **Parametri:**
    *   `limit`: 5 (numero massimo di nuovi link da creare in questa sessione).

### 5. Report Finale & Verifica Stato Post-Routine
*   **Scopo:** Confermare il completamento delle operazioni e mostrare lo stato aggiornato del database all'utente.
*   **Comando da Esecutare:** `synapse_stats` (nuova chiamata per confrontare prima/dopo).
*   **Output Richiesto:** Un riassunto testuale che indichi:
    *   Se la pulizia è stata eseguita con successo.
    *   Se il riassunto settimanale è stato generato.
    *   Quanti link sono stati creati dalla curatura.

---

## 🛠️ REQUISITI TECNICI PER L'ESECUZIONE
1.  **Ordine:** Le fasi devono essere eseguite rigorosamente nell'ordine indicato (da 1 a 5).
2.  **Gestione Errori:** Se un comando fallisce, l'agente deve segnare l'errore nel log ma continuare con la fase successiva (salvataggio in fallback), a meno che non sia critico per il sistema.
3.  **Logging:** Tutte le operazioni devono essere registrate nel file `C:\mcp_projects\tool_nebula\logs\skill_log.md` con timestamp e risultato (successo/errore).

---

## 📋 PROMPT DI ATTIVAZIONE PER L'AGENTE
Quando l'utente invia il comando **"Esegui la Skill LmStudio"**, l'agente deve:
1.  Leggere questo file (`lmstudio_skill.md`).
2.  Esecuire i comandi in ordine numerico.
3.  Restituire un report finale all'utente basato sui risultati della Fase 5.
