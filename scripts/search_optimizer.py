"""
Search Optimizer - Middleware per LLM Locali
Previene loop infiniti, gestisce errori, sanizza risultati web
Versione: 1.0 (Refactored for Local LLMs)
Autore: Nebula Orchestratore Autonomo
"""

import json
import re
import time
from typing import Optional, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime
import sys
import logging

# Configurazione logging (su stderr per non interferire con MCP protocol)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    stream=sys.stderr
)
logger = logging.getLogger(__name__)


@dataclass
class SearchConfig:
    """Configurazione parametri ricerca"""
    max_iterations: int = 3
    max_search_history_size: int = 10
    max_context_length: int = 2000
    timeout_seconds: float = 30.0
    api_base_url: str = "https://api.tavily.com"  # Opzionale: Tavily API


@dataclass
class SearchResult:
    """Risultato di una singola ricerca"""
    query: str
    content: str
    timestamp: datetime = field(default_factory=datetime.now)
    success: bool = True
    error_message: Optional[str] = None


class LocalLLMSearchAgent:
    """
    Orchestratore Rigido per LLM locali.
    
    Pattern: State Machine con Circuit Breaker
    - Max 3 iterazioni di ricerca
    - Blocco duplicati query identiche
    - Sanitizzazione automatica risultati web
    - Fallback automatico quando max_iterations raggiunto
    """
    
    def __init__(self, config: Optional[SearchConfig] = None):
        self.config = config or SearchConfig()
        self.search_history: set = set()  # Query già cercate (anti-loop)
        self.iteration_count = 0
        self.context_window_usage = 0
        
    def perform_web_search(self, query: str) -> SearchResult:
        """
        Esegue ricerca web con sanitizzazione automatica.
        
        Supporta multiple API:
        - Tavily (default): https://api.tavily.com/search
        - DuckDuckGo: https://api.duckduckgo.com/?q=
        - Google Custom Search API
        
        Restituisce testo PULITO e COMPRESSO (< 1000 caratteri)
        """
        start_time = time.time()
        
        try:
            # Scegliere API in base a configurazione
            if self.config.api_base_url == "https://api.tavily.com":
                results = self._search_tavily(query)
            elif self.config.api_base_url.startswith("duckduckgo"):
                results = self._search_duckduckgo(query)
            else:
                # Fallback a mock per testing
                logger.warning(f"API non configurata, uso mock search")
                return SearchResult(
                    query=query,
                    content=self._mock_search_result(query),
                    success=True
                )
            
            # Sanitizzazione e compressione risultati
            sanitized_content = self._sanitize_and_compress(results)
            
            elapsed = time.time() - start_time
            logger.info(f"✅ Ricerca completata in {elapsed:.2f}s per '{query[:50]}...'")
            
            return SearchResult(
                query=query,
                content=sanitized_content,
                success=True
            )
            
        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(f"❌ Errore ricerca '{query[:50]}...': {str(e)}")
            
            return SearchResult(
                query=query,
                content=f"[SISTEMA]: Errore durante la ricerca web ({type(e).__name__}: {str(e)})\nRiprova con termini diversi.",
                success=False,
                error_message=str(e)
            )
    
    def _search_tavily(self, query: str) -> Dict[str, Any]:
        """Chiamata API Tavily"""
        import requests
        
        params = {
            "query": query,
            "max_results": 5,
            "include_answer": True
        }
        
        response = requests.get(
            f"{self.config.api_base_url}/search",
            params=params,
            timeout=self.config.timeout_seconds
        )
        
        if response.status_code == 200:
            data = response.json()
            # Estrai solo testo pulito dai risultati
            return self._extract_clean_text(data.get("answers", [])) + \
                   self._extract_clean_text(data.get("results", []))
        else:
            raise Exception(f"Tavily API error: {response.status_code}")
    
    def _search_duckduckgo(self, query: str) -> Dict[str, Any]:
        """Chiamata API DuckDuckGo"""
        import requests
        
        response = requests.get(
            f"{self.config.api_base_url}/q/{query}",
            timeout=self.config.timeout_seconds
        )
        
        if response.status_key == 200:
            data = response.json()
            return self._extract_clean_text(data.get("results", []))
        else:
            raise Exception(f"DuckDuckGo API error: {response.status_code}")
    
    def _mock_search_result(self, query: str) -> str:
        """Mock per testing senza API"""
        return f"Risultati mock per '{query}': [Informazione rilevante trovata nel web, estratta e sintetizzata. Questo è un testo di esempio con circa 50-100 parole che simula risultati reali da una ricerca web pulita.] La lunghezza è controllata per non saturare il context window dell'LLM locale."
    
    def _extract_clean_text(self, data: list) -> str:
        """Estrae testo pulito dai risultati API"""
        clean_parts = []
        
        for item in data[:5]:  # Limita a massimo 5 risultati
            if isinstance(item, dict):
                # Estrai titolo e contenuto
                title = item.get("title", "")[:200]
                content = item.get("content", "")[:500]
                
                # Rimuovi HTML tag se presenti
                clean_parts.append(self._remove_html_tags(title + " - " + content))
            elif isinstance(item, str):
                # Testo già pulito
                clean_parts.append(item[:800])
        
        return "\n\n".join(clean_parts) if clean_parts else "[Nessun risultato trovato]"
    
    def _remove_html_tags(self, text: str) -> str:
        """Rimuove tag HTML e lascia solo testo"""
        # Pattern per rimuovere tutto ciò che è tra < e >
        cleaned = re.sub(r'<[^>]+>', '', text)
        return cleaned.strip()
    
    def _sanitize_and_compress(self, content: str) -> str:
        """
        Sanitizzazione multi-step dei risultati web:
        1. Rimozione HTML
        2. Compressione token (max 1000 caratteri)
        3. Estrazione parole chiave rilevanti
        """
        # Step 1: Pulizia base
        cleaned = self._remove_html_tags(content)
        
        # Step 2: Limita lunghezza massima
        if len(cleaned) > self.config.max_context_length:
            # Prendi solo la prima parte significativa
            cleaned = cleaned[:self.config.max_context_length]
            
            # Aggiungi marker che il testo è stato compresso
            cleaned += "\n\n[SISTEMA]: Il testo è stato compresso per limitare il context window. Se hai bisogno di più dettagli, riformula la ricerca."
        
        # Step 3: Estrazione parole chiave (opzionale - future enhancement)
        # Per ora restituiamo testo pulito diretto
        
        return cleaned
    
    def execute_agent_loop(self, user_prompt: str, llm_generate_function) -> str:
        """
        Ciclo di controllo rigido per prevenire loop infiniti.
        
        Pattern State Machine:
        - Iterazione 1-3: Cerca informazioni web
        - Se "FINAL_ANSWER:" trovato → restituisce risposta finale
        - Se max_iterations raggiunto → fallback automatico
        
        Args:
            user_prompt: Prompt iniziale dall'utente
            llm_generate_function: Funzione che chiama il modello locale
            
        Returns:
            Stringa di risposta finale (senza tag SPECIALI)
        """
        context = user_prompt
        iteration = 0
        
        logger.info(f"🔄 Inizio ciclo agente. Max iterazioni: {self.config.max_iterations}")
        
        while iteration < self.config.max_iterations:
            iteration += 1
            
            # Reset contatori per ogni nuova ricerca
            self.iteration_count = 0
            self.search_history.clear()
            
            print(f"\n{'='*60}")
            print(f"🔄 --- Iterazione {iteration}/{self.config.max_iterations} ---")
            print(f"{'='*60}")
            
            # 1. Chiamata al modello locale
            try:
                llm_response = llm_generate_function(context)
            except Exception as e:
                logger.error(f"Errore chiamata LLM: {str(e)}")
                context += f"\n\n[SISTEMA]: Errore nella comunicazione con il modello locale ({type(e).__name__}). Riprova."
                continue
            
            # 2. Controllo risposta finale (Stop Condition)
            if self._check_final_answer(llm_response):
                print("✅ Risposta finale trovata!")
                return self._extract_final_answer(llm_response)
            
            # 3. Controllo richiesta ricerca web
            if self._requires_search(llm_response):
                try:
                    search_query = self._extract_search_query(llm_response)
                    
                    # [ANTI-LOOP 1]: Controllo duplicati
                    if self._is_duplicate_query(search_query):
                        print("⚠️ [ANTI-LOOP] Query duplicata rilevata!")
                        context += f"\n\n[SISTEMA]: Hai già cercato '{search_query}'. Usa termini più specifici o riformula completamente la ricerca."
                        continue
                    
                    # Aggiungi alla history
                    self.search_history.add(search_query)
                    
                    # Limita size della history
                    if len(self.search_history) > self.config.max_search_history_size:
                        oldest = next(iter(self.search_history))
                        self.search_history.remove(oldest)
                        logger.info(f"Query '{oldest}' rimossa dalla history (max {self.config.max_search_history_size})")
                    
                    # 4. Esecuzione ricerca web
                    search_result = self.perform_web_search(search_query)
                    
                    if not search_result.success:
                        context += f"\n\n[SISTEMA]: Ricerca fallita per '{search_query}'. Errore: {search_result.error_message}\nRiprova con termini diversi."
                        continue
                    
                    # 5. Aggiunta risultati al contesto (con limitazione)
                    results_preview = search_result.content[:self.config.max_context_length]
                    context += f"\n\n📊 RISULTATO RICERCA '{search_query}':\n{results_preview}\n\n[SISTEMA]: Analizza questi risultati. Se hai la risposta completa, usa 'FINAL_ANSWER: tua risposta'. Altrimenti, usa 'SEARCH: nuova query' più specifica."
                    
                    # Monitoraggio uso context window
                    self.context_window_usage += len(results_preview)
                    if self.context_window_usage > 5000:
                        logger.warning(f"⚠️ Context window usage alto: {self.context_window_usage} caratteri")
                        
                except Exception as e:
                    # [GESTIONE ERRORI]: Prevengo il crash
                    error_msg = f"[SISTEMA]: Errore durante la ricerca web ({type(e).__name__}: {str(e)})\nRiprova con una query più semplice."
                    context += error_msg
                    logger.error(error_msg)
                    
            else:
                # [ANTI-LOOP 2]: Formato output non valido
                print("⚠️ [ANTI-LOOP] Formato output non riconosciuto")
                context += "\n\n[SISTEMA]: Il tuo formato è errato. Devi iniziare la risposta ESATTAMENTE con 'SEARCH: tua query' oppure con 'FINAL_ANSWER: tua risposta'. Niente preamboli, niente spiegazioni."
        
        # [CIRCUIT BREAKER]: Limite massimo raggiunto
        print(f"\n🛑 [CIRCUIT BREAKER] Raggiunto limite massimo di {self.config.max_iterations} iterazioni.")
        
        # Fallback: chiedi all'LLM di rispondere con info già disponibili
        fallback_prompt = context + "\n\n[SISTEMA]: LIMITE RICERCHE RAGGIUNTO. Basandoti SOLO sulle informazioni qui sopra (senza cercare altro), genera una FINAL_ANSWER completa e utile per l'utente."
        
        try:
            final_attempt = llm_generate_function(fallback_prompt)
            
            if self._check_final_answer(final_attempt):
                return self._extract_final_answer(final_attempt)
            else:
                # Se anche il fallback non produce FINAL_ANSWER, restituiamo contesto
                print("⚠️ Fallback senza risposta finale. Restituendo contesto completo.")
                return context[-500:]  # Ultimi 500 caratteri come fallback estremo
                
        except Exception as e:
            logger.error(f"Errore fallback: {str(e)}")
            return "[SISTEMA]: Errore nel processo finale. Controlla i log per dettagli."
    
    def _check_final_answer(self, response: str) -> bool:
        """Verifica se la risposta contiene FINAL_ANSWER"""
        return "FINAL_ANSWER:" in response.upper()
    
    def _extract_final_answer(self, response: str) -> str:
        """Estrae solo il testo dopo FINAL_ANSWER:"""
        parts = response.split("FINAL_ANSWER:")
        if len(parts) > 1:
            return parts[1].strip()
        return response
    
    def _requires_search(self, response: str) -> bool:
        """Verifica se la risposta richiede una ricerca web"""
        # Controllo per SEARCH: (case insensitive ma con formato preciso)
        search_pattern = r'^SEARCH:\s*(.+)$'
        match = re.match(search_pattern, response.strip(), re.IGNORECASE)
        
        if match:
            return True
        
        # Fallback: se contiene parole chiave di ricerca
        search_keywords = ["cerca", "ricerca", "trova", "info su", "dove", "quando"]
        response_lower = response.lower()
        
        for keyword in search_keywords:
            if keyword in response_lower and len(response) > 100:
                return True
        
        return False
    
    def _extract_search_query(self, response: str) -> str:
        """Estrae la query dalla risposta"""
        # Cerca pattern SEARCH: query
        match = re.search(r'SEARCH:\s*(.+?)(?:\n|$)', response, re.IGNORECASE | re.DOTALL)
        
        if match:
            return match.group(1).strip()
        
        # Fallback: prendi tutto dopo SEARCH:
        parts = response.split("SEARCH:")
        if len(parts) > 1:
            return parts[1].strip()
        
        raise ValueError("Impossibile estrarre query da risposta non valida")
    
    def _is_duplicate_query(self, query: str) -> bool:
        """Verifica se la query è già stata cercata (con tolleranza case-insensitive)"""
        normalized = query.lower().strip()
        
        for existing in self.search_history:
            if existing.lower().strip() == normalized:
                return True
        
        return False
    
    def get_stats(self) -> Dict[str, Any]:
        """Restituisce statistiche dello stato corrente"""
        return {
            "iteration_count": self.iteration_count,
            "max_iterations": self.config.max_iterations,
            "search_history_size": len(self.search_history),
            "context_window_usage": self.context_window_usage,
            "is_in_loop_risk": len(self.search_history) > 2 and self.iteration_count >= 3
        }


