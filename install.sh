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

# # POSIX way to get script's dir: https://stackoverflow.com/a/29834779/12156188
# script_dir="$(cd -P -- "$(dirname -- "$(command -v -- "$0")")" && pwd -P)"

# set -- init --apply --source="${script_dir}" --no-tty --force

if [ "${CODESPACES:-false}" = true ]; then
	set -- init --apply
else
	set -- init --apply ${GITHUB_USERNAME:-h-wb}
fi

# exec: replace current process with chezmoi
exec "$chezmoi" "$@"
