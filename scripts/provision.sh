# Shared by install.sh and pod-bootstrap. Sourced, POSIX sh. Sets MISE.

# Install mise if missing, and self-update below config.toml's hard min_version:
# self_update.auto skips unattended runs, so every run would fail instead.
ensure_mise() {
	MISE="${HOME}/.local/bin/mise"
	if [ ! -x "$MISE" ]; then
		echo "[info] installing mise"
		installer="$(mktemp)" || return 1
		if curl -fsSL https://mise.run -o "$installer" && sh "$installer"; then
			rm -f "$installer"
		else
			rm -f "$installer"
			return 1
		fi
	fi
	[ -x "$MISE" ] || { echo "[error] mise was not installed at $MISE" >&2; return 1; }
	min="$(sed -n 's/^min_version = { hard = "\([^"]*\)" }.*/\1/p' "${HOME}/.dotfiles/config.toml" 2>/dev/null)"
	have="$("$MISE" --version 2>/dev/null | awk '{print $1}')"
	if [ -n "$min" ] &&
		[ "$(printf '%s\n%s\n' "$min" "${have:-0}" | sort -V | head -1)" != "$min" ]; then
		echo "[info] mise ${have:-?} < ${min}; self-updating"
		"$MISE" self-update --yes || return 1
		have="$("$MISE" --version 2>/dev/null | awk '{print $1}')"
		[ "$(printf '%s\n%s\n' "$min" "${have:-0}" | sort -V | head -1)" = "$min" ] ||
			{ echo "[error] mise ${have:-?} is still below required $min" >&2; return 1; }
	fi
}

# declare_env DIR SPEC: record this machine's environment in DIR/miserc.local.toml.
# SPEC is a set from DIR/miserc.toml's [env_sets], then any extra layers,
# comma-separated (`code-server`, `paseo,paseo-overlay`). A bad SPEC writes
# nothing. A MISE_ENV inherited from an activated shell would override the file.
declare_env() {
	case "$2" in
	"" | ,* | *, | *,,* | *[!a-z0-9,-]*)
		echo "[error] environment '$2': a set name, then layers, comma-separated" >&2
		return 1 ;;
	esac
	sets="$(sed -n '/^\[env_sets\]/,/^\[/s/^\([a-z0-9-]*\) = .*/\1/p' "$1/miserc.toml")"
	printf '%s\n' "$sets" | grep -qx -- "${2%%,*}" || {
		echo "[error] environment '${2%%,*}' is not a set in miserc.toml:" $sets >&2
		return 1
	}
	printf 'env = [%s]\n' "$(printf '%s' "$2" | sed 's/[^,]*/"&"/g; s/,/, /g')" >"$1/miserc.local.toml"
	unset MISE_ENV
}
