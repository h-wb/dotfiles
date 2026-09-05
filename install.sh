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

# 3. make this repo's mise.toml the global mise config
mkdir -p "${HOME}/.config/mise"
ln -sf "${DOTFILES_DIR}/mise.toml" "${HOME}/.config/mise/config.toml"
#    ...plus every env overlay (mise.<env>.toml -> config.<env>.toml), so mise
#    finds them next to the global config: personal, neko, whatever comes next.
for overlay in "${DOTFILES_DIR}"/mise.*.toml; do
	name="$(basename "${overlay}")"
	case "${name}" in
	mise.local.toml | *.example) continue ;;
	esac
	ln -sf "${overlay}" "${HOME}/.config/mise/config.${name#mise.}"
done
[ -d "${HOME}/.config/mise/conf.d" ] && [ ! -L "${HOME}/.config/mise/conf.d" ] && rm -rf "${HOME}/.config/mise/conf.d"
ln -sfn "${DOTFILES_DIR}/conf.d" "${HOME}/.config/mise/conf.d"   # macos-defaults + settings fragments

# 3b. per-machine runtime config (selects env overlays; enables env-scoped conf.d).
#     Not a symlink: it's machine-specific, and it must exist before config
#     discovery. Copy the example on first setup; edit `env` per machine after.
#     The active env defaults to the machine class: `neko` inside the neko
#     container (/etc/neko is baked into that image), `personal` otherwise.
#     Override with DOTFILES_ENV=work sh install.sh.
if [ ! -f "${HOME}/.config/mise/miserc.toml" ]; then
	cp "${DOTFILES_DIR}/miserc.toml.example" "${HOME}/.config/mise/miserc.toml"
	if [ -z "${DOTFILES_ENV:-}" ] && [ -d /etc/neko ]; then
		DOTFILES_ENV="neko"
	fi
	if [ -n "${DOTFILES_ENV:-}" ]; then
		sed -i.bak "s/^env = .*/env = [\"${DOTFILES_ENV}\"]/" "${HOME}/.config/mise/miserc.toml"
		rm -f "${HOME}/.config/mise/miserc.toml.bak"
	fi
fi

# 4. trust + bootstrap everything (secrets injected by fnox). The preflight logs
#    into Proton Pass if there is no session yet, and --if-missing error makes an
#    unresolved secret fatal instead of a warning that renders the secret-gated
#    dotfiles empty. On a machine without secrets, run `mise bootstrap` directly.
"${MISE}" trust
MISE="${MISE}" "${DOTFILES_DIR}/scripts/pass-preflight" || exit 1
exec "${MISE}" exec github:jdx/fnox@latest -- \
	fnox --if-missing error exec -c fnox.toml -- "${MISE}" bootstrap --yes
