#!/usr/bin/env bash
set -euo pipefail

# CloudGraph installation script
# Installs the CloudGraph CLI via curl so the `cloudgraph` command works immediately.

CLOUDGRAPH_VERSION="${CLOUDGRAPH_VERSION:-0.1.0}"
CLOUDGRAPH_REPO_URL="${CLOUDGRAPH_REPO_URL:-https://raw.githubusercontent.com/shivamshashank/CloudGraph/main}"
CLOUDGRAPH_INSTALL_DIR="${CLOUDGRAPH_INSTALL_DIR:-}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

print_header() {
    echo -e "${BLUE}===================================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}===================================================${NC}"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ $1${NC}"
}

command_exists() {
    command -v "$1" >/dev/null 2>&1
}

resolve_install_dir() {
    if [[ -n "$CLOUDGRAPH_INSTALL_DIR" ]]; then
        mkdir -p "$CLOUDGRAPH_INSTALL_DIR"
        echo "$CLOUDGRAPH_INSTALL_DIR"
        return 0
    fi

    if [[ -w /usr/local/bin ]]; then
        echo "/usr/local/bin"
    else
        mkdir -p "$HOME/.local/bin"
        echo "$HOME/.local/bin"
    fi
}

ensure_shell_path() {
    local install_dir="$1"
    local profile_file=""

    if [[ "$install_dir" != "$HOME/.local/bin" ]]; then
        return 0
    fi

    if [[ -f "$HOME/.zshrc" ]]; then
        profile_file="$HOME/.zshrc"
    elif [[ -f "$HOME/.bashrc" ]]; then
        profile_file="$HOME/.bashrc"
    elif [[ -f "$HOME/.profile" ]]; then
        profile_file="$HOME/.profile"
    else
        profile_file="$HOME/.zshrc"
    fi

    # shellcheck disable=SC2016
    local export_line='export PATH="$HOME/.local/bin:$PATH"'
    if ! grep -Fq "$export_line" "$profile_file" 2>/dev/null; then
        echo "$export_line" >> "$profile_file"
        print_info "Added $install_dir to $profile_file"
    fi
}

install_cloudgraph_cli() {
    print_header "Installing CloudGraph CLI"

    if ! command_exists curl; then
        print_error "curl is required"
        exit 1
    fi

    local install_dir
    install_dir=$(resolve_install_dir)
    local target="$install_dir/cloudgraph"
    local local_script="$SCRIPT_DIR/cloudgraph"

    if [[ -f "$local_script" ]]; then
        print_info "Using local CloudGraph CLI script from $local_script"
        cp "$local_script" "$target"
    else
        print_info "Downloading CloudGraph CLI to $target"
        curl -fsSL "${CLOUDGRAPH_REPO_URL%/}/cloudgraph" -o "$target"
    fi

    chmod +x "$target"

    ensure_shell_path "$install_dir"

    print_success "CloudGraph CLI installed"
}

print_summary() {
    print_header "Installation Complete"
    echo ""
    echo "CloudGraph CLI is ready. Try:"
    echo "  cloudgraph --help"
    echo "  cloudgraph version"
    echo "  cloudgraph health http://localhost:8000"
    echo ""
}

main() {
    print_header "CloudGraph Installation"
    print_info "Version: $CLOUDGRAPH_VERSION"
    echo ""
    install_cloudgraph_cli
    print_summary
}

main "$@"
