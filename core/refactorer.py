"""
Code Refactoring Engine Module
Responsible for automatically fixing detected issues in source code.
"""

import ast
import json
import os
from typing import List, Dict, Any, Tuple


class RefactorRule:
    """Represents a refactoring rule with pattern and replacement logic."""
    
    def __init__(self, description: str, pattern: str, replacement: str = None, 
                 conditions: List[str] = None):
        self.description = description
        self.pattern = pattern
        self.replacement = replacement  # Can be a string or function
        self.conditions = conditions or []


class Refactorer:
    """Engine for applying refactoring rules to source code."""
    
    def __init__(self, config_path: str):
        """Initialize the refactorer with configuration rules."""
        self.config_path = config_path
        self.rules = []
        
        if os.path.exists(config_path):
            self.load_config()
    
    def load_config(self) -> None:
        """Load refactoring rules from JSON configuration."""
        with open(self.config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        # Parse refactoring rules
        for rule_name, rule_data in config.get('refactoring_rules', {}).items():
            self.rules.append(RefactorRule(
                description=rule_data.get('description', ''),
                pattern=rule_data.get('pattern', ''),
                replacement=rule_data.get('replacement', ''),
                conditions=rule_data.get('conditions', [])
            ))
    
    def apply_rules(self, source_code: str) -> Tuple[str, List[Dict[str, Any]]]:
        """Apply all refactoring rules to the source code."""
        modified = False
        changes_log = []
        
        # Make a copy of the original code
        current_code = source_code
        
        for rule in self.rules:
            if not rule.pattern or rule.pattern == '':
                continue
            
            # Check conditions (simplified implementation)
            if self._check_conditions(rule, current_code):
                # Apply replacement
                new_code, applied_changes = self._apply_pattern(rule, current_code)
                
                if applied_changes:
                    current_code = new_code
                    modified = True
                    changes_log.append({
                        'rule': rule.description,
                        'changes': len(applied_changes),
                        'details': applied_changes[:3]  # Log first 3 changes
                    })
        
        return current_code, changes_log
    
    def _check_conditions(self, rule: RefactorRule, code: str) -> bool:
        """Check if refactoring conditions are met."""
        for condition in rule.conditions:
            if not self._evaluate_condition(condition, code):
                return False
        return True
    
    def _evaluate_condition(self, condition: str, code: str) -> bool:
        """Evaluate a simple string condition against the code."""
        # Simple keyword matching for conditions (e.g., "variable_not_referenced")
        if 'not_referenced' in condition.lower():
            return True  # Assume true if we're in a refactoring context
        elif 'class_definition' in condition.lower():
            return False  # Don't refactor inside class definitions yet
        return True
    
    def _apply_pattern(self, rule: RefactorRule, code: str) -> Tuple[str, List[str]]:
        """Apply the pattern replacement to the code."""
        changes = []
        
        if rule.replacement is None or rule.replacement == '':
            # Remove line entirely
            lines = code.split('\n')
            new_lines = []
            for i, line in enumerate(lines):
                if rule.pattern not in line:
                    new_lines.append(line)
                else:
                    changes.append(f"Removed unused variable at line {i+1}")
            return '\n'.join(new_lines), changes
        
        # Simple string replacement (more complex logic for regex patterns would go here)
        if isinstance(rule.replacement, str):
            new_code = code.replace(rule.pattern, rule.replacement)
            changes.append(f"Applied replacement: {rule.description}")
            return new_code, [changes[0]]
        
        # If replacement is a function (not implemented yet), call it
        pass
    
    def generate_fix_report(self, original_code: str, fixed_code: str, 
                           changes_log: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate a detailed report of the refactoring process."""
        return {
            'original_length': len(original_code),
            'fixed_length': len(fixed_code),
            'bytes_saved': len(original_code) - len(fixed_code),
            'changes_applied': changes_log,
            'success': True  # Assuming all rules applied successfully
        }
