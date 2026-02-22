# ============================
# Powerlevel10k Instant Prompt
# ============================
if [[ -r "${XDG_CACHE_HOME:-$HOME/.cache}/p10k-instant-prompt-${(%):-%n}.zsh" ]]; then
  source "${XDG_CACHE_HOME:-$HOME/.cache}/p10k-instant-prompt-${(%):-%n}.zsh"
fi


# ======================
# Helper Functions
# ======================
# Append to PATH only if directory exists and isn't already there
path_append() {
    if [[ -d "$1" ]] && [[ ":$PATH:" != *":$1:"* ]]; then
        export PATH="${PATH:+"$PATH:"}$1"
    fi
}

# Prepend to PATH only if directory exists and isn't already there
path_prepend() {
    if [[ -d "$1" ]] && [[ ":$PATH:" != *":$1:"* ]]; then
        export PATH="$1${PATH:+":$PATH"}"
    fi
}


# ======================
# Oh-My-Zsh Configuration
# ======================
export ZSH="$HOME/.oh-my-zsh"

if [[ -d "$ZSH" ]]; then
    zstyle ':omz:update' mode auto
    zstyle ':omz:update' frequency 7
    
    # 1. Base Plugins
    plugins=(gitfast gh history ssh sudo)
    
    # 2. Dynamic Plugin Detection
    [[ -d "$ZSH/custom/plugins/zsh-autosuggestions" ]] && plugins+=(zsh-autosuggestions)
    [[ -d "$ZSH/custom/plugins/zsh-syntax-highlighting" ]] && plugins+=(zsh-syntax-highlighting)
    
    # 3. Theme Configuration
    if [[ -d "$ZSH/custom/themes/powerlevel10k" ]]; then
        ZSH_THEME="powerlevel10k/powerlevel10k"
        [[ ! -f ~/.p10k.zsh ]] || source ~/.p10k.zsh
    else
        ZSH_THEME="robbyrussell"
    fi

    # 4. Load Oh-My-Zsh
    source $ZSH/oh-my-zsh.sh

    # 5. Load Syntax Highlighting Theme (Catppuccin)
    SYNTAX_THEME="$ZSH/custom/plugins/zsh-syntax-highlighting/themes/catppuccin_mocha-zsh-syntax-highlighting.zsh"
    [[ -f "$SYNTAX_THEME" ]] && source "$SYNTAX_THEME"
else
    # Fallback prompt if OMZ is missing
    PROMPT="%n@%m:%~%# "
fi


# ======================
# Environment & Tools
# ======================
# Standard paths
path_prepend "/usr/local/bin"
path_prepend "/usr/local/sbin"

# Tool-specific paths
path_prepend "$HOME/anaconda3/bin"
path_prepend "$HOME/.npm-global/bin"
path_prepend "$HOME/.bun/bin"
path_prepend "$HOME/.opencode/bin"
path_prepend "$HOME/.spicetify"
path_prepend "$HOME/.fzf/bin"

# Environment Variables
export BUN_INSTALL="$HOME/.bun"
export FZF_DEFAULT_OPTS_FILE="$HOME/.config/fzf/fzf.conf"
export FZF_DEFAULT_OPTS="--bind='focus:'"

# Preferred editor
if [[ -n $SSH_CONNECTION ]]; then
  export EDITOR='nvim'
else
  export EDITOR='code --wait'
fi


# ======================
# Aliases
# ======================

alias c="clear"

# --- System & Config ---
alias zshconfig="nvim ~/.zshrc"
alias ohmyzsh="nvim ~/.oh-my-zsh"
alias hyprconfig='[ -f ~/.config/hypr/hyprland.conf ] && nvim ~/.config/hypr/hyprland.conf || echo "Error: File ~/.config/hypr/hyprland.conf does not exist"'

# --- Package Manager (Distribution-aware) ---
if command -v pacman >/dev/null 2>&1; then
    # Arch Linux
    alias pacu="sudo pacman -Syu"
    alias paci="sudo pacman -S"
    alias pacr="sudo pacman -Rs"
    alias pacc="sudo pacman -Sc && pacman -Rns $(pacman -Qtdq 2>/dev/null || echo '')"
    alias pacq='pacman -Qq | fzf --preview="pacman -Qi {}"'
    alias pacs='pacman -Slq | fzf --preview="pacman -Si {}"'
    
    # AUR (yay)
    if command -v yay >/dev/null 2>&1; then
        alias yayu="yay -Syu"
        alias yayi="yay -S"
        alias yayr="yay -Rs"
        alias yayc="yay -Yc"
        alias yayq='yay -Qq | fzf --preview="yay -Qi {}"'
        alias yays='yay -Slq | fzf --preview="yay -Si {}"'
    fi
