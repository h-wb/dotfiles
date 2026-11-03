-- Read-only fnox provider: item titles in repos, share discovery here.
local cmd = require("fnox.cmd")
local json = require("fnox.json")
local fnox = require("fnox")

local function run(ctx, args)
  local opts = { env = {
    PROTON_PASS_AGENT_REASON = ctx.options.agent_reason or "fnox named Proton Pass item lookup",
  } }
  if not cmd.run({ "pass-cli", "info" }, opts).ok then
    fnox.auth_error("Proton Pass session is inactive; run mise run pass:login")
  end
  local argv = { "pass-cli" }
  for _, arg in ipairs(args) do argv[#argv + 1] = arg end
  return cmd.run(argv, opts)
end

local function metadata(ctx, args, key)
  local result = run(ctx, args)
  if not result.ok then error("Proton Pass metadata lookup failed; check the session and grants") end
  local ok, value = pcall(json.decode, result.stdout)
  if not ok or type(value) ~= "table" or type(value[key]) ~= "table" then
    error("Invalid Proton Pass metadata response")
  end
  return value[key]
end

local function single(values, label)
  if #values > 1 then error("Ambiguous Proton Pass " .. label .. "; use unique names") end
  return values[1]
end

local function resolve_item(ctx, name, vault_share, shares)
  local candidates = {}
  if vault_share then
    candidates[1] = vault_share
  else
    -- Only explicit item grants are eligible when the named vault is invisible.
    -- Never search another vault or treat a folder grant as an item grant.
    for _, share in ipairs(shares) do
      if share.share_type == "Item" and share.name == name then
        candidates[#candidates + 1] = share.id
      end
    end
  end
  local matches = {}
  for _, share_id in ipairs(candidates) do
    local items = metadata(ctx, {
      "item", "list", "--share-id=" .. share_id, "--output", "json",
    }, "items")
    for _, item in ipairs(items) do
      if item.title == name then
        matches[#matches + 1] = { share_id = share_id, item_id = item.id }
      end
    end
  end
  local match = single(matches, "item title " .. name)
  if not match then error("No granted Proton Pass item named " .. name) end
  return match
end

local function get_batch(ctx, refs)
  local vault = ctx.options.vault
  if not vault or vault == "" then error("Named Proton Pass provider requires options.vault") end
  local matching_vaults = {}
  for _, entry in ipairs(metadata(ctx, { "vault", "list", "--output", "json" }, "vaults")) do
    if entry.name == vault then matching_vaults[#matching_vaults + 1] = entry.share_id end
  end
  local vault_share = single(matching_vaults, "vault name " .. vault)
  local shares = vault_share and {} or metadata(ctx, { "share", "list", "--output", "json" }, "shares")
  local items, values = {}, {}
  for _, ref in ipairs(refs) do
    local name, field = ref:match("^(.+)/([^/]+)$")
    if not name or name:find("^pass://") then error("Expected Item Title/field, not an ID or URI") end
    if not items[name] then items[name] = resolve_item(ctx, name, vault_share, shares) end
    local item = items[name]
    local result = run(ctx, {
      "item", "view", "--share-id=" .. item.share_id, "--item-id=" .. item.item_id,
      "--field", field,
    })
    if result.ok then
      values[ref] = result.stdout:gsub("\r?\n$", "")
    elseif not result.stderr:lower():find("field does not exist", 1, true) then
      -- CLI diagnostics can contain private content; do not copy them into logs.
      error("Proton Pass read failed for " .. ref .. "; check the session, grant and field name")
    end
  end
  return values
end

return {
  get = function(ctx, ref) return get_batch(ctx, { ref })[ref] end,
  get_batch = get_batch,
  test = function(ctx)
    if not cmd.run({ "pass-cli", "info" }).ok then
      fnox.auth_error("Proton Pass session is inactive; run mise run pass:login")
    end
  end,
}
