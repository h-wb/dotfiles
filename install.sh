#!/bin/sh
# The Mac and CachyOS: DOTFILES_ENV=personal|cachyos, needed the first time.
set -eu

DOTFILES_DIR="${HOME}/.dotfiles" # fixed: config.toml links ~/.config/mise here
REPO_URL="${REPO_URL:-https://github.com/h-wb/dotfiles.git}"
export PATH="${HOME}/.local/bin:${PATH}"
unset MISE_ENV # never an activated shell's

case "${DOTFILES_ENV:-}" in
*[!a-z0-9,-]* | ,* | *, | *,,*) echo "Unknown DOTFILES_ENV: $DOTFILES_ENV" >&2; exit 1 ;;
esac
if [ -z "${DOTFILES_ENV:-}" ] && [ ! -f "${DOTFILES_DIR}/miserc.local.toml" ]; then
	echo "Set DOTFILES_ENV to this machine's environment (personal, cachyos, ...)" >&2
	exit 1
fi
# mise reuses a checkout only when its origin is exactly --from.
[ ! -d "${DOTFILES_DIR}/.git" ] || REPO_URL="$(git -C "$DOTFILES_DIR" remote get-url origin)"

if ! command -v mise >/dev/null 2>&1; then
	installer="$(mktemp)"
	curl -fsSL https://mise.run -o "$installer" || { rm -f "$installer"; exit 1; }
	sh "$installer"
	rm -f "$installer"
fi

if [ -n "${DOTFILES_ENV:-}" ]; then
	mise -E "$DOTFILES_ENV" bootstrap --from "$REPO_URL" --from-dir "$DOTFILES_DIR" \
		--config-dir . --save-env --yes --only final-hook
	grep -q "^${DOTFILES_ENV%%,*} = \[" "${DOTFILES_DIR}/miserc.toml" || {
		echo "DOTFILES_ENV: '${DOTFILES_ENV%%,*}' is not a set in miserc.toml" >&2
		exit 1
	}
else
	mise bootstrap --from "$REPO_URL" --from-dir "$DOTFILES_DIR" --config-dir . --yes --only final-hook
fi
cd "$DOTFILES_DIR"
mise run apply
