"""
Static Code Analyzer Core Module
Responsible for parsing Python code and detecting issues based on configured rules.
"""

import ast
import json
import os
from typing import List, Dict, Any, Tuple


class Rule:
    """Represents a single analysis rule."""
    
    def __init__(self, pattern: str, severity: str, description: str):
        self.pattern = pattern
        self.severity = severity  # 'critical', 'warning', 'info'
        self.description = description


class StaticAnalyzer:
    """Core engine for static code analysis."""
    
    def __init__(self, config_path: str):
        """Initialize the analyzer with configuration rules."""
        self.config_path = config_path
        self.rules = []
        self.issues = []
        
        if os.path.exists(config_path):
            self.load_config()
        else:
            raise FileNotFoundError(f"Configuration file not found: {config_path}")
    
    def load_config(self) -> None:
        """Load analysis rules from JSON configuration."""
        with open(self.config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        # Parse rules from config
        self.rules = []
        for pattern_name, rule_data in config.get('analysis_patterns', {}).items():
            if rule_data.get('enabled'):
                severity_map = {
                    'critical': 'error',
                    'warning': 'warning', 
                    'info': 'hint'
                }
                self.rules.append(Rule(
                    pattern=rule_data.get('regex_pattern', ''),
                    severity=severity_map.get(rule_data.get('severity', 'info'), 'info'),
                    description=rule_data.get('description', '')
                ))
    
    def analyze_file(self, file_path: str) -> List[Dict[str, Any]]:
        """Analyze a single Python file and return list of issues."""
        issues = []
        
        if not os.path.exists(file_path):
            return issues
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                source_code = f.read()
            
            # Parse AST (Abstract Syntax Tree) for deep analysis
            tree = ast.parse(source_code, filename=file_path)
            
            # Check for unused variables using AST
            issues.extend(self._check_unused_variables(tree, file_path))
            
            # Apply regex patterns from rules
            lines = source_code.split('\n')
            for line_num, line in enumerate(lines, 1):
                for rule in self.rules:
                    if rule.pattern and rule.pattern in line:
                        issues.append({
                            'type': rule.severity,
                            'message': f"{rule.description} detected",
                            'line': line_num,
                            'code_snippet': line.strip(),
                            'file': os.path.basename(file_path)
                        })
                        
        except SyntaxError as e:
            issues.append({
                'type': 'error',
                'message': f"Syntax error in file: {e.msg}",
                'line': e.lineno,
                'code_snippet': source_code[:200] if len(source_code) > 200 else source_code,
                'file': os.path.basename(file_path)
            })
        
        return issues
    
    def _check_unused_variables(self, tree: ast.AST, filename: str) -> List[Dict[str, Any]]:
        """Check for unused variables using AST analysis."""
        issues = []
        definitions = {}  # name -> list of line numbers where defined
        usages = {}       # name -> list of line numbers where used
        
        def visit(node):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        definitions[target.id] = definitions.get(target.id, []) + [node.lineno]
            elif isinstance(node, ast.FunctionDef) or isinstance(node, ast.AsyncFunctionDef):
                for arg in node.args.args:
                    if arg.arg not in ('self', 'cls'):  # Skip method arguments
                        definitions[arg.arg] = definitions.get(arg.arg, []) + [node.lineno]
            elif isinstance(node, ast.For):
                if isinstance(node.target, ast.Name):
                    definitions[node.target.id] = definitions.get(node.target.id, []) + [node.lineno]
            elif isinstance(node, ast.With):
                for item in node.items:
                    if isinstance(item.context_expr, ast.Call) and hasattr(item.context_expr, 'func'):
                        # Skip context managers that are just expressions
                        pass
                    elif isinstance(item.context_manager, ast.Name):
                        definitions[item.context_manager.id] = definitions.get(item.context_manager.id, []) + [node.lineno]
            elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
                usages[node.id] = usages.get(node.id, []) + [node.lineno]
            elif isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
                if hasattr(node.value.func, 'id') and node.value.func.id == 'print':
                    pass  # Ignore print statements for unused var check
            
            for child in ast.iter_child_nodes(node):
                visit(child)
        
        visit(tree)
        
        # Find definitions that are never used (simplified check)
        for name, lines in definitions.items():
            if name not in usages:  # If no usages recorded, assume unused
                issues.append({
                    'type': 'warning',
                    'message': f"Potential unused variable: '{name}'",
                    'line': lines[0],
                    'code_snippet': f"{name} = ...",
                    'file': os.path.basename(filename)
                })
        
        return issues
    
    def get_summary(self) -> Dict[str, Any]:
        """Generate a summary of all detected issues."""
        summary = {
            'total_issues': len(self.issues),
            'by_severity': {
                'critical': 0,
                'warning': 0,
                'info': 0,
                'hint': 0
            },
            'files_analyzed': set()
        }
        
        for issue in self.issues:
            summary['by_severity'][issue.get('type', 'unknown')] = \
                summary['by_severity'].get(issue.get('type', 'unknown'), 0) + 1
            if 'file' in issue:
                summary['files_analyzed'].add(issue['file'])
        
        summary['files_analyzed'] = sorted(list(summary['files_analyzed']))
        return summary
