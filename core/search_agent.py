"""
Search Agent Module - The Weaver Core
Implementa la logica di ricerca controllata (Circuit Breaker) e sanitizzazione web.
"""

import os
import re
import requests
import json
import sqlite3
from datetime import datetime
from bs4 import BeautifulSoup
from typing import List, Dict, Any

class LocalLLMSearchAgent:
    def __init__(self, max_retries: int = 3, max_chars: int = 4000):
        self.max_retries = max_retries
        self.max_chars = max_chars
        self.current_retry = 0
        self.history = []

    def sanitize_html(self, html_content: str) -> str:
        """Pulisce l'HTML per estrarre solo il testo utile (Ottimizzato)."""
        # Se non sembra HTML (niente tag), rispondi direttamente per velocità
        if "<" not in html_content and ">" not in html_content:
            return html_content[:self.max_chars]

        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            for s in soup(["script", "style", "header", "footer", "nav"]):
                s.decompose()

            text = soup.get_text(separator=' ')
            clean_text = ' '.join(text.split())
            
            if len(clean_text) > self.max_chars:
                return clean_text[:self.max_chars] + "... [Troncato]"
            return clean_text
        except Exception:
            return html_content[:self.max_chars]

    def execute_web_query(self, query: str) -> Dict[str, Any]:
        """Esegue una query web REALE via DuckDuckGo Search (Ottimizzata)."""
        from duckduckgo_search import DDGS
        results = []
        try:
            # Timeout 20s per evitare WebSocket closed in LM Studio
            with DDGS(timeout=20) as ddgs:
                # Limitiamo i risultati per velocità
                ddg_gen = ddgs.text(query, region='wt-wt', safesearch='moderate', max_results=4)
                for r in ddg_gen:
                    results.append(f"TITOLO: {r['title']}\nSNIPPET: {r['body']}\nURL: {r['href']}\n")
            
            if not results:
                return {"status": "error", "message": "Nessun risultato trovato."}

            return {
                "status": "success",
                "query": query,
                "data": "\n" + "-"*30 + "\n".join(results)
            }
        except Exception as e:
            return {"status": "error", "message": f"DDG Error: {str(e)}"}

    def check_circuit_breaker(self) -> bool:
        """Verifica se abbiamo superato il limite di loop di ricerca."""
        self.current_retry += 1
        if self.current_retry >= self.max_retries:
            return False
        return True

    def format_for_llm(self, data: str) -> str:
        """Formatta i dati puliti per essere iniettati nel prompt dell'LLM."""
        return f"\n[DATI WEB PULITI - TENTATIVO {self.current_retry}/{self.max_retries}]:\n{data}\n"

# Esempio di utilizzo (per testing interno)
if __name__ == "__main__":
    agent = LocalLLMSearchAgent()
    test_html = "<html><head><style>body {color:red;}</style></head><body><h1>Titolo</h1><p>Testo importante.</p><script>alert('spam');</script></body></html>"
    print("Test Sanitizzazione:")
    print(agent.sanitize_html(test_html))
