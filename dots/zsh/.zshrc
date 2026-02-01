# ============================
# Powerlevel10k Instant Prompt
# ============================
if [[ -r "${XDG_CACHE_HOME:-$HOME/.cache}/p10k-instant-prompt-${(%):-%n}.zsh" ]]; then
  source "${XDG_CACHE_HOME:-$HOME/.cache}/p10k-instant-prompt-${(%):-%n}.zsh"
fi


# ======================
# Oh-My-Zsh Configuration
# ======================
zstyle ':omz:update' mode auto      # run 'omz update' to update manually
zstyle ':omz:update' frequency 7
export ZSH="$HOME/.oh-my-zsh"
ZSH_THEME="powerlevel10k/powerlevel10k"
[[ ! -f ~/.p10k.zsh ]] || source ~/.p10k.zsh

# Standard plugins can be found in $ZSH/plugins/
# Custom plugins may be added to $ZSH_CUSTOM/plugins/
source ${ZSH_CUSTOM:-$HOME/.oh-my-zsh/custom}/plugins/zsh-syntax-highlighting/themes/catppuccin_mocha-zsh-syntax-highlighting.zsh
plugins=(gitfast gh zsh-autosuggestions zsh-syntax-highlighting history ssh sudo)
source $ZSH/oh-my-zsh.sh
source ${ZSH_CUSTOM:-$HOME/.oh-my-zsh/custom}/themes/powerlevel10k


# ======================
# Aliases
# ======================
alias zshconfig="nvim ~/.zshrc"
alias ohmyzsh="nvim ~/.oh-my-zsh"

# ubuntu
alias aptu="sudo apt update && sudo apt upgrade && sudo apt autoremove"
alias apti="sudo apt install"
alias aptc="sudo apt clean && sudo apt autoclean && sudo apt autoremove"
alias aptr="sudo apt purge"

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
# Environment Variables
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

# Gemini CLI
# export GOOGLE_CLOUD_PROJECT="erudite-nation-470903-t5"

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
source <(fzf --zsh)

# bun completions
[ -s "$HOME/.bun/_bun" ] && source "$HOME/.bun/_bun"

# atuin
eval "$(atuin init zsh)"

# starship
# export PATH="$HOME/.cargo/bin:$PATH"
# eval "$(starship init zsh)"


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

