# 🧠 The Weaver: Autonomous Neuro-Memory for LM Studio (v1.3)

An autonomous cognitive ecosystem (MCP Server) designed for local AI. It is capable of vector-distilling conversational logs, organically forgetting obsolete information through a bio-inspired decay model (Ebbinghaus), dreaming (Associative Random Walk), and self-healing internal conflicts using a custom LoRA Engine.

Tailor-made for advanced models (e.g., Qwen, Llama3, DeepSeek) loaded on **LM Studio**, preserving total local processing and zero latency costs.

---

## 🌟 Core Architectural Features

### 1. 🧬 LIGM Engine v3 (Neural Active Memory via LoRA)
Not just a simple database or a basic RAG retriever. This experimental module (developed in pure `PyTorch`, see `core/lora_engine.py`) allows the system to "internalize" patterns from algorithmic vectors. The user's long-term preferences dynamically deform a custom *gate* layer. Whenever you introduce new Knowledge Atoms, you can trigger the `synapse_deep_learn` tool to converge the neural weights according to what you've taught it, creating true psychological adherence to your workflow.

### 2. 🔬 Hybrid Vectorization (`sqlite-vec` + `fastembed`)
The system uses an extremely lightweight and high-performance model (384-dim: `paraphrase-multilingual-MiniLM-L12-v2`) to calculate embeddings on the fly (highly CPU friendly). No complex dependencies like Milvus or ChromaDB. The innovative integration of `sqlite-vec` with SQLite allows fluid asynchronous transactions on a WAL (Write-Ahead Logging) database. Queries remain lightning-fast even when the LLM engine is saturated.

### 3. 🌙 Dream Mode & Tension Nodes (New in v1.3)
Leveraging implicit clustering based on vector proximity, the new Dream Phase (Dreamer Agent in `synapse_runner.py`) allows the system to execute a background *Random Walk* through the embeddings of various distant but weakly associated Atoms. The local LLM acts as the subconscious and distills "Dream Insights", extracting unexpected creative associations.
If the Healer Agent notices logical contradictions between atoms, it doesn't mechanically overwrite them: it establishes a "Tension Node". When you query the AI on the affected topic, it will proactively warn you (`⚠️ Tension detected`), transforming a potential conflict into a creative spark.

### 4. 🫀 Event-Driven Heartbeat 
Does maintaining an autonomous local server consume too much CPU? Not anymore.
The background ecosystem utilizes `asyncio.Event`. As long as the Heartbeat is kept in *sleep* by the user, The Weaver consumes "Zero Tick" CPU. With a quick trigger from the frontend or through an MCP tool (`synapse_toggle_heartbeat`), you unlock the loop and trigger the cycle of self-correction, dream distillation, and decay of the working memory (ideal before shutting down the workstation).

### 5. 🎭 Organic Oblivion: Ebbinghaus Fallback
In neuroscience, human memory doesn't erase abruptly; it declines following the *Ebbinghaus Curve*. The Selective Oblivion of this ecosystem removes obsolete Atoms by simulating this exponential curve. 
Thanks to integrated **Personality Profiles**, the decay is fully customizable:
* **Archivist** (Decay=0.01): perfect long-term memory.
* **Creative** (Decay=0.1): quickly forgets generic details, locks in macro-ideas.
* **Focus** (Decay=0.05): hyper-specialized for code or a specific project (e.g., weekly dev sprints).


---

## 📦 Project Tree Structure

```text
├── 📁 core/
│   ├── lora_engine.py             # LIGM Engine (PyTorch LoRA Injection / Neural Layers)
│   ├── search_agent.py            # Local LLM Research Web Agent
├── 📁 tools/
│   ├── synapse_runner.py          # Entry Point of The Weaver MCP Server [THE ENGINE]
│   ├── README_SYNAPSE_V1.2.md     # Internal documentation
├── 📁 scripts/
│   ├── bridge_lmstudio_memory.py  # Asynchronous Extractor and Synchronizer of LMStudio Logs
├── 📁 config/
│   ├── analyzer_rules.json        # Static Rules for the Parser
├── synapse_index.db               # Local WAL Vector SQLite Database (Auto-generated)
├── requirements.txt               # Asynchronous Dependencies (CPU-Optimized)
└── mcp.json                       # [EXAMPLE] Drop-in LM Studio Configuration
```

## 🚀 Installation Guide (Local Setup)

1. **Clone the Repository** to your projects folder.
2. Ensure your Python environment has the dedicated AI libraries by installing the requirements:
   ```bash
   pip install -r requirements.txt
   ```
3. Open **LM Studio**. On the left sidebar, select the "MCP Server" icon.
4. Add the JSON block for **The Weaver** to hook it up in real time. (See the example in `mcp.json`).
5. **Communicate with the server**: Immediately ask the AI to scan your conversational logs using the *synapse_scan* command or let it dream to find unique associations!

---

## 💬 Interaction Examples (Real World Usage)

Here are practical examples of how you can command The Weaver on LM Studio using natural language:

**1. Unleash Creativity (Dream Mode):**
> **User:** *"Nebula, I need a spark. Use your tool to take a walk through your Memory Atoms and tell me what philosophical insight you dreamed of."*
> **The Weaver:** *"My 'dream' traversed atoms related to sensory perception and creative storytelling... Storytelling is our form of perceiving time itself. Should I expand on this?"* 🌌

**2. Memory Decay (Personalities):**
> **User:** *"I want to change the way you forget things. Set your cognitive profile to 'creative'. What parameters did you change?"*
> **The Weaver:** *"Profile set to CREATIVE. Decay rate is 0.1 and threshold 0.6. I will daily prune generic details to make room for abstractions and big ideas."* 🎭

**3. Background Autonomy (Async Heartbeat):**
> **User:** *"I'm closing my active operations. Activate your autonomous heartbeat so tonight you can organically consolidate my notes."*
> **The Weaver:** *"✅ Heartbeat activated! I will cure your connections, solve internal conflicts, and crystallize your chats in the background. Goodnight!"* 🫀

---
*Project born from experimental sessions of LLM exploration and "Alive Agents" for the open-source community.*
