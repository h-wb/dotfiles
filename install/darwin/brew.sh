#!/usr/bin/env bash

set -Eeuo pipefail

fi

function is_homebrew_installed() {
    command -v brew &>/dev/null
}

function install_homebrew() {
    if ! is_homebrew_installed; then
        echo "[info] installing homebrew"
        /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    fi
}

function setup_homebrew_path() {
    if [[ "$(uname -m)" == "arm64" ]]; then
        local homebrew_bin="/opt/homebrew/bin"
        if ! grep -q "${homebrew_bin}" /etc/paths; then
            echo "[info] setting up homebrew binary path"
            printf '%s\n' "${homebrew_bin}" "$(cat /etc/paths)" | sudo tee /etc/paths > /dev/null
        fi
    fi
}

function main() {
    install_homebrew
    setup_homebrew_path
}

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main
fi
