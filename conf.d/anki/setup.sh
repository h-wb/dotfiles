# The `anki:setup` task: link the AnkiConnect add-on into Anki, write its
# config, and have supervisord start Anki. Safe to repeat; run by `sh`.

# AnkiConnect into Anki's add-on folder (~/.local/share/Anki2, on the PVC). The
# link is re-pointed every run, so a version bump of the tool is picked up.
#
# meta.json is where Anki keeps an add-on's user config. AnkiConnect listens on
# 127.0.0.1 with no auth by default; it is opened to the pod network (home-ops
# has a ClusterIP Service for n8n) ONLY together with an apiKey, and only when
# ANKICONNECT_API_KEY is set (fnox.toml, from Proton Pass).
#
# Without the key — a session start with no Proton Pass session — an existing
# meta.json is left alone, the same reasoning as neko-bootstrap's `protect`
# mode. A fresh add-on dir (first install, or a version bump) then has none and
# stays on localhost until a run with secrets. Anki reads this at start, so a
# changed key needs an Anki restart.
#
# update_enabled=false in every variant: Anki checks AnkiWeb for add-on updates
# at start, and its installer deletes the add-on dir first — here that is this
# symlink, and the reinstall then dies on the link's target (FileExistsError),
# leaving Anki with no AnkiConnect at all. The version is pinned in mise.neko.toml.
AC="$("$HOME/.local/bin/mise" where http:anki-connect 2>/dev/null || true)"
if [ -n "$AC" ] && [ -d "$AC/plugin" ]; then
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
fi

# Have supervisord load anki.conf ([bootstrap.files] in mise.neko.toml). `update` only acts
# on a config that is new or changed, so a running Anki is left alone on every
# later run; on a rolled pod this is what starts it.
if [ -f /etc/neko/supervisord/anki.conf ]; then
  sudo supervisorctl -c /etc/neko/supervisord.conf update anki || echo "[warn] supervisorctl update failed"
fi
