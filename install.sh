#!/bin/sh
# Provision ~/.dotfiles on a machine a person installs by hand (the Mac,
# CachyOS); pods run scripts/pod-bootstrap instead. DOTFILES_ENV names the
# environment, a set from miserc.toml's [env_sets] plus any extra layers
# (`personal`, `cachyos`). mise saves it in miserc.local.toml before preflight.
# Later runs need it only to change it. Update an existing checkout with git.
set -eu

REPO_URL="${REPO_URL:-https://github.com/${GITHUB_USERNAME:-h-wb}/dotfiles.git}"
DOTFILES_DIR="${HOME}/.dotfiles" # fixed: config.toml links ~/.config/mise here
export PATH="${HOME}/.local/bin:${PATH}"

if [ -z "${DOTFILES_ENV:-}" ] && [ ! -f "${DOTFILES_DIR}/miserc.local.toml" ]; then
	echo "Set DOTFILES_ENV to this machine's environment (personal, cachyos, ...)" >&2
	exit 1
fi
case "${DOTFILES_ENV:-}" in
*[!a-z0-9,-]*) echo "Unknown DOTFILES_ENV: $DOTFILES_ENV" >&2; exit 1 ;;
esac

# On a fresh Mac, git triggers the Command Line Tools install.
[ -d "${DOTFILES_DIR}/.git" ] || git clone "${REPO_URL}" "${DOTFILES_DIR}"
cd "${DOTFILES_DIR}"

# The ~/.config/mise link doesn't exist until this run's dotfiles step.
export MISE_CONFIG_DIR="${DOTFILES_DIR}"
. ./scripts/provision.sh
# Not declared now: the saved environment, not an activated shell's MISE_ENV.
unset MISE_ENV
[ -z "${DOTFILES_ENV:-}" ] || use_env "$DOTFILES_ENV" || exit 1
ensure_mise || exit 1

if [ -n "${DOTFILES_ENV:-}" ]; then
	# Save without loading config or running any provisioning before login.
	"$MISE" --no-config bootstrap --save-env --yes --only final-hook
fi
configs="$("$MISE" config)"
case "$configs" in
*config.workstation.toml*)
	# Activate configured tools and env before login.
	"$MISE" exec github:jdx/fnox github:protonpass/pass-cli -- sh -c '
		./scripts/pass-preflight || exit 1
		exec fnox --if-missing error exec -c fnox.toml -- "$@"
	' sh "$MISE" bootstrap --yes --force-dotfiles || exit 1 ;;
*) "$MISE" bootstrap --yes --force-dotfiles || exit 1 ;;
esac
