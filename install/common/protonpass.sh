#!/usr/bin/env bash

set -euo pipefail

export PATH="${HOME}/.local/share/mise/shims:${PATH}"

if ! command -v pass-cli &> /dev/null; then
    echo "[info] installing pass-cli via mise"
    mise use -gy "github:tnfssc/protonpass-cli-bin"
fi

# Check authentication silently — exits 0 if connected, non-zero if not
if pass-cli test &> /dev/null; then
    exit 0
fi

# Not authenticated — show browser URL and wait
pass-cli login
