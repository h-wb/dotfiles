#!/bin/sh
# Shared managed-agent login for mise's global proton:login task.
# Tokens arrive through the Keychain or environment, never command arguments.
set -eu
umask 077

session="${usage_session:-${PROTON_PASS_LOGIN_SESSION:-}}"
case "$session" in
'' | *[!a-zA-Z0-9_-]*)
	echo "proton:login: session must contain only letters, numbers, _ or -" >&2
	exit 1
	;;
esac

export PROTON_PASS_SESSION_DIR="$HOME/.local/state/pass-cli/$session"
marker="$PROTON_PASS_SESSION_DIR/.token-fingerprint"

clear_session() {
	pass-cli logout >/dev/null 2>&1 || true
	# Logout can fail offline. Remove this managed session's cached files too.
	rm -rf "$PROTON_PASS_SESSION_DIR"
}

token=""
if [ "$(uname -s)" = Darwin ]; then
	# A failed Keychain lookup must not fall back to another environment's token.
	token="$(security find-generic-password -s "pass-cli-$session" -a "${USER:-$(id -un)}" -w)" || token=""
else
	token="${PROTON_PASS_TOKEN:-}"
fi
if [ -z "$token" ]; then
	clear_session
	echo "proton:login: no credential for $session; cached session cleared" >&2
	exit 1
fi

if command -v sha256sum >/dev/null 2>&1; then
	fingerprint="$(printf '%s' "$token" | sha256sum | cut -d ' ' -f 1)"
else
	fingerprint="$(printf '%s' "$token" | shasum -a 256 | cut -d ' ' -f 1)"
fi
if [ -f "$marker" ] && [ "$(cat "$marker")" = "$fingerprint" ] && pass-cli info >/dev/null 2>&1; then
	exit 0
fi

clear_session
mkdir -p "$PROTON_PASS_SESSION_DIR"
chmod 700 "$PROTON_PASS_SESSION_DIR"
if ! PROTON_PASS_PERSONAL_ACCESS_TOKEN="$token" pass-cli login; then
	clear_session
	echo "proton:login: authentication failed for $session; cached session cleared" >&2
	exit 1
fi
printf '%s' "$fingerprint" > "$marker"
