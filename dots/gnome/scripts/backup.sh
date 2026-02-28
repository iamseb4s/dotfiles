#!/usr/bin/env bash

# Resolve paths
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../../" && pwd)"
DCONF_DIR="$REPO_ROOT/dots/gnome/dconf"

mkdir -p "$DCONF_DIR"

# Categories Definition
declare -A CATEGORIES
CATEGORIES=(
    ["Shell"]="/org/gnome/shell/"
    ["Extensions"]="/org/gnome/shell/extensions/"
    ["Appearance"]="/org/gnome/desktop/interface/"
    ["Window Manager"]="/org/gnome/mutter/"
    ["Keybindings"]="/org/gnome/desktop/wm/keybindings/ /org/gnome/settings-daemon/plugins/media-keys/ /org/gnome/shell/keybindings/"
    ["Privacy & Search"]="/org/gnome/desktop/privacy/ /org/gnome/desktop/search-providers/"
    ["System"]="/org/gnome/settings-daemon/plugins/power/ /org/gnome/settings-daemon/plugins/color/"
    ["Nautilus"]="/org/gnome/nautilus/"
)

# Descriptions for each category
declare -A DESCRIPTIONS
DESCRIPTIONS=(
    ["All"]="Backup all available categories"
    ["Shell"]="Favorite apps, enabled extensions, and UI layout"
    ["Extensions"]="Internal settings for all physically installed extensions"
    ["Appearance"]="GTK theme, icons, fonts, and accent color"
    ["Window Manager"]="Mutter settings and window management behavior"
    ["Keybindings"]="System shortcuts, media keys, and shell bindings"
    ["Privacy & Search"]="Usage history, search providers, and privacy settings"
    ["System"]="Power management, sleep timeouts, and night light"
    ["Nautilus"]="File manager preferences and view settings"
)

# Create a sorted list of labels
mapfile -t LABELS < <(printf "%s\n" "${!CATEGORIES[@]}" | sort)
OPTIONS=("All" "${LABELS[@]}")
SELECTED=()
for i in "${!OPTIONS[@]}"; do SELECTED[i]=0; done

CURSOR=0

# UI Drawing function
draw_menu() {
    echo -ne "\033[H\033[J" # Clear screen and move to top
    echo -e "\033[1;34mGNOME Backup System\033[0m"
    echo -e "Interactive script to backup your GNOME desktop configurations.\n"
    
    for i in "${!OPTIONS[@]}"; do
        prefix="  "
        [[ $i -eq $CURSOR ]] && prefix="> "
        
        symbol="[ ]"
        [[ ${SELECTED[$i]} -eq 1 ]] && symbol="[\033[1;32m■\033[0m]"
        
        label="${OPTIONS[$i]}"
        if [[ $i -eq $CURSOR ]]; then
            echo -e "$prefix$symbol \033[7m $label \033[0m  \033[2m${DESCRIPTIONS[$label]}\033[0m"
        else
            echo -e "$prefix$symbol $label"
        fi
    done
    
    echo -e "\n\033[2mEsc cancel  -  up/down move  -  Space toggle  -  Enter accept\033[0m"
}

# Function to get physically installed extension IDs
get_installed_extensions() {
    local ext_dirs=(
        "$HOME/.local/share/gnome-shell/extensions"
        "/usr/share/gnome-shell/extensions"
    )
    local installed=""
    for dir in "${ext_dirs[@]}"; do
        if [[ -d "$dir" ]]; then
            installed+="$(ls "$dir") "
        fi
    done
    echo "$installed"
}

