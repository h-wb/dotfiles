#!/usr/bin/env bash

set -eou pipefail

if [[ ! -x "$(command -v brew)" ]];then
  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
fi
