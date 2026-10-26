# The `cachyos:decky` task: Decky Loader from its official installer. It re-execs
# itself with `sudo "$0"` and uses bash `<<<`, so it can't be piped into sh.
# Plugins come from Decky's store (romm-tender's settings hold a RomM token).
if [ ! -d "$HOME/.steam/steam" ]; then
	echo "[skip] Decky Loader: launch Steam once, then re-run"
	exit 0
fi
tmp="$(mktemp)"
trap 'rm -f "$tmp"' EXIT
curl -fsSL https://github.com/SteamDeckHomebrew/decky-installer/releases/latest/download/install_release.sh -o "$tmp" &&
	sudo bash "$tmp" || echo "[warn] Decky Loader install failed"
