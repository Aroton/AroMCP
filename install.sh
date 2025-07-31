#!/bin/bash

# AroMCP Install Script
# Copies shared Claude commands and templates to ~/.claude directory

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if we're in the correct directory
if [[ ! -d "./shared-claude" ]]; then
    print_error "shared-claude directory not found!"
    print_error "Please run this script from the AroMCP project root directory."
    exit 1
fi

print_status "Starting AroMCP installation..."

# Create ~/.claude directory if it doesn't exist
CLAUDE_DIR="$HOME/.claude"
if [[ ! -d "$CLAUDE_DIR" ]]; then
    print_status "Creating ~/.claude directory..."
    mkdir -p "$CLAUDE_DIR"
    print_success "Created ~/.claude directory"
else
    print_status "~/.claude directory already exists"
fi

# Copy AroMCP files to ~/.claude
print_status "Installing AroMCP files..."

# Ensure target directories exist
mkdir -p "$CLAUDE_DIR/commands"
mkdir -p "$CLAUDE_DIR/templates"
mkdir -p "$CLAUDE_DIR/agents"

# Install AroMCP command files
if [[ -d "./shared-claude/commands" ]]; then
    print_status "Installing AroMCP commands..."
    INSTALLED_COMMANDS=0

    # Copy all files from shared-claude/commands to ensure we get everything
    for cmd_file in ./shared-claude/commands/*.md; do
        if [[ -f "$cmd_file" ]]; then
            filename=$(basename "$cmd_file")
            cp "$cmd_file" "$CLAUDE_DIR/commands/"
            echo -e "${GREEN}[SUCCESS]${NC} Installed command: $filename"
            INSTALLED_COMMANDS=$((INSTALLED_COMMANDS + 1))
        fi
    done

    print_success "Installed $INSTALLED_COMMANDS AroMCP command files"
else
    print_warning "No commands directory found in ./shared-claude"
fi

# Install AroMCP template files
if [[ -d "./shared-claude/templates" ]]; then
    print_status "Installing AroMCP templates..."
    INSTALLED_TEMPLATES=0

    # Copy all template files if any exist
    for tpl_file in ./shared-claude/templates/*.md; do
        if [[ -f "$tpl_file" ]]; then
            filename=$(basename "$tpl_file")
            cp "$tpl_file" "$CLAUDE_DIR/templates/"
            echo -e "${GREEN}[SUCCESS]${NC} Installed template: $filename"
            INSTALLED_TEMPLATES=$((INSTALLED_TEMPLATES + 1))
        fi
    done

    if [[ $INSTALLED_TEMPLATES -gt 0 ]]; then
        print_success "Installed $INSTALLED_TEMPLATES AroMCP template files"
    else
        print_status "No template files found to install"
    fi
else
    print_status "No templates directory found in ./shared-claude"
fi

# Install AroMCP agent files
if [[ -d "./shared-claude/agents" ]]; then
    print_status "Installing AroMCP agents..."
    INSTALLED_AGENTS=0

    # Copy all agent files if any exist
    for agent_file in ./shared-claude/agents/*.md; do
        if [[ -f "$agent_file" ]]; then
            filename=$(basename "$agent_file")
            cp "$agent_file" "$CLAUDE_DIR/agents/"
            echo -e "${GREEN}[SUCCESS]${NC} Installed agent: $filename"
            INSTALLED_AGENTS=$((INSTALLED_AGENTS + 1))
        fi
    done

    if [[ $INSTALLED_AGENTS -gt 0 ]]; then
        print_success "Installed $INSTALLED_AGENTS AroMCP agent files"
    else
        print_status "No agent files found to install"
    fi
else
    print_status "No agents directory found in ./shared-claude"
fi

# Install any other AroMCP-specific files/directories (non-commands/templates)
# Only install if they don't conflict with existing files
for item in ./shared-claude/*; do
    if [[ -d "$item" ]]; then
        dirname=$(basename "$item")
        if [[ "$dirname" != "commands" ]] && [[ "$dirname" != "templates" ]] && [[ "$dirname" != "agents" ]]; then
            if [[ ! -d "$CLAUDE_DIR/$dirname" ]]; then
                print_status "Installing additional directory: $dirname"
                cp -r "$item" "$CLAUDE_DIR/"
                print_success "Installed $dirname"
            else
                print_warning "Directory already exists, skipping: $dirname"
                print_status "Use --force flag or manually merge if needed"
            fi
        fi
    elif [[ -f "$item" ]]; then
        filename=$(basename "$item")
        if [[ ! -f "$CLAUDE_DIR/$filename" ]]; then
            print_status "Installing file: $filename"
            cp "$item" "$CLAUDE_DIR/"
            print_success "Installed $filename"
        else
            print_warning "File already exists, skipping: $filename"
            print_status "Use --force flag or manually replace if needed"
        fi
    fi
done

# Set appropriate permissions on installed files only
print_status "Setting file permissions..."
chmod 755 "$CLAUDE_DIR/commands"/standards*.md 2>/dev/null || true
chmod 755 "$CLAUDE_DIR/templates"/*.md 2>/dev/null || true
print_success "File permissions set"

# Installation complete
echo
print_success "🎉 AroMCP installation complete!"
echo
echo "Installation summary:"
echo "  📁 Target directory: $CLAUDE_DIR"

if [[ -d "$CLAUDE_DIR/commands" ]]; then
    FINAL_COMMAND_COUNT=$(find "$CLAUDE_DIR/commands" -name "*.md" | wc -l)
    echo "  📋 Commands installed: $FINAL_COMMAND_COUNT"
fi

if [[ -d "$CLAUDE_DIR/templates" ]]; then
    FINAL_TEMPLATE_COUNT=$(find "$CLAUDE_DIR/templates" -name "*.md" | wc -l)
    echo "  📄 Templates installed: $FINAL_TEMPLATE_COUNT"
fi

if [[ -d "$CLAUDE_DIR/agents" ]]; then
    FINAL_AGENT_COUNT=$(find "$CLAUDE_DIR/agents" -name "*.md" | wc -l)
    echo "  🤖 Agents installed: $FINAL_AGENT_COUNT"
fi

echo
print_status "You can now use AroMCP commands with Claude Code!"
print_status "Available AroMCP commands:"

# Show all installed command files
for cmd_file in "$CLAUDE_DIR/commands"/standards*.md; do
    if [[ -f "$cmd_file" ]]; then
        cmd_name=$(basename "$cmd_file" .md)
        echo "  • claude $cmd_name"
    fi
done

echo
print_status "For help with any command, use: claude <command-name> --help"