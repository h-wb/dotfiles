#!/bin/sh
# Provision a machine from scratch: a Mac, the CachyOS desktop or the neko
# container. Installs mise, clones this repo to ~/.dotfiles, makes it mise's
# config dir (scripts/wire), then runs `mise bootstrap` with secrets from fnox.
set -eu

REPO_URL="${REPO_URL:-https://github.com/${GITHUB_USERNAME:-h-wb}/dotfiles.git}"
DOTFILES_DIR="${DOTFILES_DIR:-${HOME}/.dotfiles}"
export PATH="${HOME}/.local/bin:${PATH}"

# 1. mise
command -v mise >/dev/null 2>&1 || curl -fsSL https://mise.run | sh
MISE="${HOME}/.local/bin/mise"

# 1b. The neko image ships curl but no git, and its /usr is wiped on every pod
#     roll. (bootstrap reinstalls it from [bootstrap.packages] afterwards.)
if ! command -v git >/dev/null 2>&1 && command -v apt-get >/dev/null 2>&1; then
	sudo apt-get update -qq
	sudo apt-get install -y -qq --no-install-recommends git
fi

# 2. The repo (git triggers the Command Line Tools install on a fresh Mac).
if [ -d "${DOTFILES_DIR}/.git" ]; then
	git -C "${DOTFILES_DIR}" pull --ff-only
else
	git clone "${REPO_URL}" "${DOTFILES_DIR}"
fi
cd "${DOTFILES_DIR}"

# 3. ~/.config/mise -> this repo, plus the machine class in miserc.local.toml.
DOTFILES_DIR="${DOTFILES_DIR}" ./scripts/wire

# 4. Bootstrap with secrets. The preflight logs into Proton Pass if there is no
#    session; --if-missing error makes an unresolved secret fatal instead of a
#    warning that renders the secret-gated dotfiles empty over good copies.
#    This is `mise run apply`, spelled out because fnox is not installed yet.
MISE="${MISE}" ./scripts/pass-preflight || exit 1
FORCE=""
[ "$(uname)" = "Darwin" ] || FORCE="--force-dotfiles" # distro-written fish config
exec "${MISE}" exec github:jdx/fnox@latest -- \
	fnox --if-missing error exec -c fnox.toml -- "${MISE}" bootstrap --yes ${FORCE}
