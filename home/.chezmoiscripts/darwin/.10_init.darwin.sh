#!/usr/bin/env bash

set -euo pipefail

CHEZMOI_SOURCE="$(chezmoi source-path)"
source "${CHEZMOI_SOURCE}/.chezmoiscripts/darwin/.00_helpers.sh"

install-homebrew
enable-sudo-touchid
check-password-manager