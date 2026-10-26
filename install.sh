#!/bin/sh
# Provision a machine from scratch: install mise, clone to ~/.dotfiles, and run
# `mise run apply` by hand (fnox isn't installed yet). The class comes from
# miserc.toml; DOTFILES_ENV overrides it.
set -eu

REPO_URL="${REPO_URL:-https://github.com/${GITHUB_USERNAME:-h-wb}/dotfiles.git}"
DOTFILES_DIR="${HOME}/.dotfiles" # fixed: config.toml links ~/.config/mise here
export PATH="${HOME}/.local/bin:${PATH}"

command -v mise >/dev/null 2>&1 || curl -fsSL https://mise.run | sh
MISE="${HOME}/.local/bin/mise"

# The neko image ships curl but no git.
if ! command -v git >/dev/null 2>&1 && command -v apt-get >/dev/null 2>&1; then
	sudo apt-get update -qq
	sudo apt-get install -y -qq --no-install-recommends git
fi

# On a fresh Mac, git triggers the Command Line Tools install.
if [ -d "${DOTFILES_DIR}/.git" ]; then
	git -C "${DOTFILES_DIR}" pull --ff-only
else
	git clone "${REPO_URL}" "${DOTFILES_DIR}"
fi
cd "${DOTFILES_DIR}"

# The ~/.config/mise link doesn't exist until this run's dotfiles step.
export MISE_CONFIG_DIR="${DOTFILES_DIR}"
[ -n "${DOTFILES_ENV:-}" ] && printf 'env = ["%s"]\n' "${DOTFILES_ENV}" >miserc.local.toml

MISE="${MISE}" ./scripts/pass-preflight || exit 1
# fnox's provider shells out to pass-cli, so both must be on PATH.
# --force-dotfiles: the distro's own config.fish, or an old real ~/.config/mise.
exec "${MISE}" exec github:jdx/fnox@latest github:protonpass/pass-cli@latest -- \
	fnox --if-missing error exec -c fnox.toml -- "${MISE}" bootstrap --yes --force-dotfiles
