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

# 1b. the neko/xfce container ships curl but no git, and its /usr is wiped on
#     every pod roll, so git can be missing on a box that is otherwise set up.
#     (bootstrap reinstalls it from [bootstrap.packages] afterwards.)
if ! command -v git >/dev/null 2>&1 && command -v apt-get >/dev/null 2>&1; then
	sudo apt-get update -qq
	sudo apt-get install -y -qq --no-install-recommends git
fi

# 2. clone/update the repo (git triggers the Command Line Tools install on a
#    fresh Mac, which is exactly what we want).
if [ -d "${DOTFILES_DIR}/.git" ]; then
	git -C "${DOTFILES_DIR}" pull --ff-only
else
	git clone "${REPO_URL}" "${DOTFILES_DIR}"
fi
cd "${DOTFILES_DIR}"

# 3. wire this repo into mise's global config dir (global config, env overlays,
#    conf.d, per-machine miserc). Shared with the neko container's session-start
#    bootstrap, which needs the same wiring on a fresh PVC.
DOTFILES_DIR="${DOTFILES_DIR}" "${DOTFILES_DIR}/scripts/link-mise-config"

# 4. trust + bootstrap everything (secrets injected by fnox). The preflight logs
#    into Proton Pass if there is no session yet, and --if-missing error makes an
#    unresolved secret fatal instead of a warning that renders the secret-gated
#    dotfiles empty. On a machine without secrets, run `mise bootstrap` directly.
"${MISE}" trust
MISE="${MISE}" "${DOTFILES_DIR}/scripts/pass-preflight" || exit 1
exec "${MISE}" exec github:jdx/fnox@latest -- \
	fnox --if-missing error exec -c fnox.toml -- "${MISE}" bootstrap --yes
