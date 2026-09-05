# Mirrors home/zsh/aliases.zsh, minus the macOS-only ones. fish auto-sources
# every conf.d/*.fish before config.fish.

alias repo="cd $HOME/Repositories"

# Code
alias dotfiles="code $HOME/.dotfiles"
alias ops="code $HOME/Repositories/home-ops"

alias ef="exec fish"

# Git
alias g="git"
alias galias="git config --get-regexp alias"

# Dotfiles (mise)
alias df="mise -C $HOME/.dotfiles"
alias dfa="mise -C $HOME/.dotfiles run apply"
