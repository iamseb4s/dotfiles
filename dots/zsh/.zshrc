# ============================
# Powerlevel10k Instant Prompt
# ============================
if [[ -r "${XDG_CACHE_HOME:-$HOME/.cache}/p10k-instant-prompt-${(%):-%n}.zsh" ]]; then
  source "${XDG_CACHE_HOME:-$HOME/.cache}/p10k-instant-prompt-${(%):-%n}.zsh"
fi


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
# Aliases
# ======================
alias zshconfig="nvim ~/.zshrc"
alias ohmyzsh="nvim ~/.oh-my-zsh"

# Ubuntu
alias aptu="sudo apt update && sudo apt upgrade && sudo apt autoremove"
alias apti="sudo apt install"
alias aptc="sudo apt clean && sudo apt autoclean && sudo apt autoremove"
alias aptr="sudo apt purge"

# Modern CLI
# eza
alias ls='eza --icons --group-directories-first --git'
alias tree='eza --tree --icons --group-directories-first --git'

# nvim
alias nv='nvim'

# bat (batcat)
alias bat="batcat"
alias batc='bat --paging=never'

# fzf
alias fp='fzf'
alias fnv='nvim $(fzf --preview="batcat {}")'
alias fcd='cd "$(fdfind --type d --hidden --no-ignore --exclude .git | fzf --preview="eza --tree --icons --color=always --group-directories-first --git {}")"'

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

# zellij
alias z='zellij'


# ======================
# Environment & Tools
# ======================
# Conda
export PATH=$HOME/anaconda3/bin:/usr/local/bin:/usr/bin:/usr/local/sbin:/usr/sbin:/bin:$PATH

# NPM
export PATH=$HOME/.npm-global/bin:$PATH

# bun
export BUN_INSTALL="$HOME/.bun"
export PATH="$BUN_INSTALL/bin:$PATH"

# fzf
export FZF_DEFAULT_OPTS_FILE="$HOME/.config/fzf/fzf.conf"
export FZF_DEFAULT_OPTS="--bind='focus:'"

# Opencode
export PATH=$HOME/.opencode/bin:$PATH

# Preferred editor for local and remote sessions
if [[ -n $SSH_CONNECTION ]]; then
  export EDITOR='nvim'
else
  export EDITOR='code --wait'
fi


# ======================
# Terminal Configuration
# ======================
# fzf
[[ ! "$PATH" == *"$HOME/.fzf/bin"* ]] && export PATH="${PATH:+${PATH}:}$HOME/.fzf/bin"
command -v fzf >/dev/null 2>&1 && source <(fzf --zsh)

# bun completions
[ -s "$HOME/.bun/_bun" ] && source "$HOME/.bun/_bun"

# atuin
command -v atuin >/dev/null 2>&1 && eval "$(atuin init zsh)"


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


