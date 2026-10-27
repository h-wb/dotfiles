# The `anki:addon` task: link the add-ons into Anki and write their meta.json.
# update_enabled=false: Anki's updater deletes a link, then fails to reinstall.
# Bind 0.0.0.0 only ever with a key; without one an existing file is kept.
# Keys go into the JSON unescaped, so keep them alphanumeric.
ADDONS="$HOME/.local/share/Anki2/addons21"
mkdir -p "$ADDONS"

# meta <addon id> <name> <key> <config>
meta() {
  if [ -n "$3" ]; then
    rm -f "$ADDONS/$1/meta.json"  # umask only applies to a new file
    ( umask 077
      printf '{"update_enabled": false, "config": %s}\n' "$4" > "$ADDONS/$1/meta.json" )
  elif [ ! -f "$ADDONS/$1/meta.json" ]; then
    printf '%s\n' '{"update_enabled": false}' > "$ADDONS/$1/meta.json"
    echo "[info] no key for $2; it stays on 127.0.0.1"
  fi
}

AC="$("$HOME/.local/bin/mise" where http:anki-connect)" || exit 1
ln -sfn "$AC/plugin" "$ADDONS/2055492159"
meta 2055492159 AnkiConnect "${ANKICONNECT_API_KEY:-}" \
  "{\"webBindAddress\": \"0.0.0.0\", \"apiKey\": \"${ANKICONNECT_API_KEY:-}\"}"

# The Host check must allow the name ToolHive dials (home-ops: default/neko-ankimcp).
MCP="$("$HOME/.local/bin/mise" where http:anki-mcp-server)" || exit 1
ln -sfn "$MCP" "$ADDONS/124672614"
meta 124672614 AnkiMCP "${ANKIMCP_API_KEY:-}" \
  "{\"http_host\": \"0.0.0.0\", \"http_api_key\": \"${ANKIMCP_API_KEY:-}\", \"http_allowed_hosts\": [\"neko-ankimcp.default.svc.cluster.local:*\"]}"
