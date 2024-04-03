#!/usr/bin/env bash

CHEZMOI_SOURCE="$(chezmoi source-path)"
export PATH="${CHEZMOI_SOURCE}/scripts:${PATH}"
