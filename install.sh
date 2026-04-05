#!/bin/sh

set -eu

export PATH="${HOME}/.local/bin:${PATH}"

if ! command -v mise >/dev/null; then
	curl https://mise.run | sh
fi

exec "${HOME}/.local/bin/mise" exec chezmoi@latest -- chezmoi init --apply --use-builtin-git true ${GITHUB_USERNAME:-h-wb}
