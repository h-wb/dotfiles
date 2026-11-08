# ai

The MCP servers every agent harness connects to, defined once for every machine.
`mise.toml` is an env-less folder fragment, so it loads everywhere without a new
env; a class file adds an agent's config where its path or key source differs.

```text
mise.toml              all machines: shared [vars], Claude Code, Codex and Vibe (merged)
mise.workstation.toml  personal, neko, cachyos: public URLs, agent wrappers
mise.personal.toml     MacBook: Claude Desktop's config, the mcp-remote wrapper
mise.paseo.toml        paseo pods: in-cluster URLs, OpenCode
fnox.toml              the only secrets the agents may read (MCP_API_KEY)
config/                the agents' config templates, rendered by the files above
```

## Scopes

Each agent's data scope follows where its model runs, and decides both its
servers and its keys (`*_scope` vars in `mise.toml`, one fnox profile each):

| scope     | agents                                 | servers                                                         |
| --------- | -------------------------------------- | --------------------------------------------------------------- |
| `general` | Claude Code, Claude Desktop, Codex     | `mcp-general` (curated tools, no private data) + memini-general |
| `private` | Vibe (Mistral)                         | `mcp-private` (the whole catalogue) + memini-private            |

home-ops enforces the split. Both gateways are ToolHive VirtualMCPServers over
the same tool group: `mcp-general` (`mcp-ops`) allows a curated list,
`mcp-private` (`mcp-gateway`) everything. ToolHive takes callers anonymously;
the Envoy route of each hostname checks `x-api-key` against that gateway's own
key list (a general key gets a 401 on `mcp-private`), and a NetworkPolicy keeps
in-cluster callers off `mcp-gateway`. Each memini checks its own named client
keys. memini is connected directly, not through the gateway: ToolHive's
optimizer hides gateway tools behind `find_tool`/`call_tool`, and memory tools
should be in view.
On the pods there is one scope per pod (`PASEO_DATA_SCOPE`), so every agent
there takes it; the pods add the in-cluster memini and `chrome-devtools` on the
Chromium sidecar. Merged files keep everything the agent wrote itself; we only
set our servers. Vibe's servers are an array, which a merge replaces whole, so
`config/vibe.toml` is all of them: add one there, not with `vibe mcp add`.

## Domain

Never committed. Workstations build the public URLs from `SECRET_DOMAIN`,
which `mise run apply`'s fnox resolves from Proton Pass
(`Infrastructure/kubernetes-gateway`, field `domain`; repo `fnox.toml`).
Outside `apply` it is empty and the gateway and memini servers are left out;
every agent file is merged, so that keeps what the last `apply` wrote. The
pods need none: they use in-cluster service names.

## Keys

Off the cluster, every agent reads its gateway key from `MCP_API_KEY` and
memini's from `MEMINI_API_KEY`, whatever its scope; no rendered file holds a
key.

- **Workstations**: this folder's `fnox.toml` has a profile per scope with the
  same variable names. mise `[wrappers]` for `claude`, `codex`, `vibe` and
  (MacBook) `mcp-remote` run them under `fnox -c conf.d/ai/fnox.toml -P
  {{ vars.<agent>_scope }} exec`, so changing a scope moves servers and keys
  together. An explicit `-c` turns off fnox's directory search, so neither the
  repo's `fnox.toml` nor a project's reaches an agent; a global
  `~/.config/fnox/config.toml` would still load, so none is kept. Both
  profiles define both variables, so one the parent shell exports is always
  replaced (a variable a scope must not have would be `env = false`, which
  strips it). A wrapper intercepts at PATH level (the shim and
  `mise activate`'s wrapper dir), so a launch from a shell, a script, an IDE or
  launchd is covered alike. A missing or dead Proton Pass item only fails that
  server (`--if-missing warn`).
- **Pods**: no gateway key. They call the gateways' in-cluster services
  (`mcp_<scope>_url` in `mise.paseo.toml`, `mcp_auth = "network"`), and
  home-ops' NetworkPolicy admits only that scope's pod. `MEMINI_API_KEY` comes
  from home-ops' ExternalSecrets in the pod env. The addresses default to
  today's services; home-ops can set them in the pod env instead
  (`TOOLHIVE_URL`, `MEMINI_BASE_URL`, `CHROME_CDP_URL`), so renaming a service
  never needs a dotfiles change.

Not covered: a client that runs its own bundled copy of an agent instead of the
one on PATH.

## Home-ops

The paseo pods run this repo's bootstrap at every start (`mise bootstrap
--from` in home-ops' `tools` init container), so home-ops consumes these definitions
without copying them. It supplies only the inputs: `PASEO_DATA_SCOPE` and the
key env vars. It keeps what is pod-specific in `agents/paseo/<scope>/config/`:
Paseo's providers (`paseo.json`) and OpenCode's models and providers
(`opencode.json` via `OPENCODE_CONFIG`, layered over the global file rendered
here; OpenCode merges both MCP lists).
