"""
Wrapper script for easy execution of the Static Analyzer and Refactorer Tool.
This script can be called from MCP servers or command line.
"""

import sys
import os

# Add tool_nebula to path - CRITICAL FIX: Add parent directory to sys.path
script_dir = os.path.dirname(os.path.abspath(__file__))
tool_nebula_root = os.path.dirname(script_dir)  # Go up one level from scripts/

if tool_nebula_root not in sys.path:
    sys.path.insert(0, tool_nebula_root)

print(f"[INFO] Tool Nebula root added to PATH: {tool_nebula_root}")

from tools.static_analyzer_refactorer.main import main as run_tool


def execute_analysis(file_path=None, directory=None):
    """Execute the analysis with optional file or directory argument."""
    if file_path:
        print(f"Analyzing file: {file_path}")
        return run_tool(file_path)
    elif directory:
        print(f"Scanning directory: {directory}")
        # Note: Directory scanning requires additional implementation in main.py
        # For now, we'll just call the tool with no arguments and let it scan current dir
        return run_tool()
    else:
        print("Usage: python run_tool.py <file_or_directory>")
        sys.exit(1)


if __name__ == '__main__':
    # The tool's main() uses argparse which will read from sys.argv automatically.
    # We just need to call it.
    try:
        run_tool()
    except Exception as e:
        print(f"[ERROR] Tool execution failed: {e}")
        sys.exit(1)
