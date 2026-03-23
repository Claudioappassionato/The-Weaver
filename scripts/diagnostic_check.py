"""
Diagnostic Check Script for Tool Nebula
Verifies environment, file existence, and basic execution capabilities.
This script helps identify why the MCP connection might be failing.
"""

import os
import sys
import subprocess


def check_python_path():
    """Verify Python interpreter is accessible."""
    print("=" * 60)
    print("CHECKING PYTHON INTERPRETER")
    print("=" * 60)
    
    try:
        result = subprocess.run(
            [sys.executable, "--version"],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            print(f"✅ Python found: {result.stdout.strip()}")
            return True
        else:
            print("❌ Python interpreter not accessible")
            print(f"   stderr: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"❌ Error checking Python: {e}")
        return False


def check_file_exists(filepath):
    """Check if a file exists and is readable."""
    print(f"\nChecking file existence: {filepath}")
    
    if os.path.exists(filepath):
        try:
            with open(filepath, 'r') as f:
                first_line = f.readline()
                print(f"✅ File exists and is readable")
                return True
        except Exception as e:
            print(f"❌ Cannot read file: {e}")
            return False
    else:
        print(f"❌ File not found: {filepath}")
        return False


def check_directory_structure():
    """Verify the tool_nebula directory structure is complete."""
    print("\n" + "=" * 60)
    print("CHECKING DIRECTORY STRUCTURE")
    print("=" * 60)
    
    base_path = "C:/mcp_projects/tool_nebula"
    
    required_files = [
        ("core/analyzer.py", "Core analyzer module"),
        ("core/refactorer.py", "Refactoring engine"),
        ("tools/static_analyzer_refactorer/main.py", "Main tool logic"),
        ("scripts/run_tool.py", "Wrapper script for MCP"),
        ("config/analyzer_rules.json", "Configuration rules"),
        ("tests/sample_code_with_issues.py", "Test case file")
    ]
    
    all_exist = True
    
    for filepath, description in required_files:
        full_path = os.path.join(base_path, filepath)
        if check_file_exists(full_path):
            print(f"  ✅ {description}")
        else:
            print(f"  ❌ {description} - MISSING")
            all_exist = False
    
    return all_exist


def check_mcp_config():
    """Verify MCP server configuration."""
    print("\n" + "=" * 60)
    print("CHECKING MCP CONFIGURATION")
    print("=" * 60)
    
    mcp_config_path = "C:/mcp_projects/tool_nebula/config/mcp_server_config.json"
    
    if os.path.exists(mcp_config_path):
        try:
            import json
            with open(mcp_config_path, 'r') as f:
                config = json.load(f)
            
            print("✅ MCP configuration file found")
            
            # Check if tool-nebula-analyzer is included
            servers = config.get('mcpServers', {})
            if 'tool-nebula-analyzer' in servers:
                print("✅ tool-nebula-analyzer server configured")
                
                # Print the configuration for verification
                print("\nCurrent MCP Server Configuration:")
                print(json.dumps(servers['tool-nebula-analyzer'], indent=2))
            else:
                print("❌ tool-nebula-analyzer NOT found in MCP config")
        except Exception as e:
            print(f"❌ Error reading MCP config: {e}")
    else:
        print("⚠️  MCP configuration file not found yet (will be generated)")


def check_pythonpath_env():
    """Verify PYTHONPATH environment variable."""
    print("\n" + "=" * 60)
    print("CHECKING PYTHONPATH ENVIRONMENT")
    print("=" * 60)
    
    if 'PYTHONPATH' in os.environ:
        path = os.environ['PYTHONPATH']
        print(f"✅ PYTHONPATH is set to: {path}")
        
        # Check if tool_nebula is included
        if 'tool_nebula' in path.lower() or 'toolnebula' in path.lower():
            print("✅ tool_nebula directory is in PYTHONPATH")
        else:
            print("⚠️  WARNING: tool_nebula NOT in PYTHONPATH")
            print("   Suggested fix: Add 'C:/mcp_projects/tool_nebula' to PYTHONPATH")
    else:
        print("❌ PYTHONPATH environment variable is NOT set")
        print("   This might cause import errors when running the tool")


def run_simple_test():
    """Run a simple Python test to verify execution works."""
    print("\n" + "=" * 60)
    print("RUNNING SIMPLE TEST")
    print("=" * 60)
    
    try:
        result = subprocess.run(
            [sys.executable, "-c", "print('Hello from Tool Nebula!')"],
            capture_output=True,
            text=True,
            cwd="C:/mcp_projects/tool_nebula"
        )
        
        if result.returncode == 0:
            print(f"✅ Simple test successful!")
            print(f"   Output: {result.stdout.strip()}")
        else:
            print("❌ Simple test failed:")
            print(f"   stderr: {result.stderr}")
    except Exception as e:
        print(f"❌ Error running simple test: {e}")


def main():
    """Run all diagnostic checks."""
    print("\n🔍 TOOL NEBULA DIAGNOSTIC CHECK")
    print("=" * 60)
    
    results = []
    
    # Run checks
    python_ok = check_python_path()
    results.append(("Python Interpreter", "OK" if python_ok else "FAILED"))
    
    structure_ok = check_directory_structure()
    results.append(("Directory Structure", "OK" if structure_ok else "INCOMPLETE"))
    
    mcp_config_ok = check_mcp_config()
    results.append(("MCP Configuration", "OK" if mcp_config_ok else "NEEDS FIX"))
    
    pythonpath_ok = check_pythonpath_env()
    results.append(("PYTHONPATH Environment", "OK" if pythonpath_ok else "NEEDS FIX"))
    
    test_ok = run_simple_test()
    results.append(("Simple Test Execution", "OK" if test_ok else "FAILED"))
    
    # Summary
    print("\n" + "=" * 60)
    print("DIAGNOSTIC SUMMARY")
    print("=" * 60)
    
    for check, status in results:
        print(f"{check}: {status}")
    
    print("\n" + "=" * 60)
    if all(status == "OK" for _, status in results):
        print("✅ ALL CHECKS PASSED - Tool Nebula is ready!")
    else:
        print("⚠️  SOME ISSUES DETECTED - Review the errors above")
        print("\nNext steps:")
        print("1. Fix any 'FAILED' or 'NEEDS FIX' items listed above")
        print("2. Re-run this diagnostic after fixes")
        print("3. Try connecting to MCP server again")


if __name__ == '__main__':
    main()
