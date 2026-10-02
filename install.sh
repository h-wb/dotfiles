#!/bin/sh
# Provision a machine from scratch: a Mac, the CachyOS desktop or the neko
# container. Installs mise, clones this repo to ~/.dotfiles, then runs
# `mise bootstrap` from it with secrets from fnox. That run also links
# ~/.config/mise -> ~/.dotfiles (a [dotfiles] entry in config.toml), and
# miserc.toml detects the machine class (DOTFILES_ENV overrides it).
set -eu

REPO_URL="${REPO_URL:-https://github.com/${GITHUB_USERNAME:-h-wb}/dotfiles.git}"
DOTFILES_DIR="${HOME}/.dotfiles" # fixed: config.toml links ~/.config/mise here
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

# 3. Load the config from the checkout for this first run; the bootstrap's
#    dotfiles step creates the ~/.config/mise link that later runs go through.
export MISE_CONFIG_DIR="${DOTFILES_DIR}"
[ -n "${DOTFILES_ENV:-}" ] && printf 'env = ["%s"]\n' "${DOTFILES_ENV}" >miserc.local.toml

# 4. Bootstrap with secrets. The preflight logs into Proton Pass if there is no
#    session; --if-missing error makes an unresolved secret fatal instead of a
#    warning that renders the secret-gated dotfiles empty over good copies.
#    This is `mise run apply`, spelled out because fnox is not installed yet.
MISE="${MISE}" ./scripts/pass-preflight || exit 1
# --force-dotfiles: the distro writes its own ~/.config/fish/config.fish, and a
# machine on the old layout has a real ~/.config/mise directory in the way.
# fnox's Proton Pass provider shells out to `pass-cli`, so it must be on PATH
# too — not just fnox. (A Mac with pass-cli already installed hides this.)
exec "${MISE}" exec github:jdx/fnox@latest github:protonpass/pass-cli@latest -- \
	fnox --if-missing error exec -c fnox.toml -- "${MISE}" bootstrap --yes --force-dotfiles
