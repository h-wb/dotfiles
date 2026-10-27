# The `claude-desktop:mcp` task: set mcpServers.toolhive-ops in Claude Desktop's
# config, leaving everything else in the file alone. Without the key an
# existing entry is kept. The key travels in `env`, not argv (visible in ps);
# mcp-remote expands ${MCP_OPS_API_KEY} itself. A running Desktop picks the
# change up on its next start.
set -eu
CONF="$HOME/Library/Application Support/Claude/claude_desktop_config.json"
if [ -z "${MCP_OPS_API_KEY:-}" ]; then
  echo "[info] no MCP_OPS_API_KEY; Claude Desktop's MCP servers left as they are"
  exit 0
fi
mkdir -p "$(dirname "$CONF")"
[ -s "$CONF" ] || echo '{}' > "$CONF"
tmp="$(mktemp "$CONF.XXXXXX")"
trap 'rm -f "$tmp"' EXIT
# macOS ships jq; the `jq` on PATH here is a stray mise shim.
/usr/bin/jq --arg cmd "$HOME/.local/share/mise/shims/mcp-remote" '
  .mcpServers["toolhive-ops"] = {
    command: $cmd,
    args: ["https://mcp-ops.wlab.ovh/mcp", "--header", "x-api-key:${MCP_OPS_API_KEY}"],
    env: { MCP_OPS_API_KEY: env.MCP_OPS_API_KEY }
  }' "$CONF" > "$tmp"
if cmp -s "$tmp" "$CONF"; then
  echo "[ok] Claude Desktop already has toolhive-ops"
else
  chmod 600 "$tmp"
  mv "$tmp" "$CONF"
  echo "[ok] toolhive-ops added to Claude Desktop; restart Desktop to load it"
fi
