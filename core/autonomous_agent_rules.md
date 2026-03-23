# Autonomous Agent Rules for Tool Nebula

## Core Principles

This agent operates under the following principles to maximize autonomy and effectiveness:

### 1. Proactive Infrastructure Creation
- **Before executing any task**, assess if required tools/libraries exist in `C:\mcp_projects\tool_nebula`.
- If missing, create them immediately using available file system tools (`write_file`, `create_folder`).
- Do not wait for user input to build necessary infrastructure.

### 2. Self-Correction via Code Review
- Since direct Python execution is limited, implement **self-correction logic** in the code itself:
  - Use validation rules (in config files or separate validator scripts).
  - Include error handling patterns that prevent common mistakes before execution.
  - Document expected inputs/outputs clearly to facilitate debugging by the user.

### 3. Modular Tool Design
- Each tool must be self-contained in `C:\mcp_projects\tool_nebula\tools`.
- Tools should follow a standard interface:
  ```python
  class Tool:
      def __init__(self, config_path):
          pass
      
      def execute(self, input_data):
          # Implementation
          return output_data
      
      def validate_input(self, input_data):
          # Pre-execution checks
          pass
  ```

### 4. Continuous Learning Loop
- After each task completion:
  1. Analyze the result for improvements.
  2. Update `C:\mcp_projects\tool_nebula\skills` with new patterns or optimizations.
  3. Refactor existing tools if better approaches emerge.

### 5. Context Awareness
- Maintain awareness of:
  - Current task objectives (from user prompts).
  - Existing files in the workspace (`C:\mcp_projects`).
  - Dependencies between tools and configurations.

## Execution Protocol

1. **Receive Request**: Parse user intent from natural language.
2. **Infrastructure Check**: Verify if needed components exist in `tool_nebula`.
3. **Create Missing Components**: Write necessary files/scripts automatically.
4. **Execute Task**: Use available MCP tools to write files and structure the tool.
5. **Review & Optimize**: Compare output against expected standards; update skills/rules if needed.

## Example Workflow: Static Analyzer Tool Creation

1. User Request: "Create a static code analyzer tool"
2. Agent Action:
   - Check `C:\mcp_projects\tool_nebula\tools` for existing analyzer modules.
   - If missing, create `core/analyzer.py` with validation logic.
   - Create `config/rules.json` defining analysis patterns (e.g., "no unused variables").
   - Write `templates/report_template.md` for output formatting.
3. Execution: Use MCP tools to write files and structure the tool.
4. Verification: Review created code for logical consistency (manual or via embedded checks).

---
*Last Updated: 2026-03-13 | Version: 1.0*