#!/bin/bash
set -e

# Colors for terminal output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}===================================================${NC}"
echo -e "${BLUE}        CloudGraph CLI Installer (Linux Only)       ${NC}"
echo -e "${BLUE}===================================================${NC}"

# Ensure running on Linux
OS=$(uname -s | tr '[:upper:]' '[:lower:]')
if [ "$OS" != "linux" ]; then
    echo -e "${RED}✗ Error: CloudGraph is only supported on Linux.${NC}"
    exit 1
fi

# Detect CPU Architecture
ARCH=$(uname -m)
case "$ARCH" in
    x86_64|amd64)
        BINARY_ARCH="amd64"
        ;;
    aarch64|arm64)
        BINARY_ARCH="arm64"
        ;;
    *)
        echo -e "${RED}✗ Error: Unsupported architecture: $ARCH. Only AMD64 and ARM64 are supported.${NC}"
        exit 1
        ;;
esac

# Define version and download URL
VERSION="v0.1.0"
DOWNLOAD_URL="https://github.com/shivamshashank/CloudGraph/releases/download/${VERSION}/cloudgraph-linux-${BINARY_ARCH}"

echo -e "${BLUE}ℹ Detected Architecture: ${BINARY_ARCH}${NC}"
echo -e "${BLUE}ℹ Downloading CloudGraph ${VERSION}...${NC}"

# Temp download path
TMP_DIR=$(mktemp -d)
TMP_BINARY="${TMP_DIR}/cloudgraph"

# Download the release binary
if command -v curl >/dev/null 2>&1; then
    curl -sSfL "$DOWNLOAD_URL" -o "$TMP_BINARY"
elif command -v wget >/dev/null 2>&1; then
    wget -qO "$TMP_BINARY" "$DOWNLOAD_URL"
else
    echo -e "${RED}✗ Error: Either curl or wget is required to download the binary.${NC}"
    exit 1
fi

# Check download succeeded
if [ ! -f "$TMP_BINARY" ] || [ ! -s "$TMP_BINARY" ]; then
    echo -e "${RED}✗ Error: Failed to download the binary. Please verify the network connection or version release exists.${NC}"
    exit 1
fi

# Setup installation directory
INSTALL_DIR="/usr/local/bin"
TARGET_PATH="${INSTALL_DIR}/cloudgraph"

echo -e "${BLUE}ℹ Installing cloudgraph to ${TARGET_PATH}...${NC}"

# Move to target path and make executable
if [ -w "$INSTALL_DIR" ]; then
    mv "$TMP_BINARY" "$TARGET_PATH"
    chmod +x "$TARGET_PATH"
else
    echo -e "${BLUE}ℹ Root privileges required to write to ${INSTALL_DIR}. Using sudo...${NC}"
    sudo mv "$TMP_BINARY" "$TARGET_PATH"
    sudo chmod +x "$TARGET_PATH"
fi

# Cleanup temp dir
rm -rf "$TMP_DIR"

echo -e "${GREEN}✓ CloudGraph CLI installed successfully!${NC}"
echo -e "${GREEN}✓ You can now run: sudo cloudgraph deploy${NC}"
echo -e "${BLUE}===================================================${NC}"