elif command -v apt >/dev/null 2>&1; then
    # Ubuntu
    alias aptu="sudo apt update && sudo apt upgrade && sudo apt autoremove"
    alias apti="sudo apt install"
    alias aptc="sudo apt clean && sudo apt autoclean && sudo apt autoremove"
    alias aptr="sudo apt purge"
fi

# --- Updates ---
# Spofity + Spicetify
if command -v spicetify >/dev/null 2>&1; then
    alias upspicetify="spicetify update && spicetify restore backup apply"
    alias upspotify="yay -S spotify && spicetify update && spicetify backup apply"
fi

# --- Modern CLI Tools ---
# ls / tree (eza)
alias ls='eza --icons --group-directories-first --git'
alias tree='eza --tree --icons --group-directories-first --git'

# nvim
alias nv='nvim'

# bat / batcat
if command -v batcat >/dev/null 2>&1; then
    alias bat="batcat"
elif command -v bat >/dev/null 2>&1; then
    unalias bat 2>/dev/null
fi
alias batc='bat --paging=never'

# fzf basic
alias fp='fzf'
if command -v fdfind >/dev/null 2>&1; then
    alias fd="fdfind"
elif command -v fd >/dev/null 2>&1; then
    unalias fd 2>/dev/null
fi

# fzf search functions (with fd fallback)
if command -v fd >/dev/null 2>&1 || command -v fdfind >/dev/null 2>&1; then
    alias fnv='nvim $(fd --type f --hidden --no-ignore --exclude .git | fzf --preview="bat --color=always {}")'
    alias fcd='cd "$(fd --type d --hidden --no-ignore --exclude .git | fzf --preview="eza --tree --icons --color=always --group-directories-first --git {}")"'
else
    # Fallback to standard find if fd is missing
    alias fnv='nvim $(find . -maxdepth 3 -not -path "*/.*" | fzf --preview="bat --color=always {}")'
    alias fcd='cd "$(find . -maxdepth 3 -type d -not -path "*/.*" | fzf --preview="eza --tree --icons --color=always --group-directories-first --git {}")"'
fi

# --- Development ---
# Git
alias lg='lazygit'

# Docker
#alias dops="docker ps"
alias docps="docker ps -a"
alias docx="docker exec -it"
alias doclog="docker logs --tail 100"
alias doco="docker compose"
alias docoup="docker compose up -d"
alias docodown="docker compose down"
alias docobuild="docker compose build --no-cache"

# Zellij
alias z='zellij'


# ======================
# Terminal Configuration
# ======================
# fzf initialization
if command -v fzf >/dev/null 2>&1; then
    source <(fzf --zsh)
fi

# bun completions
[ -s "$HOME/.bun/_bun" ] && source "$HOME/.bun/_bun"

# atuin initialization
if command -v atuin >/dev/null 2>&1; then
    eval "$(atuin init zsh)"
fi


# >>> conda initialize >>>
# !! Contents within this block are managed by 'conda init' !!
# __conda_setup="$('$HOME/anaconda3/bin/conda' 'shell.zsh' 'hook' 2> /dev/null)"
# if [ $? -eq 0 ]; then
#     eval "$__conda_setup"
# else
#     if [ -f "$HOME/anaconda3/etc/profile.d/conda.sh" ]; then
#         . "$HOME/anaconda3/etc/profile.d/conda.sh"
#     else
#         export PATH="$HOME/anaconda3/bin:$PATH"
#     fi
# fi
# unset __conda_setup
# conda activate myenv
# <<< conda initialize <<<


# ======================
# Zellij Configuration
# ======================
# Automatic tab naming based on currently running process
if [[ -n $ZELLIJ ]]; then
    function zellij_tab_name_update() {
        local tab_name="zsh"
        if [[ -n $1 ]]; then
            # Extract command name and handle paths
            tab_name="${1%% *}"
            tab_name="${tab_name##*/}"
            
            # Special case for sudo
            if [[ "$tab_name" == "sudo" ]]; then
                local next_cmd="${${1#* }%% *}"
                tab_name="${next_cmd##*/}"
            fi
        fi
        # Rename the current tab
        command zellij action rename-tab "$tab_name" >/dev/null 2>&1
    }
    
    autoload -Uz add-zsh-hook
    add-zsh-hook precmd  zellij_tab_name_update
    add-zsh-hook preexec zellij_tab_name_update
fi
