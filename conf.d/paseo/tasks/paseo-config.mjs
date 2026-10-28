// Merged, not rendered: the daemon keeps its own settings in the same file.
import fs from "node:fs";

const dir = `${process.env.HOME}/.paseo`;
const path = `${dir}/config.json`;
let config = { version: 1 };
try {
  config = JSON.parse(fs.readFileSync(path, "utf8"));
} catch {}
config.agents ??= {};
config.agents.providers ??= {};
config.agents.providers.claude = { ...config.agents.providers.claude, enabled: false };
fs.mkdirSync(dir, { recursive: true });
fs.writeFileSync(path, JSON.stringify(config, null, 2) + "\n");
