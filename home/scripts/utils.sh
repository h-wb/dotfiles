#!/usr/bin/env bash

declare -r red='\033[0;31m'
declare -r green='\033[0;32m'
declare -r orange='\033[0;33m'
declare -r blue='\033[0;34m'
declare -r normal='\033[0m' # No Color

echo_error() {
  printf "${red}[error] ${normal}$@\n"
}

echo_info() {
  printf "${blue}[info] ${normal}$@\n"
}

echo_warn() {
  printf "${orange}[warn] ${normal}$@\n"
}

command_exists() {
  type "${1}" >/dev/null 2>&1
}

is_arm64() {
  local -r arch="$(uname -m)"
  test "${arch}" = "arm64" || test "${arch}" = "aarch64"
}

should_include_secrets() {
  local -r bool="$(chezmoi execute-template '{{ get . "should_include_secrets" }}')"
  test "${bool}" = "true"
}