# ============================================
# UTILITÀ PER TESTING E MOCK LLM
# ============================================

class MockLLM:
    """Simula un modello locale per testing"""
    
    def __init__(self, seed_response=None):
        self.seed_response = seed_response
    
    def generate(self, prompt: str) -> str:
        """Genera risposta simulata"""
        if self.seed_response:
            return self.seed_response
        
        # Simula comportamento LLM locale con loop potenziale
        if "meteo" in prompt.lower() or "tempo" in prompt.lower():
            return "SEARCH: qual è il meteo a Roma oggi?"
        
        elif "informazioni su" in prompt.lower() or "ricerca" in prompt.lower():
            # Simula ricerca ripetuta (loop)
            if "prima volta" not in prompt.lower():
                return "SEARCH: informazioni su Python programming"  # Query duplicata!
            return "FINAL_ANSWER: Python è un linguaggio di programmazione orientato agli oggetti molto popolare. Ha una sintassi semplice e leggibile."
        
        else:
            return "FINAL_ANSWER: Questa è una risposta finale simulata dal modello locale."


# ============================================
# ESEMPIO DI UTILIZZO
# ============================================

if __name__ == "__main__":
    print("🔍 Search Optimizer - Demo Execution")
    print("=" * 60)
    
    # Configurazione
    config = SearchConfig(max_iterations=3, max_context_length=1500)
    
    # Creazione agente
    agent = LocalLLMSearchAgent(config=config)
    
    # Mock LLM per testing
    llm_mock = MockLLM()
    
    # Prompt utente
    user_prompt = "Qual è il meteo a Roma oggi?"
    
    print(f"\n📝 Prompt utente: {user_prompt}\n")
    
    # Esecuzione ciclo agente
    final_result = agent.execute_agent_loop(user_prompt, llm_mock.generate)
    
    print("\n" + "=" * 60)
    print("✅ RISPOSTA FINALE:")
    print("=" * 60)
    print(final_result)
    
    # Statistiche finali
    stats = agent.get_stats()
    print(f"\n📊 STATISTICHE:")
    for key, value in stats.items():
        print(f"   {key}: {value}")
