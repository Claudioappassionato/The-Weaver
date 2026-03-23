"""
Static Analyzer and Refactorer Tool Package Initialization
"""

from .main import StaticAnalyzerRefactorer, main

__version__ = '1.0.0'
__author__ = 'Tool Nebula Autonomous Agent'

def get_tool_instance(config_path=None):
    """Factory function to create a tool instance."""
    return StaticAnalyzerRefactorer(config_path)
