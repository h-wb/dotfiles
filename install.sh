#!/bin/sh

set -eu

export PATH="${HOME}/.local/bin:${PATH}"

if ! command -v mise >/dev/null; then
	curl https://mise.run | sh
fi

eval "${HOME}/.local/bin/mise use -yg chezmoi"
chezmoi="${HOME}/.local/bin/chezmoi"

exec "$chezmoi" init --apply --use-builtin-git true ${GITHUB_USERNAME:-h-wb}
