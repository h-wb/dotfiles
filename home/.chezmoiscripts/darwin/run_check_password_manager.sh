#!/usr/bin/env bash

CHEZMOI_SOURCE="$(chezmoi source-path)"
source "${CHEZMOI_SOURCE}/.chezmoiscripts/darwin/.00_helpers.sh"

check-password-manager