# Shared by the Linux pods' provisioning scripts (conf.d/{neko,paseo}/bin/*-bootstrap).
# Sourced, POSIX sh. Sets MISE.

# Install mise if missing, and self-update below config.toml's hard min_version:
# self_update.auto skips unattended runs, so every run would fail instead.
ensure_mise() {
	if ! command -v mise >/dev/null 2>&1; then
		echo "[info] installing mise"
		curl -fsSL https://mise.run | sh
	fi
	MISE="${HOME}/.local/bin/mise"
	min="$(sed -n 's/^min_version = { hard = "\([^"]*\)" }.*/\1/p' "${HOME}/.dotfiles/config.toml" 2>/dev/null)"
	have="$("$MISE" --version 2>/dev/null | awk '{print $1}')"
	if [ -n "$min" ] &&
		[ "$(printf '%s\n%s\n' "$min" "${have:-0}" | sort -V | head -1)" != "$min" ]; then
		echo "[info] mise ${have:-?} < ${min}; self-updating"
		"$MISE" self-update --yes || echo "[warn] mise self-update failed"
	fi
}

# Fast-forward ~/.dotfiles. On a new commit, re-exec "$@" once, so the caller
# (and this file, and the min_version check) run as of that commit.
pull_dotfiles() {
	[ -z "${DOTFILES_PULLED:-}" ] || return 0
	before="$(git -C "${HOME}/.dotfiles" rev-parse HEAD 2>/dev/null)"
	if timeout 60 git -C "${HOME}/.dotfiles" pull --ff-only --quiet; then
		after="$(git -C "${HOME}/.dotfiles" rev-parse HEAD 2>/dev/null)"
		if [ "$after" != "$before" ]; then
			echo "[info] dotfiles updated ${before} -> ${after}"
			DOTFILES_PULLED=1 exec "$@"
		fi
	else
		echo "[warn] dotfiles pull skipped (offline, local commits, or no upstream)"
	fi
}
