#!/bin/sh

set -eu

if ! echo $PATH | grep -q "$HOME/\.local/bin:"; then
	export PATH="$HOME/.local/bin:$PATH"
fi

if ! mise="$(command -v mise)"; then
	if command -v curl >/dev/null; then
		curl https://mise.run | sh
	elif command -v wget >/dev/null; then
		wget -qO- https://mise.run | sh
	else
		echo "To install mise, you must have curl or wget installed." >&2
		exit 1
	fi
	mise=~/.local/bin/mise
else
	mise=$(which mise)
fi

eval "${mise} use -yg chezmoi"
chezmoi=$(${mise} which chezmoi)

if [ "${CODESPACES:-false}" = true ]; then
	set -- init --apply
else
	set -- init --apply ${GITHUB_USERNAME:-h-wb}
fi

# exec: replace current process with chezmoi
exec "$chezmoi" "$@"
