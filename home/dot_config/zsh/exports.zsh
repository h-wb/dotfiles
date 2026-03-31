export GPG_TTY=$TTY
export EDITOR="code --wait"
export PATH="${KREW_ROOT:-$HOME/.krew}/bin:$PATH"
export PATH="/opt/homebrew/bin:/opt/homebrew/sbin:$PATH"
export BWS_ACCESS_TOKEN="$(security find-generic-password -w -s 'BWS_ACCESS_TOKEN' -a "h-wb")"
export NO_ROOTMOI=1 # INFO: on daily basis do not want to execute rootmoi after bootstrap
