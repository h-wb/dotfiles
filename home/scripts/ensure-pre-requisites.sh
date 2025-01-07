#!/bin/sh

export PATH="${CHEZMOI_SOURCE_DIR?}/scripts:${PATH}"

case "$(uname -s)" in
Darwin)
    install-homebrew
    install-password-manager
    ;;
*)
    echo "unsupported OS"
    exit 1
    ;;
esac