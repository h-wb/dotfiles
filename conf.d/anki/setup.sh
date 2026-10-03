# The `anki:setup` task. Safe to repeat.

AC="$("$HOME/.local/bin/mise" where http:anki-connect 2>/dev/null || true)"
if [ -n "$AC" ] && [ -d "$AC/plugin" ]; then
  ADDON="$HOME/.local/share/Anki2/addons21/2055492159"
  mkdir -p "$(dirname "$ADDON")"
  ln -sfn "$AC/plugin" "$ADDON"
  # meta.json is the add-on's user config.
  # - update_enabled=false: Anki's add-on updater deletes this symlink and then
  #   fails to reinstall, leaving no AnkiConnect at all.
  # - Bind 0.0.0.0 only ever together with the apiKey. Without the key (no
  #   Proton Pass session) an existing file is left alone.
  if [ -n "${ANKICONNECT_API_KEY:-}" ]; then
    ( umask 077
      printf '{"update_enabled": false, "config": {"webBindAddress": "0.0.0.0", "apiKey": "%s"}}\n' "$ANKICONNECT_API_KEY" > "$ADDON/meta.json" )
  elif [ ! -f "$ADDON/meta.json" ]; then
    printf '%s\n' '{"update_enabled": false}' > "$ADDON/meta.json"
    echo "[info] no ANKICONNECT_API_KEY; AnkiConnect stays on 127.0.0.1"
  fi
fi

# Starts Anki on a rolled pod; a no-op when the config is unchanged.
if [ -f /etc/neko/supervisord/anki.conf ]; then
  sudo supervisorctl -c /etc/neko/supervisord.conf update anki || echo "[warn] supervisorctl update failed"
fi
