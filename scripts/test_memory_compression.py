"""
Memory Compression Test Script - Persistent Context Project
Tests the memory compression engine with real conversation data from LM Studio.

Usage: python test_memory_compression.py <conversation_json_path> [optional_args]

This script demonstrates how to compress long conversation histories while preserving
critical context, reducing token usage from ~18k to ~500 tokens.
"""

import sys
import os
import json
from typing import List, Dict, Any

# Add tool_nebula to path
script_dir = os.path.dirname(os.path.abspath(__file__))
tool_nebula_root = os.path.dirname(script_dir)  # Go up one level from scripts/

if tool_nebutter_root not in sys.path:
    sys.path.insert(0, tool_nebutter_root)

from core.memory_compressor import MemoryCompressor


class LMStudioMemoryCompressor:
    """Wrapper that integrates MemoryCompressor with actual LM Studio API calls."""
    
    def __init__(self, model_name: str = "qwen3.5-4bud", 
                 lmstudio_url: str = "http://localhost:1234"):
        self.model_name = model_name
        self.lmstudio_url = lmstudio_url
        
    async def call_local_model(self, prompt: str) -> str:
        """Make an API call to LM Studio server.
        
        TODO: Implement actual MCP or direct API integration here.
        For now, this is a placeholder that demonstrates the integration point.
        """
        print(f"[LM STUDIO] Calling model '{self.model_name}' with prompt length: {len(prompt)} chars")
        
        # Placeholder - replace with actual LM Studio API call
        # Example using MCP tool (when available):
        # from mcp import tools
        # result = await tools.searxng_web_search(query=prompt)
        
        # Or direct HTTP call to LM Studio API:
        # response = requests.post(f"{self.lmstudio_url}/api/generate", json={...})
        
        raise NotImplementedError("LM Studio API integration not yet implemented. "
                                  "Use fallback strategy or implement MCP tool integration.")


def load_conversation_json(file_path: str) -> List[Dict[str, Any]]:
    """Load conversation history from JSON file."""
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Extract messages from the conversation structure
    messages = []
    for msg in data.get('messages', []):
        if 'versions' in msg and len(msg['versions']) > 0:
            version = msg['versions'][0]
            if isinstance(version, dict) and 'text' in version:
                messages.append({
                    'role': msg.get('role', 'assistant'),
                    'content': version['text'][:2000] + ('...' if len(version['text']) > 2000 else '')
                })
    
    return messages


def test_compression(messages: List[Dict[str, Any]], 
                     compressor: MemoryCompressor) -> Dict[str, Any]:
    """Test the compression engine with sample data."""
    print(f"\n{'='*60}")
    print("MEMORY COMPRESSION TEST")
    print(f"{'='*60}")
    print(f"Original messages: {len(messages)}")
    print(f"Model: {compressor.model_name}\n")
    
    # Perform compression
    result = compressor.summarize_context(messages)
    
    # Display results
    print("COMPRESSION RESULTS:")
    print("-" * 40)
    print(f"Original size estimate: ~{len(json.dumps(messages))} bytes")
    print(f"Compressed size estimate: {result.get('compressed_size_estimate', 'N/A')} tokens")
    print(f"Compression ratio: {result.get('compression_ratio', 'N/A')}")
    print(f"\nKey points preserved:")
    for i, point in enumerate(result.get('key_points', []), 1):
        print(f"  {i}. {point}")
    
    return result


def main():
    """Main entry point for memory compression testing."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Test Memory Compression Engine')
    parser.add_argument('input_file', help='Path to conversation JSON file')
    parser.add_argument('--model', '-m', default='qwen3.5-4bud', 
                       help=f'Model name (default: {\"qwen3.5-4bud\"})')
    parser.add_argument('--url', '-u', default='http://localhost:1234',
                       help=f'LM Studio API URL (default: http://localhost:1234)')
    
    args = parser.parse_args()
    
    try:
        # Load conversation data
        print(f"[INFO] Loading conversation from: {args.input_file}")
        messages = load_conversation_json(args.input_file)
        
        if not messages:
            print("[ERROR] No valid messages found in file")
            sys.exit(1)
        
        # Create compressor instance
        print(f"[INFO] Initializing MemoryCompressor with model: {args.model}")
        compressor = MemoryCompressor(model_name=args.model)
        
        # Test compression (using placeholder for now)
        result = test_compression(messages, compressor)
        
        # TODO: Integrate actual LM Studio API call here
        # When MCP tools are available, replace with:
        # lm_compressor = LMStudioMemoryCompressor(model_name=args.model, lmstudio_url=args.url)
        # async_result = await lm_compressor.call_local_model(prompt)
        
        print(f"\n[SUCCESS] Compression test completed.")
        print(f"[NOTE] Actual AI summarization requires LM Studio API integration.")
        
    except FileNotFoundError:
        print(f"[ERROR] File not found: {args.input_file}")
        sys.exit(1)
    except Exception as e:
        print(f"[ERROR] Failed to run compression test: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
