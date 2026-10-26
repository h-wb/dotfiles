# The `anki:addon` task: link AnkiConnect into Anki and write its meta.json.
# update_enabled=false: Anki's updater deletes the link, then fails to reinstall.
# Bind 0.0.0.0 only ever with the apiKey; without one an existing file is kept.
AC="$("$HOME/.local/bin/mise" where http:anki-connect)" || exit 1
ADDON="$HOME/.local/share/Anki2/addons21/2055492159"
mkdir -p "$(dirname "$ADDON")"
ln -sfn "$AC/plugin" "$ADDON"
if [ -n "${ANKICONNECT_API_KEY:-}" ]; then
  ( umask 077
    printf '{"update_enabled": false, "config": {"webBindAddress": "0.0.0.0", "apiKey": "%s"}}\n' "$ANKICONNECT_API_KEY" > "$ADDON/meta.json" )
elif [ ! -f "$ADDON/meta.json" ]; then
  printf '%s\n' '{"update_enabled": false}' > "$ADDON/meta.json"
  echo "[info] no ANKICONNECT_API_KEY; AnkiConnect stays on 127.0.0.1"
fi
