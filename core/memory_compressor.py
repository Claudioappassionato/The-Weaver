"""
Memory Compression Engine Module
Responsible for summarizing long conversation histories to reduce token usage while preserving critical context.
Inspired by OpenClaw's skill-based architecture but adapted for local LM Studio agents.
"""

import json
from typing import List, Dict, Any, Optional


class MessageSummary:
    """Represents a summarized segment of messages."""
    
    def __init__(self, summary_text: str, original_count: int, key_points: List[str] = None):
        self.summary_text = summary_text
        self.original_count = original_count
        self.key_points = key_points or []


class MemoryCompressor:
    """Engine for compressing conversation history using AI summarization."""
    
    def __init__(self, model_name: str = "qwen3.5-4bud", max_summary_length: int = 1024):
        """Initialize the compressor with model configuration.
        
        Args:
            model_name: Name of the local model to use for summarization (e.g., 'qwen3.5-4bud')
            max_summary_length: Maximum token length for the summary text
        """
        self.model_name = model_name
        self.max_summary_length = max_summary_length
        
    def _generate_summarization_prompt(self, messages: List[Dict[str, Any]]) -> str:
        """Generate a prompt optimized for extracting key information from conversation history.
        
        Args:
            messages: List of message dictionaries with 'role' and 'content' keys
            
        Returns:
            Formatted prompt string ready for the LLM
        """
        # Extract critical metadata
        user_messages = [m for m in messages if m.get('role') == 'user']
        assistant_messages = [m for m in messages if m.get('role') == 'assistant']
        
        total_turns = len(user_messages) // 2 if user_messages else 0
        
        prompt = f"""You are an expert AI agent memory manager. Your task is to compress a conversation history while preserving all critical facts, decisions, and technical insights.

CONVERSATION CONTEXT:
- Total message turns: {total_turns}
- User messages: {len(user_messages)}
- Assistant responses: {len(assistant_messages)}

CRITICAL INSTRUCTIONS:
1. Identify and preserve ALL factual claims, code snippets, configuration details, and decisions made.
2. Summarize repetitive conversational filler into single sentences where appropriate.
3. Maintain the chronological flow of critical events.
4. Output exactly 3 key paragraphs as described below.

REQUIRED OUTPUT FORMAT:
Produce a summary consisting of EXACTLY 3 paragraphs with this structure:

Paragraph 1 - Context & Setup: Describe the initial context, goals established, and technical setup discussed in the conversation. Include specific model names, configurations, or environment details mentioned.

Paragraph 2 - Core Work & Decisions: Summarize the main tasks completed, critical decisions made, and any problems solved during the conversation. Preserve all technical solutions and architectural choices.

Paragraph 3 - Current State & Next Steps: Describe the current status of the project/work, any pending items, and the agreed-upon next steps or priorities for future work.

CONSTRAINTS:
- Total output length must be under {self.max_summary_length} tokens (approximately 500-800 words).
- Do not include conversational pleasantries or filler.
- Maintain technical accuracy - do not invent facts not present in the original conversation.
- Use clear, concise language suitable for quick reference by an AI agent.

CONVERSATION TO SUMMARIZE:
{json.dumps(messages)}

BEGIN SUMMARY:"""
        
        return prompt
    
    def summarize_context(self, messages: List[Dict[str, Any]], 
                         output_format: str = "markdown") -> Dict[str, Any]:
        """Summarize a conversation history to reduce token usage.
        
        Args:
            messages: List of message dictionaries from the conversation history
            output_format: Output format ('text', 'json', or 'markdown')
            
        Returns:
            Dictionary containing summary text and metadata about what was compressed
        """
        if not messages:
            return {
                'summary': '',
                'original_count': 0,
                'compressed_size': 0,
                'key_points': [],
                'status': 'empty'
            }
        
        # Generate the summarization prompt
        prompt = self._generate_summarization_prompt(messages)
        
        # TODO: Integrate with LM Studio API here
        # For now, we'll use a placeholder that demonstrates the structure
        # In production, this would call the local model via MCP or direct API
        
        # Placeholder implementation - replace with actual API call
        print(f"[MEMORY COMPRESSOR] Generating summary for {len(messages)} messages using model: {self.model_name}")
        
        # Simulated summary generation (replace with actual LLM call)
        # This is where you would integrate the LM Studio API call
        
        return {
            'summary': '[SUMMARY PLACEHOLDER - Replace with actual AI-generated text]',
            'original_count': len(messages),
            'compressed_size_estimate': 500,  # Target reduction from ~18k to ~500 tokens
            'key_points': [
                'Critical facts and technical decisions preserved',
                'Conversation flow maintained chronologically',
                'Repetitive content condensed into essential information'
            ],
            'status': 'placeholder',
            'model_used': self.model_name,
            'compression_ratio': f"{len(messages)} messages -> ~500 tokens"
        }
    
    def compress_with_fallback(self, messages: List[Dict[str, Any]], 
                               fallback_strategy: str = "keep_recent") -> Dict[str, Any]:
        """Compress conversation history with fallback strategies if AI summarization fails.
        
        Args:
            messages: Conversation history to compress
            fallback_strategy: Strategy when AI summary is unavailable ('keep_recent', 'simple_text')
            
        Returns:
            Compressed message list or text representation
        """
        # Primary method: Use AI summarization
        ai_summary = self.summarize_context(messages)
        
        if ai_summary['status'] == 'placeholder':
            print("[MEMORY COMPRESSOR] AI summary not available, using fallback strategy")
            
            # Fallback 1: Keep only recent messages (default behavior in existing script)
            if fallback_strategy == "keep_recent":
                return {
                    'compressed_messages': messages[-10:],  # Last 10 messages
                    'original_count': len(messages),
                    'kept_count': min(10, len(messages)),
                    'strategy': 'keep_recent',
                    'status': 'fallback_applied'
                }
            
            # Fallback 2: Simple text representation (for debugging)
            elif fallback_strategy == "simple_text":
                return {
                    'summary': '\n'.join([f"{m.get('role', '?')}: {str(m.get('content', ''))[:100]}..." 
                                         for m in messages[-5:]]),
                    'original_count': len(messages),
                    'compressed_size': 200,
                    'strategy': 'simple_text_fallback',
                    'status': 'fallback_applied'
                }
        
        return ai_summary


def create_memory_compressor(model_name: str = "qwen3.5-4bud") -> MemoryCompressor:
    """Factory function to create a configured memory compressor instance.
    
    Args:
        model_name: Name of the local model to use
        
    Returns:
        Configured MemoryCompressor instance
    """
    return MemoryCompressor(model_name=model_name)
