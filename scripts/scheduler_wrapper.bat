@echo off
REM ============================================
REM The Weaver - Windows Task Scheduler Wrapper
REM Esegue synapse_runner.py in background headless
REM ============================================

setlocal enabledelayedexpansion

REM Percorsi configurabili
set "SYNAPSE_SCRIPT=C:\mcp_projects\tool_nebula\core\synapse_runner.py"
set "LOG_DIR=C:\mcp_projects\tool_nebula\logs"
set "WORKING_DIR=%~dp0"

REM Crea directory log se non esiste
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

echo [INFO] Starting The Weaver scheduler... > "%LOG_DIR%\scheduler.log"
echo [INFO] Working directory: %WORKING_DIR% >> "%LOG_DIR%\scheduler.log"

REM Esegue MCP server in background (headless mode)
python "%SYNAPSE_SCRIPT%" --headless >> "%LOG_DIR%\scheduler.log" 2>&1

if errorlevel 1 (
    echo [ERROR] synapse_runner.py exited with error code %errorlevel% >> "%LOG_DIR%\scheduler.log"
    exit /b 1
) else (
    echo [SUCCESS] synapse_runner.py completed successfully >> "%LOG_DIR%\scheduler.log"
)

echo [INFO] Scheduler wrapper finished. >> "%LOG_DIR%\scheduler.log"
pause >nul