# Function to perform dconf dump
do_backup() {
    local label=$1
    local paths=${CATEGORIES[$label]}
    local filename="${label,,}"
    filename="${filename// /_}"
    filename="${filename//&/and}"
    local output_file="$DCONF_DIR/${filename}.dconf"
    
    local temp_raw=$(mktemp)

    for path in $paths; do
        local clean_path="${path#/}"; clean_path="${clean_path%/}"
        echo "PATH_MARKER:$clean_path" >> "$temp_raw"
        dconf dump "$path" >> "$temp_raw"
        echo "" >> "$temp_raw"
    done

    local installed_ids=$(get_installed_extensions)
    
    # Process with Python for perfect formatting and filtering
    python3 -c "
import sys, re

installed = set(sys.argv[1].split())
label = sys.argv[3]

with open(sys.argv[2], 'r') as f:
    content = f.read()

path_chunks = content.split('PATH_MARKER:')
final_blocks = []
enabled_ids_in_dump = set()

# First pass to find enabled extensions in the dump content
if label == 'Shell':
    for chunk in path_chunks:
        if not chunk.strip(): continue
        lines = chunk.split('\n', 1)
        if lines[0].strip() == 'org/gnome/shell':
            e_match = re.search(r'enabled-extensions=\[(.*?)\]', lines[1])
            if e_match:
                enabled_ids_in_dump = set(re.findall(r\"'([^']+)'\", e_match.group(1)))

# Second pass: process and filter
for chunk in path_chunks:
    if not chunk.strip(): continue
    lines = chunk.split('\n', 1)
    base_path = lines[0].strip()
    raw_blocks = re.split(r'\n(?=\[)', lines[1].strip())
    
    for block in raw_blocks:
        if not block.strip(): continue
        block_lines = [l.strip() for l in block.strip().split('\n') if l.strip()]
        if not block_lines: continue
        
        # Fix header
        header_raw = block_lines[0].strip('[]')
        if header_raw == '/':
            header = f'[{base_path}]'
        else:
            header = f'[{base_path}/{header_raw.lstrip(\"/\")}]'
        
        if label == 'Shell' and any(header.startswith(f'[{x}') for x in ['org/gnome/shell/extensions', 'org/gnome/shell/keybindings', 'org/gnome/shell/weather', 'org/gnome/shell/world-clocks']):
            continue
        
        new_lines = [header]
        for line in block_lines[1:]:
            if label == 'Shell' and line.startswith('enabled-extensions='):
                items = re.findall(r\"'([^']+)'\", line)
                # Keep only physically installed
                filtered = [f\"'{x}'\" for x in items if x in installed]
                new_lines.append(f\"enabled-extensions=[{', '.join(filtered)}]\")
            elif label == 'Shell' and line.startswith('disabled-extensions='):
                items = re.findall(r\"'([^']+)'\", line)
                # Keep if installed AND NOT garbage AND NOT in enabled list
                filtered = [f\"'{x}'\" for x in items if x in installed and x not in enabled_ids_in_dump]
                new_lines.append(f\"disabled-extensions=[{', '.join(filtered)}]\")
            else:
                new_lines.append(line)
        
        # Keep block if it has content or is the main Shell block
        if len(new_lines) > 1 or (label == 'Shell' and header == '[org/gnome/shell]'):
            final_blocks.append('\n'.join(new_lines))

if final_blocks:
    sys.stdout.write('\n\n'.join(final_blocks).strip() + '\n')
" "$installed_ids" "$temp_raw" "$label" > "$output_file"

    rm "$temp_raw"
}

# Terminal setup
tput civis # Hide cursor
trap 'tput cnorm; echo -e "\nInterrupted."; exit 1' INT TERM

# Main interaction loop
while true; do
    draw_menu
    IFS= read -rsn1 key
    
    case "$key" in
        $'\x1b') # Handle Escape or Arrow Keys
            read -rsn2 -t 0.01 next_key
            if [[ -z "$next_key" ]]; then # Pure Escape
                tput cnorm; echo -e "\n\033[1;31mOperation cancelled.\033[0m"; exit 0
            elif [[ "$next_key" == "[A" ]]; then # Up
                ((CURSOR--)); [[ $CURSOR -lt 0 ]] && CURSOR=$((${#OPTIONS[@]} - 1))
            elif [[ "$next_key" == "[B" ]]; then # Down
                ((CURSOR++)); [[ $CURSOR -ge ${#OPTIONS[@]} ]] && CURSOR=0
            fi
            ;;
        " ") # Toggle selection
            if [[ $CURSOR -eq 0 ]]; then # Toggle "All"
                new_state=$((1 - SELECTED[0]))
                for i in "${!SELECTED[@]}"; do SELECTED[$i]=$new_state; done
            else
                SELECTED[$CURSOR]=$((1 - SELECTED[$CURSOR]))
                all_set=1
                for i in $(seq 1 $((${#OPTIONS[@]} - 1))); do
                    [[ ${SELECTED[$i]} -eq 0 ]] && all_set=0
                done
                SELECTED[0]=$all_set
            fi
            ;;
        $'\n'|""|$'\r') # Enter
            break
            ;;
    esac
done

tput cnorm # Show cursor
echo -ne "\n"

# Process selection
HAS_BACKUP=0
for i in $(seq 1 $((${#OPTIONS[@]} - 1))); do
    if [[ ${SELECTED[$i]} -eq 1 ]]; then
        do_backup "${OPTIONS[$i]}"
        HAS_BACKUP=1
    fi
done

[[ $HAS_BACKUP -eq 0 ]] && echo "No categories selected." || echo -e "\n\033[1;34mBackup completed successfully!\033[0m"
