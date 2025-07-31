#!/usr/bin/env python3
"""Health check script for AroMCP servers."""

import json
import subprocess
import sys
from pathlib import Path
from typing import Dict, Any

# Colors for terminal output
RED = '\033[0;31m'
GREEN = '\033[0;32m'
YELLOW = '\033[1;33m'
BLUE = '\033[0;34m'
NC = '\033[0m'  # No Color

def get_project_root() -> Path:
    """Get the project root directory."""
    return Path(__file__).parent.parent

def check_server_process(server_name: str) -> Dict[str, Any]:
    """Check if a server process is running."""
    pid_file = get_project_root() / "logs" / f"{server_name}.pid"
    
    if not pid_file.exists():
        return {"running": False, "pid": None, "status": "No PID file"}
    
    try:
        with open(pid_file) as f:
            pid = int(f.read().strip())
        
        # Check if process is running
        import os
        import signal
        
        try:
            os.kill(pid, 0)  # Signal 0 doesn't kill, just checks
            return {"running": True, "pid": pid, "status": "Running"}
        except OSError:
            return {"running": False, "pid": pid, "status": "Process not found (stale PID)"}
    except Exception as e:
        return {"running": False, "pid": None, "status": f"Error: {e}"}

def check_server_dependencies(server_name: str) -> Dict[str, Any]:
    """Check if server dependencies are installed."""
    server_path = get_project_root() / "servers" / server_name
    pyproject_file = server_path / "pyproject.toml"
    
    if not pyproject_file.exists():
        return {"valid": False, "message": "No pyproject.toml found"}
    
    # Try to import the server
    try:
        cmd = ["python", "-c", f"from aromcp.{server_name}_server.server import mcp; print('OK')"]
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=get_project_root())
        
        if result.returncode == 0 and "OK" in result.stdout:
            return {"valid": True, "message": "Dependencies OK"}
        else:
            return {"valid": False, "message": f"Import failed: {result.stderr}"}
    except Exception as e:
        return {"valid": False, "message": f"Check failed: {e}"}

def check_server_config(server_name: str) -> Dict[str, Any]:
    """Check server configuration."""
    config_file = get_project_root() / ".aromcp" / "servers" / f"{server_name}.yaml"
    
    if config_file.exists():
        return {"exists": True, "path": str(config_file)}
    else:
        return {"exists": False, "path": str(config_file)}

def print_server_status(server_name: str, status: Dict[str, Any]):
    """Print server status in a formatted way."""
    print(f"\n{BLUE}{'='*50}{NC}")
    print(f"{BLUE}{server_name.upper()} SERVER{NC}")
    print(f"{BLUE}{'='*50}{NC}")
    
    # Process status
    process = status["process"]
    if process["running"]:
        print(f"Process: {GREEN}✓ Running (PID: {process['pid']}){NC}")
    else:
        print(f"Process: {RED}✗ {process['status']}{NC}")
    
    # Dependencies status
    deps = status["dependencies"]
    if deps["valid"]:
        print(f"Dependencies: {GREEN}✓ {deps['message']}{NC}")
    else:
        print(f"Dependencies: {RED}✗ {deps['message']}{NC}")
    
    # Config status
    config = status["config"]
    if config["exists"]:
        print(f"Config: {GREEN}✓ Found at {config['path']}{NC}")
    else:
        print(f"Config: {YELLOW}⚠ Not found (optional){NC}")
    
    # Overall health
    if process["running"] and deps["valid"]:
        print(f"Health: {GREEN}✓ HEALTHY{NC}")
    elif deps["valid"]:
        print(f"Health: {YELLOW}⚠ NOT RUNNING (dependencies OK){NC}")
    else:
        print(f"Health: {RED}✗ UNHEALTHY{NC}")

def main():
    """Main health check function."""
    servers = ["filesystem", "build", "analysis", "standards", "workflow"]
    
    print(f"{BLUE}AroMCP Server Health Check{NC}")
    print(f"{BLUE}{'='*50}{NC}")
    
    all_healthy = True
    
    for server in servers:
        status = {
            "process": check_server_process(server),
            "dependencies": check_server_dependencies(server),
            "config": check_server_config(server)
        }
        
        print_server_status(server, status)
        
        if not (status["process"]["running"] and status["dependencies"]["valid"]):
            all_healthy = False
    
    print(f"\n{BLUE}{'='*50}{NC}")
    if all_healthy:
        print(f"{GREEN}✓ All servers are healthy!{NC}")
        return 0
    else:
        print(f"{YELLOW}⚠ Some servers need attention{NC}")
        print(f"\nTo start all servers: {BLUE}./scripts/run-all-servers.sh{NC}")
        print(f"To start a specific server: {BLUE}./scripts/run-server.sh <server-name>{NC}")
        return 1

if __name__ == "__main__":
    sys.exit(main())