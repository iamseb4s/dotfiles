#!/usr/bin/env bash

# ==============================================================================
# Dotfiles Bootstrap Script
# Ensures Python 3 is installed and launches the main installer.
# ==============================================================================

set -e # Exit immediately if a command exits with a non-zero status.

# Colors
C_RESET='\033[0m'
C_GREEN='\033[0;32m'
C_BLUE='\033[0;34m'
C_RED='\033[0;31m'

info() { echo -e "${C_BLUE}INFO: $1${C_RESET}"; }
success() { echo -e "${C_GREEN}SUCCESS: $1${C_RESET}"; }
error() { echo -e "${C_RED}ERROR: $1${C_RESET}"; }

# Check for Python 3
if ! command -v python3 &> /dev/null; then
    info "Python 3 not found. Attempting to install..."
    
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        case "$ID" in
            arch|manjaro)
                info "Detected Arch Linux. Installing 'python'..."
                sudo pacman -Sy --noconfirm python
                ;;
            ubuntu|debian|pop)
                info "Detected Debian/Ubuntu. Installing 'python3'..."
                sudo apt-get update && sudo apt-get install -y python3
                ;;
            *)
                error "Unsupported distribution '$ID' for automatic Python installation."
                echo "Please install Python 3 manually and try again."
                exit 1
                ;;
        esac
    else
        error "Cannot detect OS distribution. Install Python 3 manually."
        exit 1
    fi
    success "Python 3 installed successfully."
else
    info "Python 3 is already installed."
fi

# Launch the main Python installer
info "Launching installer..."
python3 install.py "$@"
