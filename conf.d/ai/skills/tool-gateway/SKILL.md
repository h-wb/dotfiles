---
name: tool-gateway
description: Use when a task needs a homelab tool (the cluster, Flux, GitHub, Grafana, tasks, Home Assistant and so on) through the `toolhive` MCP server. Covers how to find the right tool and call it safely.
---

# Using the tool gateway

The `toolhive` server shows only two tools: `find_tool` and `call_tool`. Every
real tool sits behind them.

## Find, then call

1. Search with `find_tool` before anything else. Use literal keywords: the
   product or server name plus the action, such as "grafana dashboard" or
   "flux reconcile". Search leans on keywords and returns at most four tools,
   so a vague sentence finds little.
2. Tool names look like `<server>_<tool>`. Copy the exact name from the result.
   Never guess one.
3. Call it with `call_tool`, passing arguments exactly as the returned schema
   says: same names, same types, nothing extra.

If nothing fits, search again with the server name alone ("grafana") before
concluding the tool does not exist.

## Skip the search for these

Each search returns full schemas, a few thousand tokens. These names are
stable; call them directly and search only when one is refused.

| Tool | Arguments |
| --- | --- |
| `kubectl_kubectl_generic` | `command` (no `kubectl` prefix). Read verbs only: get, describe, logs, events, top, explain. No exec. |
| `kubectl_kubectl_logs` | `pod_name` (or `deployment/x`), `namespace`, `tail`, `since`, `container` |
| `flux_reconcile_flux_resource` | `kind`, `name`, `namespace`, `with_source` |
| `grafana_list_datasources` | none. Gives the uids the next two need; they are not `prometheus` or `loki`. |
| `grafana_query_prometheus` | `datasourceUid`, `expr`, `queryType` (`instant`), `startTime`, `endTime` (`now`) |
| `grafana_query_loki_logs` | `datasourceUid`, `logql`, `startRfc3339`, `endRfc3339`, `limit`, `format` (`compact`). The store is VictoriaLogs: LogsQL, fields like `kubernetes.pod_name`. |
| `n8n_search_workflow_executions` | `workflowId`, `status` (list), `limit` |
| `n8n_get_workflow_execution` | `workflowId`, `executionId`, `includeData`, `nodeNames` |

## Keep results small

A result cannot be filtered after it arrives. Ask for less: `tail` and `since`
on logs, a `jsonpath` or field selector on `get`, `limit` on searches,
`nodeNames` on executions, `format: compact` on log queries.

With a shell and a token, `gh` and `git` are cheaper than the GitHub tools.

## Reads and writes

- Lookups are free: list, get, search, describe.
- Before anything that changes state, say what you are about to do and wait
  for a yes, unless you were already told to proceed.
- After a write, read the thing back to confirm it took.

## Slow first search

The first search after the gateway restarts can take about a minute while it
indexes its tools. Wait for it; do not retry in a loop.
