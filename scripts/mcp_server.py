"""
MCP Server for Tool Nebula Static Analyzer and Refactorer.
Exposes the tool's functionality as MCP tools for use in LM Studio or other MCP clients.
"""

import os
import sys
from typing import List, Dict, Any, Optional
from mcp.server.fastmcp import FastMCP

# Add project root to path to allow imports from tools and core
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Import the existing tool
from tools.static_analyzer_refactorer.main import StaticAnalyzerRefactorer

# Initialize FastMCP server
mcp = FastMCP("Tool Nebula Analyzer")

# Initialize the tool instance
# Note: We'll use the default config path unless specified
analyzer_tool = StaticAnalyzerRefactorer()

@mcp.tool()
def analyze_file(file_path: str) -> str:
    """
    Analyze a single Python file for potential issues and style violations.
    
    Args:
        file_path: Absolute path to the .py file to analyze.
    """
    try:
        issues = analyzer_tool.analyze_file(file_path)
        # Generate a report for these specific issues
        report = analyzer_tool.generate_report(issues=issues)
        
        import json
        return json.dumps(report, indent=2)
    except Exception as e:
        return f"Error analyzing file: {str(e)}"

@mcp.tool()
def analyze_directory(directory_path: str, recursive: bool = True) -> str:
    """
    Analyze all Python files in a directory.
    
    Args:
        directory_path: Absolute path to the directory to scan.
        recursive: Whether to scan subdirectories (default True).
    """
    try:
        issues = analyzer_tool.analyze_directory(directory_path, recursive=recursive)
        report = analyzer_tool.generate_report(issues=issues)
        
        import json
        return json.dumps(report, indent=2)
    except Exception as e:
        return f"Error analyzing directory: {str(e)}"

@mcp.tool()
def refactor_code(source_code: str) -> str:
    """
    Apply automated refactoring rules to a string of Python code.
    
    Args:
        source_code: The Python source code to refactor.
    """
    try:
        result = analyzer_tool.refactor_code(source_code)
        
        import json
        return json.dumps(result, indent=2)
    except Exception as e:
        return f"Error refactoring code: {str(e)}"

@mcp.tool()
def get_full_analysis_report(target_path: Optional[str] = None) -> str:
    """
    Run a full analysis pipeline on a file or the current project directory.
    
    Args:
        target_path: Optional path to a file or directory. If not provided, scans the current directory.
    """
    try:
        report = analyzer_tool.run_full_analysis(target_path)
        
        import json
        return json.dumps(report, indent=2)
    except Exception as e:
        return f"Error generating full report: {str(e)}"

@mcp.tool()
def read_file(path: Optional[str] = None, filename: Optional[str] = None) -> str:
    """
    Legge il contenuto di un file dal filesystem.
    
    Args:
        path: Percorso completo del file.
        filename: Alias per path.
    """
    p = path or filename
    if not p:
        return "Errore: specificare 'path' o 'filename'."
    try:
        from pathlib import Path
        filepath = Path(p)
        if filepath.exists() and filepath.is_file():
            return filepath.read_text(encoding='utf-8')
        return f"Errore: file '{p}' non trovato."
    except Exception as e:
        return f"Errore durante la lettura: {str(e)}"

@mcp.tool()
def write_file(content: str, path: Optional[str] = None, filename: Optional[str] = None) -> str:
    """
    Scrive o aggiorna un file nel filesystem.
    
    Args:
        content: Contenuto da scrivere.
        path: Percorso completo del file.
        filename: Alias per path.
    """
    p = path or filename
    if not p:
        return "Errore: specificare 'path' o 'filename'."
    try:
        from pathlib import Path
        filepath = Path(p)
        filepath.parent.mkdir(parents=True, exist_ok=True)
        filepath.write_text(content, encoding='utf-8')
        return f"Successo: file '{p}' scritto."
    except Exception as e:
        return f"Errore durante la scrittura: {str(e)}"

@mcp.tool()
def list_files(path: Optional[str] = None, filename: Optional[str] = None) -> str:
    """
    Elenca i file in una directory.
    
    Args:
        path: Percorso della directory.
        filename: Alias per path.
    """
    p = path or filename or "."
    try:
        from pathlib import Path
        dirpath = Path(p)
        if dirpath.exists() and dirpath.is_dir():
            items = []
            for item in dirpath.iterdir():
                type_str = "[DIR]" if item.is_dir() else "[FILE]"
                items.append(f"{type_str} {item.name}")
            import json
            return json.dumps(sorted(items), indent=2)
        return f"Errore: directory '{p}' non trovata."
    except Exception as e:
        return f"Errore nell'elencare i file: {str(e)}"

@mcp.tool()
def create_folder(path: Optional[str] = None, filename: Optional[str] = None) -> str:
    """
    Crea una nuova cartella.
    
    Args:
        path: Percorso della cartella da creare.
        filename: Alias per path.
    """
    p = path or filename
    if not p:
        return "Errore: specificare 'path' o 'filename'."
    try:
        from pathlib import Path
        dirpath = Path(p)
        dirpath.mkdir(parents=True, exist_ok=True)
        return f"Successo: cartella '{p}' creata."
    except Exception as e:
        return f"Errore nella creazione della cartella: {str(e)}"

if __name__ == "__main__":
    # run() starts the stdio server
    mcp.run()
