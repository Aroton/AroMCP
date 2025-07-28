#!/bin/bash
# Run a specific AroMCP server

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Get the directory where the script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"

# Check arguments
if [ $# -eq 0 ]; then
    echo -e "${RED}Error: No server specified${NC}"
    echo "Usage: $0 <server-name> [--background]"
    echo "Available servers: filesystem, build, analysis, standards, workflow"
    exit 1
fi

SERVER_NAME=$1
BACKGROUND=false

if [ "$2" == "--background" ]; then
    BACKGROUND=true
fi

# Map server names to paths
case $SERVER_NAME in
    filesystem|fs)
        SERVER_PATH="$PROJECT_ROOT/servers/filesystem"
        SERVER_NAME="filesystem"
        ;;
    build)
        SERVER_PATH="$PROJECT_ROOT/servers/build"
        ;;
    analysis)
        SERVER_PATH="$PROJECT_ROOT/servers/analysis"
        ;;
    standards|std)
        SERVER_PATH="$PROJECT_ROOT/servers/standards"
        SERVER_NAME="standards"
        ;;
    workflow|wf)
        SERVER_PATH="$PROJECT_ROOT/servers/workflow"
        SERVER_NAME="workflow"
        ;;
    *)
        echo -e "${RED}Error: Unknown server '$SERVER_NAME'${NC}"
        echo "Available servers: filesystem, build, analysis, standards, workflow"
        exit 1
        ;;
esac

# Check if uv is installed
if ! command -v uv &> /dev/null; then
    echo -e "${RED}Error: uv is not installed. Please install it first.${NC}"
    exit 1
fi

# Check if server directory exists
if [ ! -d "$SERVER_PATH" ]; then
    echo -e "${RED}Error: Server directory not found: $SERVER_PATH${NC}"
    exit 1
fi

if [ "$BACKGROUND" == true ]; then
    # Run in background
    mkdir -p "$PROJECT_ROOT/logs"
    LOG_FILE="$PROJECT_ROOT/logs/${SERVER_NAME}.log"
    
    echo -e "${YELLOW}Starting ${SERVER_NAME} server in background...${NC}"
    cd "$SERVER_PATH" && uv run python main.py > "$LOG_FILE" 2>&1 &
    PID=$!
    
    # Save the PID
    echo $PID > "$PROJECT_ROOT/logs/${SERVER_NAME}.pid"
    
    echo -e "${GREEN}✓ ${SERVER_NAME} server started (PID: $PID)${NC}"
    echo -e "${BLUE}Logs: $LOG_FILE${NC}"
else
    # Run in foreground
    echo -e "${YELLOW}Starting ${SERVER_NAME} server...${NC}"
    cd "$SERVER_PATH" && uv run python main.py
fi