# The `bootstrap` task: what `mise bootstrap` runs last, after packages,
# dotfiles and tools. Everything here is image state that a pod roll resets, or
# a one-time cost that lands on the PVC. Safe to repeat; run by `sh`, not
# templated.

# Login shell for `kubectl exec` shells. /etc/passwd is image state, so this is
# re-applied every roll; the terminal emulator gets fish from terminalrc instead.
FISH="$(command -v fish || true)"
if [ -n "$FISH" ] && [ "$(getent passwd "$(id -un)" | cut -d: -f7)" != "$FISH" ]; then
  sudo chsh -s "$FISH" "$(id -un)" || true
fi

# Glyphs for the starship prompt. ~/.local/share/fonts is on the PVC, so this is a one-time cost.
FONTDIR="$HOME/.local/share/fonts"
mkdir -p "$FONTDIR"
for style in "Regular" "Bold" "Italic" "Bold Italic"; do
  target="$FONTDIR/MesloLGS NF $style.ttf"
  [ -f "$target" ] && continue
  url="https://github.com/romkatv/powerlevel10k-media/raw/master/MesloLGS%20NF%20$(echo "$style" | sed 's/ /%20/g').ttf"
  curl -fsSL "$url" -o "$target" || rm -f "$target"
done
command -v fc-cache >/dev/null 2>&1 && fc-cache -f "$FONTDIR" >/dev/null 2>&1 || true

# Persist the token into gh's own config (~/.config/gh, on the PVC) so `gh` works
# in a terminal later, where GH_TOKEN is not in the environment.
#
# Both `env -u` are load-bearing. While GH_TOKEN is set, `gh auth status` reports
# "logged in (GH_TOKEN)" — so the obvious `! gh auth status` guard is always false
# and this block never runs — and `gh auth login` refuses outright: "The value of
# the GH_TOKEN environment variable is being used for authentication ... first
# clear the value from the environment."
if [ -n "${GH_TOKEN:-}" ] && command -v gh >/dev/null 2>&1 &&
  ! env -u GH_TOKEN -u GITHUB_TOKEN gh auth status >/dev/null 2>&1; then
  if printf %s "$GH_TOKEN" | env -u GH_TOKEN -u GITHUB_TOKEN gh auth login --with-token; then
    echo "[info] gh authenticated and stored"
  else
    echo "[warn] gh auth login failed"
  fi
fi

# The image is UTC and /etc resets on every pod roll, so this is re-applied each
# session. mise [env] TZ covers mise-run processes; this covers the desktop apps
# and any plain shell, which never see mise's env.
WANT_TZ="America/New_York"
if [ -f "/usr/share/zoneinfo/$WANT_TZ" ] &&
  [ "$(readlink /etc/localtime 2>/dev/null)" != "/usr/share/zoneinfo/$WANT_TZ" ]; then
  sudo ln -sf "/usr/share/zoneinfo/$WANT_TZ" /etc/localtime &&
    echo "[info] timezone set to $WANT_TZ"
fi
