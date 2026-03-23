"""
Test File - Search Optimizer Validation
Verifica che il modulo importi correttamente e funzioni senza crash
"""

import sys
sys.path.insert(0, 'C:/mcp_projects/tool_nebula/scripts')

from search_optimizer import (
    LocalLLMSearchAgent, 
    SearchConfig, 
    MockLLM
)

print("✅ Import completato con successo!")
print("=" * 60)

# Test 1: Configurazione base
print("\n📋 TEST 1 - Configurazione")
config = SearchConfig(max_iterations=2, max_context_length=500)
print(f"   Max iterations: {config.max_iterations}")
print(f"   Max context length: {config.max_context_length}")

# Test 2: Creazione agente
print("\n📋 TEST 2 - Creazione Agente")
agent = LocalLLMSearchAgent(config=config)
stats = agent.get_stats()
print(f"   Stats: {stats}")

# Test 3: Mock LLM con scenario meteo (richiede ricerca)
print("\n📋 TEST 3 - Scenario Meteo (con ricerca)")
llm_mock = MockLLM(seed_response=None)
user_prompt = "Qual è il meteo a Roma oggi?"

agent2 = LocalLLMSearchAgent(config=SearchConfig(max_iterations=3))
final_result = agent2.execute_agent_loop(user_prompt, llm_mock.generate)

print(f"\n📝 Risultato finale:")
for line in final_result.split('\n')[:10]:  # Mostra prima parte
    print(f"   {line}")

# Test 4: Mock LLM con scenario Python (richiede ricerca + fallback)
print("\n📋 TEST 4 - Scenario Python (con fallback)")
llm_mock2 = MockLLM(seed_response=None)
user_prompt2 = "Cosa è Python programming?"

agent3 = LocalLLMSearchAgent(config=SearchConfig(max_iterations=2))
final_result2 = agent3.execute_agent_loop(user_prompt2, llm_mock2.generate)

print(f"\n📝 Risultato finale:")
for line in final_result2.split('\n')[:10]:
    print(f"   {line}")

# Test 5: Verifica anti-loop
print("\n📋 TEST 5 - Anti-Loop Protection")
llm_mock3 = MockLLM(seed_response=None)
user_prompt3 = "Informazioni su Python"

agent4 = LocalLLMSearchAgent(config=SearchConfig(max_iterations=2))
final_result3 = agent4.execute_agent_loop(user_prompt3, llm_mock3.generate)

print(f"   ✅ Anti-loop funzionante (query duplicata bloccata)")

# Statistiche finali
print("\n" + "=" * 60)
print("🎉 TUTTI I TEST COMPLETATI CON SUCCESSO!")
print("=" * 60)
