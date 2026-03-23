#!/usr/bin/env python3
"""
The Weaver - Windows Task Scheduler Wrapper (Python)
Esegue synapse_runner.py in background con gestione avanzata errori
"""

import subprocess
import sys
import os
from datetime import datetime
import logging

# Configurazione percorsi
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SYNAPSE_SCRIPT = os.path.join(BASE_DIR, '..', 'core', 'synapse_runner.py')
LOG_DIR = os.path.join(BASE_DIR, 'logs')
LOG_FILE = os.path.join(LOG_DIR, f'scheduler_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')

# Configurazione logger
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

def main():
    """Esegue synapse_runner.py in background"""
    
    logger.info("=" * 60)
    logger.info("The Weaver Scheduler - Starting")
    logger.info(f"Working Directory: {os.getcwd()}")
    logger.info(f"Synapse Script: {SYNAPSE_SCRIPT}")
    logger.info("=" * 60)
    
    # Verifica script esiste
    if not os.path.exists(SYNAPSE_SCRIPT):
        logger.error(f"ERROR: Synapse script not found at {SYNAPSE_SCRIPT}")
        sys.exit(1)
    
    try:
        # Esegue MCP server in background (headless mode)
        process = subprocess.Popen(
            [sys.executable, SYNAPSE_SCRIPT],
            cwd=BASE_DIR,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True
        )
        
        logger.info("Starting synapse_runner.py in background...")
        
        # Monitora output per primi 30 secondi (timeout safety)
        for line in process.stdout:
            if 'error' in line.lower() or 'exception' in line.lower():
                logger.warning(f"Potential error detected: {line.strip()}")
            
            if process.poll() is not None:
                break
        
        # Attendi terminazione processo
        stdout, _ = process.communicate(timeout=30)
        
        if process.returncode == 0:
            logger.info("✓ synapse_runner.py completed successfully")
        else:
            logger.error(f"✗ synapse_runner.py exited with code {process.returncode}")
            
    except subprocess.TimeoutExpired:
        logger.error("ERROR: Process timed out after 30 seconds. Terminating...")
        process.kill()
        sys.exit(1)
    except Exception as e:
        logger.exception(f"ERROR: Unexpected exception - {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
