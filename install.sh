#!/bin/sh
# Full-mise bootstrap. Installs mise, clones this repo, makes it the global mise
# config, and runs `mise bootstrap` (packages, macOS, dotfiles, tools) with
# secrets injected by fnox.
set -eu

REPO_URL="${REPO_URL:-https://github.com/${GITHUB_USERNAME:-h-wb}/dotfiles.git}"
DOTFILES_DIR="${DOTFILES_DIR:-${HOME}/.dotfiles}"

export PATH="${HOME}/.local/bin:${PATH}"

# 1. mise
if ! command -v mise >/dev/null 2>&1; then
	curl https://mise.run | sh
fi
MISE="${HOME}/.local/bin/mise"

# 2. clone/update the repo (git triggers the Command Line Tools install on a
#    fresh Mac, which is exactly what we want).
if [ -d "${DOTFILES_DIR}/.git" ]; then
	git -C "${DOTFILES_DIR}" pull --ff-only
else
	git clone "${REPO_URL}" "${DOTFILES_DIR}"
fi
cd "${DOTFILES_DIR}"

# 3. make this repo's mise.toml the global mise config
mkdir -p "${HOME}/.config/mise"
ln -sf "${DOTFILES_DIR}/mise.toml" "${HOME}/.config/mise/config.toml"
ln -sf "${DOTFILES_DIR}/mise.personal.toml" "${HOME}/.config/mise/config.personal.toml"
[ -d "${HOME}/.config/mise/conf.d" ] && [ ! -L "${HOME}/.config/mise/conf.d" ] && rm -rf "${HOME}/.config/mise/conf.d"
ln -sfn "${DOTFILES_DIR}/conf.d" "${HOME}/.config/mise/conf.d"   # macos-defaults + settings fragments

# 3b. per-machine runtime config (selects env overlays; enables env-scoped conf.d).
#     Not a symlink: it's machine-specific, and it must exist before config
#     discovery. Copy the example on first setup; edit `env` per machine after.
[ -f "${HOME}/.config/mise/miserc.toml" ] || cp "${DOTFILES_DIR}/miserc.toml.example" "${HOME}/.config/mise/miserc.toml"

# 4. trust + bootstrap everything (secrets injected by fnox; first run triggers
#    `pass-cli login`). On a machine without secrets, run `mise bootstrap` directly.
"${MISE}" trust
exec "${MISE}" exec github:jdx/fnox@latest -- fnox exec -c fnox.toml -- "${MISE}" bootstrap --yes
