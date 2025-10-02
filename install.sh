#!/usr/bin/env bash

# ===============================================================
# Dotfiles Installation Script
# ===============================================================

# --- Output colors ---
C_RESET='\033[0m'
C_RED='\033[0;31m'
C_GREEN='\033[0;32m'
C_BLUE='\033[0;34m'
C_YELLOW='\033[0;33m'

# --- Helper functions ---
info() { echo -e "${C_BLUE}INFO: $1${C_RESET}"; }
success() { echo -e "${C_GREEN}SUCCESS: $1${C_RESET}"; }
error() { echo -e "${C_RED}ERROR: $1${C_RESET}"; }
warning() { echo -e "${C_YELLOW}WARNING: $1${C_RESET}"; }

# --- Dotfiles Packages and their System Dependencies Definition ---
declare -A DOTFILE_PACKAGES
DOTFILE_PACKAGES=(
    ["refind"]="refind gdisk:arch,ubuntu"
)

# --- Install mandatory base packages ---
install_mandatory_packages() {
    info "Installing mandatory dependencies: git, nano, gnu-stow..."
    if [ -f /etc/os-release ]; then . /etc/os-release; else error "Cannot detect distribution."; exit 1; fi

    case "$ID" in
        "arch")
            # Using 'yes |' to automatically confirm any prompts from pacman
            yes | sudo pacman -Syu --needed git nano stow
            ;;
        "ubuntu"|"debian")
            sudo apt-get update && sudo apt-get install -y git nano stow
            ;;
        *)
            error "Distribution '$ID' is not supported."; exit 1
            ;;
    esac
    success "Mandatory dependencies installed."
}

# --- Show the menu and capture user selection ---
show_menu() {
    info "Select the dotfiles you want to install."
    
    local indexed_packages=()
    mapfile -t indexed_packages < <(printf "%s\n" "${!DOTFILE_PACKAGES[@]}" | sort)

    while true; do
        echo "----------------------------------------"
        echo "Enter numbers separated by spaces (e.g., 1 3), or 'all'."
        echo "Press ENTER to finish selection."
        echo "----------------------------------------"
        echo "[all] Install ALL available packages"
        
        for i in "${!indexed_packages[@]}"; do
            echo "[$((i+1))] ${indexed_packages[i]}"
        done
        echo "----------------------------------------"

        read -p "Your selection: " user_choice
        
        if [[ "$user_choice" == "all" ]]; then
            SELECTIONS=$(printf "%s\n" "${indexed_packages[@]}")
            break
        fi
        if [[ -z "$user_choice" ]]; then error "No selection was made. Aborting."; exit 1; fi

        local selections_arr=()
        local valid_selection=true
        for choice in $user_choice; do
            if [[ "$choice" =~ ^[0-9]+$ ]] && (( choice > 0 && choice <= ${#indexed_packages[@]} )); then
                selections_arr+=("${indexed_packages[choice-1]}")
            else
                error "Invalid selection: '$choice'. Please try again."; valid_selection=false; break
            fi
        done

        if $valid_selection; then
            SELECTIONS=$(printf "%s\n" "${selections_arr[@]}" | sort -u); break
        fi
    done

    if [ -z "$SELECTIONS" ]; then error "No packages were selected. Aborting."; exit 1; fi
    (info "The following will be installed:"; echo "$SELECTIONS" | awk '{printf "- %s\n", $0}')
}
    
# --- Install dependencies for the selected packages ---
install_selected_dependencies() {
    local packages_to_install=()
    for selection in $SELECTIONS; do
        local deps_string="${DOTFILE_PACKAGES[$selection]%:*}"
        [[ -n "$deps_string" ]] && packages_to_install+=($deps_string)
    done
    
    if [ ${#packages_to_install[@]} -eq 0 ]; then info "No additional dependencies to install."; return; fi
    
    local unique_packages=$(printf "%s\n" "${packages_to_install[@]}" | sort -u | tr '\n' ' ')
    info "Installing selected dependencies: $unique_packages"
    
    . /etc/os-release
    case "$ID" in
        "arch")
            yes | sudo pacman -S --needed $unique_packages
            ;;
        "ubuntu"|"debian")
            sudo apt-get install -y $unique_packages
            ;;
    esac
    success "Selected dependencies installed."
}

# --- Deploy dotfiles using Stow (and special cases) ---
deploy_dotfiles() {
    info "Deploying dotfiles..."
    local dotfiles_source_dir="dots"
    local stow_packages=()
    for selection in $SELECTIONS; do
        if [ "$selection" == "refind" ]; then
            warning "Handling special case: rEFInd."
            local root_device
            root_device=$(findmnt -n -o SOURCE /)
            
            # Check if we are in a Docker/virtual environment where refind-install cannot work
            if [[ "$root_device" == "overlay" ]] || [[ ! -b "$root_device" ]]; then
                warning "Docker/virtual environment detected. 'refind-install' cannot be run."
                info "This step will be skipped during testing. On a real machine, it would run."
            else
                # This is the logic for a real machine installation
                info "Running the official refind-install script..."
                if sudo refind-install; then
                    info "Replacing default refind.conf with custom template..."
                    local root_partuuid
                    root_partuuid=$(lsblk -no PARTUUID "$root_device")
                    if [ -z "$root_partuuid" ]; then error "Could not detect root PARTUUID."; continue; fi
                    success "Detected root PARTUUID: $root_partuuid"
                    
                    local refind_template_path="$dotfiles_source_dir/refind/refind.conf"
                    local refind_dest_path="/boot/EFI/refind/refind.conf"
                    sed "s/__ROOT_PARTUUID__/$root_partuuid/" "$refind_template_path" | sudo tee "$refind_dest_path" > /dev/null
                    success "Custom rEFInd configuration with correct PARTUUID deployed."
                else
                    error "refind-install script failed. Aborting rEFInd setup."
                fi
            fi
        else
            stow_packages+=("$selection")
        fi
    done
    
    if [ ${#stow_packages[@]} -gt 0 ]; then
        info "Running stow for: ${stow_packages[*]}"
        stow --dir="$dotfiles_source_dir" --target=$HOME -S "${stow_packages[@]}"
        success "Symlinks created with Stow."
    fi
}

# --- Clean up installation residue ---
cleanup() {
    info "Cleaning up package cache..."
    . /etc/os-release
    case "$ID" in
        "arch")
            yes | sudo pacman -Scc
            ;;
        "ubuntu"|"debian")
            sudo apt-get autoremove -y && sudo apt-get clean
            ;;
    esac
    success "Cleanup finished."
}

# --- Main function to orchestrate everything ---
main() {
    clear
    install_mandatory_packages
    show_menu
    install_selected_dependencies
    deploy_dotfiles
    cleanup
    echo
    success "ALL DONE! Your environment has been configured."
    info "You may need to restart your session for all changes to take effect."
}

main