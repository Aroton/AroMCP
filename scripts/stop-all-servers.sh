#!/bin/bash
# Stop all running AroMCP servers

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Get the directory where the script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"

echo -e "${BLUE}Stopping all AroMCP servers...${NC}"

# Function to stop a server
stop_server() {
    local server_name=$1
    local pid_file="$PROJECT_ROOT/logs/${server_name}.pid"
    
    if [ -f "$pid_file" ]; then
        local pid=$(cat "$pid_file")
        if kill -0 $pid 2>/dev/null; then
            echo -e "${YELLOW}Stopping ${server_name} server (PID: $pid)...${NC}"
            kill $pid
            rm -f "$pid_file"
            echo -e "${GREEN}✓ ${server_name} server stopped${NC}"
        else
            echo -e "${YELLOW}${server_name} server not running (stale PID file)${NC}"
            rm -f "$pid_file"
        fi
    else
        echo -e "${YELLOW}${server_name} server not running (no PID file)${NC}"
    fi
}

# Stop all servers
stop_server "filesystem"
stop_server "build"
stop_server "analysis"
stop_server "standards"
stop_server "workflow"

echo -e "${BLUE}All servers stopped!${NC}"