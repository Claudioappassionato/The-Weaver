"""
Static Analyzer and Refactorer Tool - Main Module
Coordinates analysis and refactoring processes for Python codebases.
"""

import os
import sys
from typing import List, Dict, Any

# Add core module to path - CRITICAL: Ensure core/ is in path before imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'core'))

from analyzer import StaticAnalyzer
from refactorer import Refactorer


class StaticAnalyzerRefactorer:
    """Main tool class that integrates static analysis and refactoring."""
    
    def __init__(self, config_path: str = None):
        """Initialize the integrated tool.
        
        Args:
            config_path: Path to configuration file (defaults to 'config/analyzer_rules.json')
        """
        self.config_path = config_path or os.path.join(
            os.path.dirname(__file__), '..', '..', 'config', 'analyzer_rules.json'
        )
        
        # Initialize components
        try:
            self.analyzer = StaticAnalyzer(self.config_path)
            print(f"[INFO] Analyzer initialized successfully", file=sys.stderr)
        except Exception as e:
            print(f"[ERROR] Failed to initialize analyzer: {e}", file=sys.stderr)
            raise
        
        try:
            self.refactorer = Refactorer(self.config_path)
            print(f"[INFO] Refactorer initialized successfully", file=sys.stderr)
        except Exception as e:
            print(f"[ERROR] Failed to initialize refactorer: {e}", file=sys.stderr)
            raise
    
    def analyze_file(self, file_path: str) -> List[Dict[str, Any]]:
        """Analyze a single Python file.
        
        Args:
            file_path: Path to the Python file to analyze
            
        Returns:
            List of detected issues with severity and details
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")
        
        print(f"[INFO] Analyzing file: {os.path.basename(file_path)}", file=sys.stderr)
        return self.analyzer.analyze_file(file_path)
    
    def analyze_directory(self, dir_path: str, recursive: bool = True) -> List[Dict[str, Any]]:
        """Analyze all Python files in a directory.
        
        Args:
            dir_path: Path to the directory to scan
            recursive: Whether to scan subdirectories
            
        Returns:
            Combined list of issues from all analyzed files
        """
        if not os.path.exists(dir_path):
            raise FileNotFoundError(f"Directory not found: {dir_path}")
        
        all_issues = []
        
        for root, dirs, files in os.walk(dir_path):
            for file in files:
                if file.endswith('.py'):
                    file_path = os.path.join(root, file)
                    try:
                        issues = self.analyze_file(file_path)
                        all_issues.extend(issues)
                    except Exception as e:
                        print(f"[WARNING] Error analyzing {file}: {e}", file=sys.stderr)
        
        return all_issues
    
    def refactor_code(self, source_code: str) -> Dict[str, Any]:
        """Refactor provided source code.
        
        Args:
            source_code: Python source code to refactor
            
        Returns:
            Dictionary containing fixed code and refactoring report
        """
        print("[INFO] Applying refactoring rules...", file=sys.stderr)
        fixed_code, changes_log = self.refactorer.apply_rules(source_code)
        
        return {
            'original_length': len(source_code),
            'fixed_length': len(fixed_code),
            'changes_applied': changes_log,
            'success': True
        }
    
    def generate_report(self, file_path: str = None, 
                       issues: List[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Generate a comprehensive report of the analysis.
        
        Args:
            file_path: Optional specific file to focus on
            issues: Optional pre-computed list of issues
            
        Returns:
            Report dictionary with summary and details
        """
        if not issues:
            # Analyze current directory or provided file
            if file_path:
                issues = self.analyze_file(file_path)
            else:
                print("[INFO] Generating report for current directory...", file=sys.stderr)
                issues = self.analyze_directory('.')
        
        summary = self.analyzer.get_summary()
        
        # Add detailed information
        report = {
            'summary': summary,
            'files_analyzed': list(summary['files_analyzed']),
            'issues_by_severity': {},
            'detailed_issues': []
        }
        
        for issue in issues:
            severity = issue.get('type', 'unknown')
            report['issues_by_severity'][severity] = \
                report['issues_by_severity'].get(severity, 0) + 1
            
            report['detailed_issues'].append({
                'file': issue.get('file', 'unknown'),
                'line': issue.get('line', 0),
                'type': severity,
                'message': issue.get('message', ''),
                'code_snippet': issue.get('code_snippet', '')[:100] + ('...' if len(issue.get('code_snippet', '')) > 100 else '')
            })
        
        return report
    
    def run_full_analysis(self, file_path: str = None) -> Dict[str, Any]:
        """Run the complete analysis and refactoring pipeline.
        
        This is the main entry point for the tool.
        
        Args:
            file_path: Path to analyze (optional)
            
        Returns:
            Complete report including analysis results and refactoring suggestions
        """
        print("=" * 60, file=sys.stderr)
        print("STATIC ANALYZER AND REFACTORER TOOL", file=sys.stderr)
        print("=" * 60, file=sys.stderr)
        
        # Step 1: Analyze
        print("\n[STEP 1] Running Static Analysis...", file=sys.stderr)
        issues = self.analyze_file(file_path) if file_path else []
        
        if not issues and not os.path.exists('.'):
            print("[WARNING] No files found to analyze.", file=sys.stderr)
            return {'error': 'No files found'}
        
        # Step 2: Generate Report
        report = self.generate_report(issues=issues)
        
        # Step 3: Refactoring Suggestions (if critical issues exist)
        if report['summary']['by_severity'].get('critical', 0) > 0:
            print("\n[STEP 3] Critical Issues Detected - Refactoring Recommended...", file=sys.stderr)
            # In a real implementation, we would extract the problematic code here
            # and apply refactoring rules to fix them
            
        return report


def main():
    """Main entry point for command-line usage."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Static Analyzer and Refactorer Tool')
    parser.add_argument('file', nargs='?', help='Python file to analyze')
    parser.add_argument('--dir', '-d', help='Directory to scan recursively')
    parser.add_argument('--config', '-c', default=None, help='Path to config file')
    
    args = parser.parse_args()
    
    try:
        tool = StaticAnalyzerRefactorer(args.config)
        
        if args.file:
            report = tool.run_full_analysis(args.file)
        elif args.dir:
            print(f"[INFO] Scanning directory: {args.dir}", file=sys.stderr)
            issues = tool.analyze_directory(args.dir)
            report = tool.generate_report(issues=issues)
        else:
            # Default: analyze current directory
            print("[INFO] Analyzing current directory...", file=sys.stderr)
            issues = tool.analyze_directory('.')
            report = tool.generate_report()
        
        # Output report as JSON for easy parsing
        import json
        print(json.dumps(report, indent=2))
            
    except Exception as e:
        print(f"[ERROR] Failed to execute analysis: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
