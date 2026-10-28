#!/bin/sh
# Provision ~/.dotfiles; DOTFILES_ENV overrides the detected class and layers.
set -eu

REPO_URL="${REPO_URL:-https://github.com/${GITHUB_USERNAME:-h-wb}/dotfiles.git}"
DOTFILES_DIR="${HOME}/.dotfiles" # fixed: config.toml links ~/.config/mise here
export PATH="${HOME}/.local/bin:${PATH}"

case "${DOTFILES_ENV:-}" in
personal) DOTFILES_LAYERS='"workstation", "personal"' ;;
neko) DOTFILES_LAYERS='"workstation", "pod", "neko"' ;;
cachyos) DOTFILES_LAYERS='"workstation", "cachyos"' ;;
paseo) DOTFILES_LAYERS='"pod", "paseo"' ;;
"") DOTFILES_LAYERS= ;;
*) echo "Unknown DOTFILES_ENV: $DOTFILES_ENV" >&2; exit 1 ;;
esac

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
[ -z "$DOTFILES_LAYERS" ] || printf 'env = [%s]\n' "$DOTFILES_LAYERS" >miserc.local.toml
. ./scripts/provision.sh
ensure_mise || exit 1

configs="$("$MISE" config)"
case "$configs" in
*config.workstation.toml*)
	# Activate configured tools and env before login (neko needs the fs key provider).
	exec "$MISE" exec github:jdx/fnox github:protonpass/pass-cli -- sh -c '
		./scripts/pass-preflight || exit 1
		exec fnox --if-missing error exec -c fnox.toml -- "$@"
	' sh "$MISE" bootstrap --yes --force-dotfiles ;;
*) exec "$MISE" bootstrap --yes --force-dotfiles ;;
esac
