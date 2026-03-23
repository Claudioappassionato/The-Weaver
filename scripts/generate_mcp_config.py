import json

mcp_config = {
    "mcpServers": {
        "document-intelligence": {
            "command": "python",
            "args": ["C:/mcp_projects/DocumentMCP/document_server.py"],
            "env": {"PYTHONPATH": "C:/mcp_projects/DocumentMCP"}
        },
        "expert-mode": {
            "command": "python",
            "args": ["C:/mcp_projects/ExpertMCP/expert_mcp_server.py"],
            "env": {"PYTHONPATH": "C:/mcp_projects/ExpertMCP"}
        },
        "in-depth-analysis": {
            "command": "python",
            "args": ["C:/mcp_projects/in-depth-analysis/in_depth_analysis_server.py"],
            "env": {"PYTHONPATH": "C:/mcp_projects/in-depth-analysis"}
        },
        "memory": {
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-memory"]
        },
        "sequential-thinking": {
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-sequential-thinking"]
        },
        "search": {
            "command": "npx",
            "args": ["-y", "mcp-searxng"],
            "env": {"SEARXNG_URL": "https://search.noemaai.com/"}
        },
        "nmap-mcp": {
            "command": "python",
            "args": ["C:\\mcp_projects\\nmap_mcp_server.py\\nmap_mcp_server.py"],
            "env": {"PYTHONPATH": "C:\\mcp_projects\\nmap_mcp_server.py"}
        },
        "essay-writer": {
            "command": "python",
            "args": ["C:/mcp_projects/Server Book/server.py"],
            "env": {
                "PYTHONPATH": "C:/mcp_projects/Server Book",
                "ESSAY_STORAGE_DIR": "C:/mcp_projects/Server Book/storage"
            }
        },
        "soul-agent-autonomous": {
            "command": "python",
            "args": ["C:/mcp_projects/SoulAgent/server.py"],
            "env": {"PYTHONPATH": "C:/mcp_projects/SoulAgent"}
        },
        "tool-nebula-analyzer": {
            "command": "C:/Program Files/Python312/python.exe",
            "args": ["C:/mcp_projects/tool_nebula/scripts/mcp_server.py"],
            "env": {"PYTHONPATH": "C:/mcp_projects/tool_nebula"}
        },
        "the-weaver": {
            "command": "python",
            "args": ["C:/mcp_projects/tool_nebula/tools/synapse_runner.py"],
            "env": {"PYTHONPATH": "C:/mcp_projects/tool_nebula"}
        }
    }
}

with open('config/mcp_server_config.json', 'w', encoding='utf-8') as f:
    json.dump(mcp_config, f, indent=4)

print("MCP Server configuration saved successfully!")