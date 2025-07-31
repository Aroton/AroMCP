#!/bin/bash
# Run all AroMCP servers in separate terminals/processes

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Get the directory where the script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"

echo -e "${BLUE}Starting all AroMCP servers...${NC}"

# Check if uv is installed
if ! command -v uv &> /dev/null; then
    echo -e "${RED}Error: uv is not installed. Please install it first.${NC}"
    exit 1
fi

# Function to start a server
start_server() {
    local server_name=$1
    local server_path=$2
    local log_file="$PROJECT_ROOT/logs/${server_name}.log"
    
    mkdir -p "$PROJECT_ROOT/logs"
    
    echo -e "${YELLOW}Starting ${server_name} server...${NC}"
    
    # Start the server in the background
    cd "$server_path" && uv run python main.py > "$log_file" 2>&1 &
    local pid=$!
    
    # Save the PID for later
    echo $pid > "$PROJECT_ROOT/logs/${server_name}.pid"
    
    echo -e "${GREEN}✓ ${server_name} server started (PID: $pid)${NC}"
}

# Start all servers
start_server "filesystem" "$PROJECT_ROOT/servers/filesystem"
start_server "build" "$PROJECT_ROOT/servers/build"
start_server "analysis" "$PROJECT_ROOT/servers/analysis"
start_server "standards" "$PROJECT_ROOT/servers/standards"
start_server "workflow" "$PROJECT_ROOT/servers/workflow"

echo -e "${BLUE}All servers started!${NC}"
echo -e "${BLUE}Logs are available in: $PROJECT_ROOT/logs/${NC}"
echo -e "${BLUE}To stop all servers, run: $SCRIPT_DIR/stop-all-servers.sh${NC}"