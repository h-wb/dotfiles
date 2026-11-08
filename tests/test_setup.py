import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import tomllib
import unittest


ROOT = Path(__file__).resolve().parents[1]
MISE = Path(os.environ.get("MISE_TEST_BIN") or shutil.which("mise")).resolve()
LAYERS = {
    "personal": ["workstation", "personal"],
    "neko": ["workstation", "pod", "neko"],
    "cachyos": ["workstation", "cachyos"],
    "paseo": ["pod", "paseo"],
}


class SetupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="dotfiles-test-")
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        self.repo = self.home / ".dotfiles"
        shutil.copytree(ROOT, self.repo, ignore=shutil.ignore_patterns(
            ".git", ".DS_Store", "*.local.toml", "__pycache__"))
        self.bin = self.home / ".local/bin"
        self.bin.mkdir(parents=True)
        (self.bin / "mise").symlink_to(MISE)
        self.env = {
            "HOME": str(self.home),
            "PATH": f"{self.bin}:/usr/bin:/bin:/usr/sbin:/sbin",
            "MISE_CONFIG_DIR": str(self.repo),
            "MISE_DATA_DIR": str(self.home / ".local/share/mise"),
            "MISE_CACHE_DIR": str(self.home / ".cache/mise"),
            "MISE_STATE_DIR": str(self.home / ".local/state/mise"),
            "MISE_SYSTEM_CONFIG_DIR": str(self.home / "system"),
            "MISE_AUTO_ENV": "false",
            "MISE_OFFLINE": "true",
            "MISE_SELF_UPDATE_AUTO": "false",
            "MISE_NOT_FOUND_AUTO_INSTALL": "false",
            "MISE_YES": "1",
            "NO_COLOR": "1",
        }
        self.select("paseo")

    def select(self, machine):
        (self.repo / "miserc.local.toml").write_text(
            "env = " + json.dumps(LAYERS[machine]) + "\n")

    def run_cmd(self, *args, ok=True, env=None):
        result = subprocess.run(args, cwd=self.home, env=env or self.env,
                                text=True, capture_output=True, timeout=60)
        if ok:
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result

    def mise(self, *args, **kwargs):
        return self.run_cmd(str(MISE), *args, **kwargs)

    def fake(self, name, body):
        path = self.bin / name
        if path.is_symlink():
            path.unlink()
        path.write_text("#!/bin/sh\n" + body + "\n")
        path.chmod(0o755)

    def fake_mise(self):
        self.fake("mise", '''
printf '%s\n' "$*" >> "$HOME/mise.calls"
case "$1" in
--version) echo "${TEST_VERSION:-2026.10.19}" ;;
self-update) exit "${TEST_UPDATE_EXIT:-0}" ;;
config)
  if grep -q workstation "$HOME/.dotfiles/miserc.local.toml"; then
    echo "$HOME/.dotfiles/config.workstation.toml"
  else
    echo "$HOME/.dotfiles/conf.d/paseo/mise.paseo.toml"
  fi ;;
which) exit 1 ;;
exec)
  export PROTON_PASS_KEY_PROVIDER=fs
  while [ "$1" != -- ]; do shift; done
  shift
  exec "$@" ;;
esac
''')

    def test_machine_configs_and_tasks(self):
        for machine, layers in LAYERS.items():
            with self.subTest(machine=machine):
                self.select(machine)
                configs = self.mise("config").stdout
                for other in LAYERS:
                    self.assertEqual(f".{other}.toml" in configs, other == machine)
                for layer in ("workstation", "pod"):
                    self.assertEqual(f".{layer}.toml" in configs, layer in layers)
                self.mise("tasks", "validate", "--errors-only")
                for line in self.mise("tasks", "--hidden", "--no-header").stdout.splitlines():
                    self.mise("tasks", "info", line.split()[0])

    def test_lockfiles_and_sidecars(self):
        self.mise("install", "--locked", "--dry-run", "npm:chrome-devtools-mcp")
        lock = tomllib.loads((self.repo / "mise.workstation.lock").read_text())
        bws = lock["tools"]["bitwarden-secrets-manager"][0]
        for key, value in bws.items():
            if key.startswith("platforms."):
                self.assertIn("/bws-v", value["url"])
                self.assertTrue(value["url"].endswith(".zip"))
        graph = next(self.repo.glob(".mise/locks/mise.paseo/**/aube-lock.yaml"))
        original = graph.read_text()
        graph.write_text(original + "\n# corrupted\n")
        result = self.mise("install", "--locked", "--dry-run", "npm:chrome-devtools-mcp", ok=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("digest mismatch", result.stderr)
        graph.unlink()
        result = self.mise("install", "--locked", "--dry-run", "npm:chrome-devtools-mcp", ok=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("dependency sidecar", result.stderr)

    def test_named_proton_provider_is_installed_for_every_machine(self):
        # Keep unrelated machine post-dotfiles hooks outside this focused check.
        self.fake("mise", "exit 0")
        for machine in LAYERS:
            with self.subTest(machine=machine):
                self.select(machine)
                target = self.home / ".config/fnox/proton-pass-items.lua"
                self.mise("bootstrap", "dotfiles", "apply", "--yes", str(target))
                source = self.repo / "conf.d/proton-pass/provider.lua"
                self.assertEqual(target.read_text(), source.read_text())
                self.assertEqual(target.stat().st_mode & 0o777, 0o600)

    def doctor(self):
        result = self.mise("doctor", "project", "--json", ok=False)
        report = json.loads(result.stdout)
        self.assertFalse(report["errors"], report)
        return {item["name"]: item["status"] for item in report["checks"]}

    def test_doctor_rejects_invalid_inactive_config_and_wrong_symlink(self):
        self.mise("bootstrap", "dotfiles", "apply", "--yes")
        self.run_cmd("git", "-C", str(self.repo), "init", "-q")
        self.run_cmd("git", "-C", str(self.repo), "add", ".")
        checks = self.doctor()
        for check in ("wiring", "config-keys", "file-modes", "tasks"):
            self.assertEqual(checks[check], "pass", checks)
        bad = self.repo / "conf.d/pod/mise.inactive.toml"
        for content in ('[broken', '[settings]\nnot_a_mise_setting = true\n'):
            bad.write_text(content)
            self.assertEqual(self.doctor()["config-keys"], "fail")
        bad.unlink()
        other = self.home / "unrelated"
        other.mkdir()
        self.run_cmd("git", "-C", str(other), "init", "-q")
        link = self.home / ".config/mise"
        link.unlink()
        link.symlink_to(other)
        self.assertEqual(self.doctor()["wiring"], "fail")

    def test_upgrade_preview_does_not_self_update(self):
        self.fake_mise()
        self.fake("pass-cli", "exit 0")
        self.fake("fnox", 'printf "%s\\n" "$*" > "$HOME/fnox.calls"')
        minimal = self.home / "minimal"
        minimal.mkdir()
        source = (self.repo / "config.workstation.toml").read_text()
        (minimal / "config.toml").write_text(
            '[vars]\nrepo = ' + json.dumps(str(self.repo)) + '\n' +
            source[source.index("[tasks.apply]"):])
        self.mise("run", "apply", "--dry-run", "--upgrade",
                  env={**self.env, "MISE_CONFIG_DIR": str(minimal)})
        self.assertFalse((self.home / "mise.calls").exists())
        self.assertIn("bootstrap --dry-run --upgrade", (self.home / "fnox.calls").read_text())

    def test_paseo_merge_preserves_app_state_and_version(self):
        # Defaults only fill missing keys; agent config is merged by home-ops.
        target = self.home / ".paseo/config.json"
        target.parent.mkdir()
        before = {"version": 2, "theme": "dark", "agents": {"providers": {
            "claude": {"enabled": True, "custom": "keep"}}}}
        target.write_text(json.dumps(before))
        self.mise("bootstrap", "dotfiles", "apply", "--yes")
        after = json.loads(target.read_text())
        self.assertIn("fresh-worktrees", after.pop("plugins"))
        self.assertTrue(after.pop("pluginsEnabled"))
        self.assertEqual(after, before)
        stamp = target.stat().st_mtime_ns
        self.mise("bootstrap", "dotfiles", "apply", "--yes")
        self.assertEqual(target.stat().st_mtime_ns, stamp)
        self.assertFalse((self.home / ".kube/main.yaml").exists())

    def test_paseo_merge_creates_defaults(self):
        self.mise("bootstrap", "dotfiles", "apply", "--yes")
        config = json.loads((self.home / ".paseo/config.json").read_text())
        self.assertEqual(config["version"], 1)
        self.assertNotIn("agents", config)

    def apply_ai(self, **env):
        self.mise("bootstrap", "dotfiles", "apply", "--yes", env={**self.env, **env})

    def test_ai_paseo_general_renders_claude_and_opencode_mcp(self):
        # Keys present in the env must stay literal refs, never be rendered.
        self.apply_ai(MCP_API_KEY="secret-value", MEMINI_API_KEY="secret-value")
        target = self.home / ".claude/.claude.json"
        self.assertNotIn("secret-value", target.read_text())
        servers = json.loads(target.read_text())["mcpServers"]
        # In-cluster and keyless: the gateway's NetworkPolicy admits this pod.
        self.assertEqual(servers["toolhive"], {"type": "http", "url": "http://vmcp-mcp-ops.llm.svc.cluster.local:4483/mcp"})
        self.assertEqual(servers["memini"]["url"],
                         "http://memini-general.llm.svc.cluster.local:8080/mcp")
        self.assertEqual(servers["memini"]["headers"],
                         {"Authorization": "Bearer ${MEMINI_API_KEY}"})
        self.assertEqual(servers["chrome-devtools"]["args"],
                         ["--browserUrl", "http://127.0.0.1:9222"])
        self.assertFalse((self.home / ".claude.json").exists())
        target = self.home / ".config/opencode/opencode.json"
        self.assertNotIn("secret-value", target.read_text())
        opencode = json.loads(target.read_text())
        self.assertEqual(set(opencode), {"$schema", "mcp", "plugins"})
        oc = opencode["mcp"]["servers"]
        self.assertEqual(oc["toolhive"], {"type": "remote", "url": "http://vmcp-mcp-ops.llm.svc.cluster.local:4483/mcp"})
        self.assertEqual(set(oc), {"toolhive", "memini", "chrome-devtools"})
        self.assertEqual(opencode["plugins"][0]["options"]["base_url"],
                         "http://memini-general.llm.svc.cluster.local:8080")

    def test_ai_paseo_private_uses_the_private_gateway_and_memini(self):
        self.apply_ai(PASEO_DATA_SCOPE="private")
        servers = json.loads((self.home / ".claude/.claude.json").read_text())["mcpServers"]
        self.assertEqual(set(servers), {"toolhive", "memini", "chrome-devtools"})
        self.assertEqual(servers["toolhive"], {"type": "http", "url": "http://vmcp-mcp-gateway.llm.svc.cluster.local:4483/mcp"})
        self.assertEqual(servers["memini"]["url"],
                         "http://memini-private.llm.svc.cluster.local:8080/mcp")
        opencode = json.loads((self.home / ".config/opencode/opencode.json").read_text())
        self.assertEqual(set(opencode["mcp"]["servers"]),
                         {"toolhive", "memini", "chrome-devtools"})
        self.assertEqual(opencode["plugins"][0]["options"]["base_url"],
                         "http://memini-private.llm.svc.cluster.local:8080")

    def vibe(self):
        return tomllib.loads((self.home / ".vibe/config.toml").read_text())

    def vibe_servers(self):
        return {v["name"]: v for v in self.vibe()["mcp_servers"]}

    def test_ai_paseo_codex_and_vibe_follow_the_scope(self):
        self.apply_ai(PASEO_DATA_SCOPE="private")
        codex = tomllib.loads((self.home / ".codex/config.toml").read_text())["mcp_servers"]
        self.assertEqual(set(codex), {"toolhive", "memini", "chrome-devtools"})
        self.assertEqual(codex["toolhive"], {"url": "http://vmcp-mcp-gateway.llm.svc.cluster.local:4483/mcp"})
        self.assertEqual(set(self.vibe_servers()), {"toolhive", "memini", "chrome-devtools"})
        self.apply_ai()
        general = self.vibe_servers()
        self.assertEqual(set(general), {"toolhive", "memini", "chrome-devtools"})
        self.assertEqual(general["toolhive"], {
            "name": "toolhive", "transport": "streamable-http", "url": "http://vmcp-mcp-ops.llm.svc.cluster.local:4483/mcp"})
        self.assertEqual(general["memini"]["url"],
                         "http://memini-general.llm.svc.cluster.local:8080/mcp")

    def test_ai_workstation_configs_reference_the_key_by_name(self):
        # `workstation` without a class, then personal for Claude Desktop.
        (self.repo / "miserc.local.toml").write_text('env = ["workstation"]\n')
        target = self.home / ".claude.json"
        before = {"oauthAccount": {"email": "x@y.z"},
                  "mcpServers": {"custom": {"type": "http", "url": "https://custom/mcp"}}}
        target.write_text(json.dumps(before))
        codex = self.home / ".codex/config.toml"
        codex.parent.mkdir()
        codex.write_text('model = "gpt-6"\n\n[mcp_servers.mine]\nurl = "https://mine/mcp"\n')
        vibe = self.home / ".vibe/config.toml"
        vibe.parent.mkdir()
        vibe.write_text('active_model = "devstral"\n\n[[mcp_servers]]\nname = "hand-added"\n'
                        'transport = "streamable-http"\nurl = "https://old/mcp"\n')
        self.apply_ai(MCP_API_KEY="secret-value", MEMINI_API_KEY="secret-value",
                      SECRET_DOMAIN="example.test")  # fnox supplies it during `apply`
        for path in (target, codex, vibe):
            self.assertNotIn("secret-value", path.read_text())
        after = json.loads(target.read_text())
        self.assertEqual(after["oauthAccount"], before["oauthAccount"])
        # Claude and Codex are general: mcp-general, plus memini-general directly.
        self.assertEqual(set(after["mcpServers"]), {"custom", "toolhive", "memini"})
        self.assertEqual(after["mcpServers"]["toolhive"], {
            "type": "http", "url": "https://mcp-general.example.test/mcp",
            "headers": {"x-api-key": "${MCP_API_KEY}"}})
        self.assertEqual(after["mcpServers"]["memini"], {
            "type": "http", "url": "https://memini-general.example.test/mcp",
            "headers": {"Authorization": "Bearer ${MEMINI_API_KEY}"}})
        codex = tomllib.loads(codex.read_text())
        self.assertEqual(codex["model"], "gpt-6")
        self.assertEqual(set(codex["mcp_servers"]), {"mine", "toolhive", "memini"})
        self.assertEqual(codex["mcp_servers"]["memini"]["bearer_token_env_var"], "MEMINI_API_KEY")
        # Vibe is private: mcp-private and memini-private. Its own keys survive;
        # its server array is ours, whole.
        self.assertEqual(self.vibe()["active_model"], "devstral")
        servers = self.vibe_servers()
        self.assertEqual(set(servers), {"toolhive", "memini"})
        self.assertEqual(servers["memini"]["url"], "https://memini-private.example.test/mcp")
        self.assertEqual(servers["memini"]["auth"], {"type": "static", "api_key_env": "MEMINI_API_KEY"})
        self.assertEqual(servers["toolhive"]["url"], "https://mcp-private.example.test/mcp")
        self.assertEqual(servers["toolhive"]["auth"], {
            "type": "static", "api_key_env": "MCP_API_KEY",
            "api_key_header": "x-api-key", "api_key_format": "{token}"})
        self.assertFalse((self.home / ".claude/.claude.json").exists())
        self.assertFalse((self.home / ".config/opencode/opencode.json").exists())
        # Claude Desktop: its mcp-remote shim, Desktop's own keys survive.
        self.select("personal")
        desktop = self.home / "Library/Application Support/Claude/claude_desktop_config.json"
        desktop.parent.mkdir(parents=True)
        desktop.write_text(json.dumps({"preferences": {"theme": "dark"}}))
        self.mise("bootstrap", "dotfiles", "apply", "--yes", str(desktop),
                  env={**self.env, "MCP_API_KEY": "secret-value", "MEMINI_API_KEY": "secret-value",
                       "SECRET_DOMAIN": "example.test"})
        self.assertNotIn("secret-value", desktop.read_text())
        config = json.loads(desktop.read_text())
        self.assertEqual(config["preferences"], {"theme": "dark"})
        bridge = f"{self.home}/.local/share/mise/shims/mcp-remote"
        self.assertEqual(config["mcpServers"], {
            "toolhive": {"command": bridge, "args": [
                "https://mcp-general.example.test/mcp", "--header", "x-api-key:${MCP_API_KEY}"]},
            "memini": {"command": bridge, "args": [
                "https://memini-general.example.test/mcp", "--header", "Authorization:Bearer ${MEMINI_API_KEY}"]}})

    def test_ai_workstation_without_a_domain_leaves_servers_out(self):
        # The domain is never committed: fnox supplies SECRET_DOMAIN from Proton
        # Pass during `apply`. Any render without it leaves the gateway and memini
        # servers out, and the merge keeps what the last apply wrote.
        self.assertIn("SECRET_DOMAIN", tomllib.loads((self.repo / "fnox.toml").read_text())["secrets"])
        (self.repo / "miserc.local.toml").write_text('env = ["workstation"]\n')
        self.apply_ai()
        self.assertEqual({}, json.loads((self.home / ".claude.json").read_text()).get("mcpServers", {}))
        for path in (".codex/config.toml", ".vibe/config.toml"):
            target = self.home / path
            self.assertNotIn("mcp_servers", tomllib.loads(target.read_text()) if target.exists() else {})
        self.apply_ai(SECRET_DOMAIN="example.test")
        servers = {"toolhive", "memini"}
        self.assertEqual(servers, set(json.loads((self.home / ".claude.json").read_text())["mcpServers"]))
        self.apply_ai()
        self.assertEqual(servers, set(json.loads((self.home / ".claude.json").read_text())["mcpServers"]))
        self.assertEqual({"toolhive", "memini"}, set(self.vibe_servers()))

    def test_ai_wrappers_run_agents_under_the_ai_fnox_config(self):
        # Each wrapper's fnox profile is its agent's scope var; Desktop's mcp-remote is Claude's.
        expected = {"conf.d/ai/mise.workstation.toml": {"claude": "claude", "codex": "codex", "vibe": "vibe"},
                    "conf.d/ai/mise.personal.toml": {"mcp-remote": "claude"}}
        for path, agents in expected.items():
            wrappers = tomllib.loads((self.repo / path).read_text())["wrappers"]
            self.assertEqual(set(wrappers), set(agents))
            for name, wrapper in wrappers.items():
                with self.subTest(wrapper=name):
                    self.assertEqual(wrapper["command"], "fnox")
                    self.assertEqual(wrapper["args"], [
                        "-c", "{{ mise_config_dir }}/conf.d/ai/fnox.toml",
                        "-P", "{{ vars.%s_scope }}" % agents[name],
                        "--if-missing", "warn", "--non-interactive", "exec", "--", name])
        # Pods take the key from their env: no wrapper outside workstations.
        self.assertNotIn("wrappers", (self.repo / "conf.d/ai/mise.paseo.toml").read_text())

    def test_ai_fnox_config_holds_only_the_agents_secrets(self):
        agents = tomllib.loads((self.repo / "conf.d/ai/fnox.toml").read_text())
        self.assertNotIn("secrets", agents)  # only per-scope profiles
        self.assertEqual(set(agents["providers"]), {"automation"})
        profiles = {name: {k for k, v in p["secrets"].items() if v.get("env", True)}
                    for name, p in agents["profiles"].items()}
        self.assertEqual(profiles, {"general": {"MCP_API_KEY", "MEMINI_API_KEY"},
                                    "private": {"MCP_API_KEY", "MEMINI_API_KEY"}})
        # A variable one scope holds is stripped from the others, never inherited.
        names = set().union(*profiles.values())
        for name, p in agents["profiles"].items():
            self.assertEqual(set(p["secrets"]), names, name)
        # Every scope an agent defaults to has a profile to run under.
        scopes = {v for k, v in tomllib.loads(
            (self.repo / "conf.d/ai/mise.toml").read_text())["vars"].items() if k.endswith("_scope")}
        self.assertEqual(scopes, set(profiles))
        repo = tomllib.loads((self.repo / "fnox.toml").read_text())
        self.assertNotIn("MCP_API_KEY", repo["secrets"])
        self.assertNotIn("profiles", repo)

    def test_paseo_merge_refuses_invalid_json(self):
        target = self.home / ".paseo/config.json"
        target.parent.mkdir()
        target.write_text('{"unfinished":')
        result = self.mise("bootstrap", "dotfiles", "apply", "--yes", ok=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(target.read_text(), '{"unfinished":')

    def mock_proton(self):
        self.fake("uname", 'echo "${TEST_OS:-Linux}"')
        self.fake("security", '''
printf '%s\\n' "$*" >> "$HOME/keychain.calls"
[ -n "${TEST_KEYCHAIN_TOKEN:-}" ] || exit 1
printf '%s' "$TEST_KEYCHAIN_TOKEN"
''')
        self.fake("pass-cli", '''
printf '%s:%s\\n' "${PROTON_PASS_SESSION_DIR##*/}" "$*" >> "$HOME/pass.calls"
case "$1" in
info) [ -f "$PROTON_PASS_SESSION_DIR/authenticated" ] && [ "${TEST_SESSION_EXPIRED:-0}" != 1 ] ;;
logout)
    [ "${TEST_LOGOUT_FAIL:-0}" != 1 ] || exit 1
    rm -f "$PROTON_PASS_SESSION_DIR/authenticated" ;;
login)
    mkdir -p "$PROTON_PASS_SESSION_DIR"
    # Simulate a partial cache even when the login is rejected.
    printf '%s' "$PROTON_PASS_PERSONAL_ACCESS_TOKEN" > "$PROTON_PASS_SESSION_DIR/authenticated"
    [ "${TEST_LOGIN_FAIL:-0}" != 1 ] ;;
esac
''')

    def proton_login(self, session="home-ops", **env):
        return self.mise("run", "--skip-tools", "proton:login", session,
                         ok=False, env={**self.env, **env})

    def test_proton_login_rotates_reuses_and_refreshes_only_its_session(self):
        self.mock_proton()
        session = self.home / ".local/state/pass-cli/home-ops"
        other = self.home / ".local/state/pass-cli/obsidian-workspace/authenticated"
        other.parent.mkdir(parents=True)
        other.write_text("other-session")
        for token, expired, expected_logins in (("first", "0", 1), ("first", "0", 1),
                                                ("second", "0", 2), ("second", "1", 3)):
            with self.subTest(token=token, expired=expired):
                result = self.proton_login(PROTON_PASS_TOKEN=token, TEST_SESSION_EXPIRED=expired)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertEqual((session / "authenticated").read_text(), token)
                self.assertEqual((self.home / "pass.calls").read_text().count("home-ops:login\n"), expected_logins)
                self.assertEqual(other.read_text(), "other-session")
                self.assertEqual(session.stat().st_mode & 0o777, 0o700)
                self.assertEqual((session / ".token-fingerprint").stat().st_mode & 0o777, 0o600)

    def test_proton_login_clears_cached_access_when_token_removed_or_rejected(self):
        self.mock_proton()
        session = self.home / ".local/state/pass-cli/home-ops"
        for failure in ({"PROTON_PASS_TOKEN": "", "TEST_LOGOUT_FAIL": "1"},
                        {"PROTON_PASS_TOKEN": "rejected-dummy-token", "TEST_LOGIN_FAIL": "1"}):
            with self.subTest(failure=failure):
                result = self.proton_login(PROTON_PASS_TOKEN="old-dummy-token")
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                result = self.proton_login(**failure)
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(session.exists())
                for token in ("old-dummy-token", "rejected-dummy-token"):
                    self.assertNotIn(token, result.stdout + result.stderr)
                    self.assertNotIn(token, (self.home / "pass.calls").read_text())

    def test_proton_login_uses_macos_keychain_and_does_not_fall_back(self):
        self.mock_proton()
        env = {"TEST_OS": "Darwin", "USER": "fixture-user", "PROTON_PASS_TOKEN": "unrelated-dummy-token"}
        result = self.proton_login(TEST_KEYCHAIN_TOKEN="keychain-first", **env)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        session = self.home / ".local/state/pass-cli/home-ops"
        self.assertEqual((session / "authenticated").read_text(), "keychain-first")
        self.assertIn("-s pass-cli-home-ops -a fixture-user -w", (self.home / "keychain.calls").read_text())
        result = self.proton_login(TEST_KEYCHAIN_TOKEN="keychain-second", **env)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual((session / "authenticated").read_text(), "keychain-second")
        result = self.proton_login(**env)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(session.exists())

    def test_proton_login_is_global_and_repo_wrapper_uses_named_session(self):
        self.mock_proton()
        project = self.home / "project"
        project.mkdir()
        (project / "mise.toml").write_text('''
[env]
PROTON_PASS_SESSION_DIR = "{{env.HOME}}/.local/state/pass-cli/obsidian-workspace"
[tasks."pass:login"]
extends = "proton-login"
env.PROTON_PASS_LOGIN_SESSION = "obsidian-workspace"
''')
        for monorepo in (False, True):
            with self.subTest(monorepo=monorepo):
                if monorepo:
                    config = project / "mise.toml"
                    config.write_text("monorepo_root = true\n" + config.read_text())
                result = self.mise("-C", str(project), "run", "--skip-tools", "pass:login", ok=False,
                                   env={**self.env, "PROTON_PASS_TOKEN": "repo-dummy-token"})
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        session = self.home / ".local/state/pass-cli/obsidian-workspace"
        self.assertEqual((session / "authenticated").read_text(), "repo-dummy-token")
        self.assertFalse((self.home / ".local/state/pass-cli/paseo-general").exists())

    def test_proton_login_rejects_session_paths_before_mutation(self):
        self.mock_proton()
        result = self.proton_login("../outside", PROTON_PASS_TOKEN="dummy-token")
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.home / "pass.calls").exists())

    def test_proton_login_finishes_before_task_secrets_are_resolved(self):
        self.mock_proton()
        self.fake("fnox", '''
if [ "$1" = --version ]; then echo 'fnox 1.42.1'; exit 0; fi
case "$*" in
*--describe*)
    printf '%s\\n' '{"schema":1,"fnox_version":"1.42.1","profile":["default"],"keys":[{"key":"FIXTURE_SECRET","kind":"secret","env":"exec","injectable":{"exec":true,"shell":false}}],"dynamic_leases":[]}' ;;
*)
    [ -f "$PROTON_PASS_SESSION_DIR/authenticated" ] || exit 1
    printf '%s\\n' resolved >> "$HOME/fnox.calls"
    printf '%s\\n' '{"schema":1,"fnox_version":"1.42.1","scope":"exec","profile":["default"],"set":{"FIXTURE_SECRET":"dummy-secret"},"files":{},"remove":[],"missing":[],"leases":[]}' ;;
esac
''')
        project = self.home / "secret-project"
        project.mkdir()
        (project / "mise.toml").write_text('''
[settings]
experimental = true
[env]
PROTON_PASS_SESSION_DIR = "{{env.HOME}}/.local/state/pass-cli/obsidian-workspace"
[secrets.fnox]
[tasks."pass:login"]
extends = "proton-login"
env.PROTON_PASS_LOGIN_SESSION = "obsidian-workspace"
[tasks.consume]
depends = ["pass:login"]
secrets = ["FIXTURE_SECRET"]
run = 'test -n "$FIXTURE_SECRET" && touch "$HOME/consumed"'
''')
        (project / "fnox.toml").write_text('[secrets.FIXTURE_SECRET]\nvalue = "unused"\n')
        args = ("-C", str(project), "run", "--skip-tools", "consume")
        result = self.mise(*args, ok=False, env={**self.env, "PROTON_PASS_TOKEN": "dummy-token"})
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue((self.home / "consumed").exists())
        calls = (self.home / "fnox.calls").read_text()
        (self.home / "consumed").unlink()
        result = self.mise(*args, ok=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.home / "consumed").exists())
        self.assertEqual(calls, (self.home / "fnox.calls").read_text())

    def test_pipelines_cluster_profile_tracks_host_scope(self):
        target = self.home / "Repositories/pipelines/mise.local.toml"
        for scope, expected in [("", "cluster"), ("general", "paseo-general-cluster")]:
            with self.subTest(scope=scope):
                self.mise("bootstrap", "dotfiles", "apply", "--yes", "--force",
                          str(target), env={**self.env, "PASEO_DATA_SCOPE": scope})
                config = tomllib.loads(target.read_text())
                self.assertEqual(config["secrets"]["fnox"]["profile"], expected)

    def test_sento_profile_reaches_task_secret_resolution(self):
        project = self.home / "sento-profile-project"
        project.mkdir()
        source = self.repo / "conf.d/paseo/projects/sento/mise.toml"
        (project / "mise.toml").write_text("[settings]\nexperimental = true\n" + source.read_text().replace(
            'run = "bash scripts/watch-api.sh"',
            "run = 'test -n \"$SENTO_PROWLARR_API_KEY\"'"))
        (project / "fnox.toml").write_text('[secrets]\n')
        keys = ["SENTO_QBITTORRENT_USERNAME", "SENTO_QBITTORRENT_PASSWORD",
                "SENTO_PROWLARR_API_KEY"]
        describe = json.dumps({"schema": 1, "fnox_version": "1.46.0",
            "profile": ["default"], "keys": [{"key": key, "kind": "secret",
            "env": "exec", "injectable": {"exec": True, "shell": False}}
            for key in keys], "dynamic_leases": []})
        export = json.dumps({"schema": 1, "fnox_version": "1.46.0",
            "scope": "exec", "profile": ["default"],
            "set": {key: "dummy-secret" for key in keys}, "files": {},
            "remove": [], "missing": [], "leases": []})
        self.fake("fnox", f'''
if [ "$1" = --version ]; then echo 'fnox 1.46.0'; exit 0; fi
printf '%s' "$FNOX_PROFILE" > "$HOME/resolved-profile"
case "$*" in
*--describe*) printf '%s\\n' '{describe}' ;;
*) printf '%s\\n' '{export}' ;;
esac
''')
        for scope, explicit, expected in [
            ("", None, "default"), ("general", None, "paseo-general"),
            ("private", None, "default"), ("general", "custom", "custom"),
        ]:
            with self.subTest(scope=scope, explicit=explicit):
                env = {**self.env, "PASEO_DATA_SCOPE": scope}
                if explicit:
                    env["FNOX_PROFILE"] = explicit
                self.mise("-C", str(project), "run", "--skip-tools", "run:watch",
                          env=env)
                self.assertEqual((self.home / "resolved-profile").read_text(), expected)

    def test_private_bootstrap_skips_general_repositories(self):
        self.fake_mise()
        self.fake("git", "exit 0")
        script = self.repo / "conf.d/paseo/bin/paseo-bootstrap"
        for scope in ["", "general", "private"]:
            with self.subTest(scope=scope):
                log = self.home / "mise.calls"
                log.unlink(missing_ok=True)
                self.run_cmd("sh", str(script), env={**self.env,
                    "DOTFILES_PULLED": "1", "PASEO_DATA_SCOPE": scope})
                command = next(line for line in log.read_text().splitlines()
                               if line.startswith("bootstrap "))
                self.assertEqual("--skip repos" in command, scope == "private")
                self.assertIn("--locked", command)
                self.assertIn("--force-dotfiles", command)

    def test_installer_layers_and_secret_routing(self):
        self.fake_mise()
        self.fake("git", "exit 0")
        self.fake("pass-cli", '''
[ "$PROTON_PASS_KEY_PROVIDER" = fs ] || exit 1
printf '%s\n' "$*" >> "$HOME/pass.calls"
''')
        self.fake("fnox", '''
printf '%s\n' "$*" >> "$HOME/fnox.calls"
while [ "$1" != -- ]; do shift; done
shift
exec "$@"
''')
        for machine, layers in LAYERS.items():
            with self.subTest(machine=machine):
                for log in self.home.glob("*.calls"):
                    log.unlink()
                self.run_cmd("sh", str(self.repo / "install.sh"),
                             env={**self.env, "DOTFILES_ENV": machine})
                actual = tomllib.loads((self.repo / "miserc.local.toml").read_text())
                self.assertEqual(actual["env"], layers)
                self.assertEqual((self.home / "fnox.calls").exists(), "workstation" in layers)
                calls = (self.home / "mise.calls").read_text()
                self.assertIn("bootstrap --yes --force-dotfiles", calls)
                self.assertNotIn("@latest", calls)

    def test_installer_rejects_unknown_class_before_side_effects(self):
        self.fake_mise()
        self.fake("git", 'echo touched > "$HOME/git.calls"')
        result = self.run_cmd("sh", str(self.repo / "install.sh"), ok=False,
                              env={**self.env, "DOTFILES_ENV": 'bogus"'})
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.home / "git.calls").exists())
        self.assertFalse((self.home / "mise.calls").exists())

    def ensure_mise(self, **extra):
        return self.run_cmd("sh", "-c", '. "$HOME/.dotfiles/scripts/provision.sh"; ensure_mise',
                            ok=False, env={**self.env, **extra})

    def test_failed_download_does_not_run_partial_installer(self):
        (self.bin / "mise").unlink()
        self.fake("curl", '''
while [ "$1" != -o ]; do shift; done
printf 'touch "$HOME/partial-ran"\n' > "$2"
exit 22
''')
        self.assertNotEqual(self.ensure_mise().returncode, 0)
        self.assertFalse((self.home / "partial-ran").exists())

    def test_minimum_version_failures_stop_bootstrap(self):
        self.fake_mise()
        for exit_code in ("0", "1"):
            with self.subTest(update_exit=exit_code):
                result = self.ensure_mise(TEST_VERSION="2026.9.1", TEST_UPDATE_EXIT=exit_code)
                self.assertNotEqual(result.returncode, 0)

    def test_neko_protects_either_kubeconfig(self):
        self.fake_mise()
        self.env["DOTFILES_PULLED"] = "1"
        self.fake("timeout", 'shift; exec "$@"')
        for name in (None, "main.yaml", "edge.yaml"):
            with self.subTest(kubeconfig=name):
                kube = self.home / ".kube"
                kube.mkdir(exist_ok=True)
                for path in kube.iterdir():
                    path.unlink()
                if name:
                    (kube / name).write_text("fixture credentials\n")
                (self.home / "mise.calls").write_text("")
                self.run_cmd("sh", str(self.repo / "conf.d/neko/bin/neko-bootstrap"))
                calls = (self.home / "mise.calls").read_text()
                self.assertEqual("--skip dotfiles" in calls, name is not None)

    def test_neko_hold_prevents_mise_update(self):
        self.fake_mise()
        (self.home / ".neko-hold").touch()
        self.run_cmd("sh", str(self.repo / "conf.d/neko/bin/neko-bootstrap"))
        self.assertFalse((self.home / "mise.calls").exists())

    def test_zsh_noninteractive_path(self):
        if not shutil.which("zsh"):
            self.skipTest("zsh is not installed")
        (self.home / ".zshenv").symlink_to(self.repo / "conf.d/zsh/zshenv")
        result = self.run_cmd("zsh", "-c", "command -v mise; print -r -- $PATH",
                             env={**self.env, "PATH": "/usr/bin:/bin"})
        self.assertEqual(result.stdout.splitlines()[0], str(self.bin / "mise"))
        self.assertIn(str(self.home / ".local/share/mise/shims"), result.stdout)

    def test_zsh_completion_autoload(self):
        if not shutil.which("zsh"):
            self.skipTest("zsh is not installed")
        result = self.run_cmd("zsh", "-f", "-c", '''
fpath=("$HOME/.dotfiles/conf.d/zsh/config/completions" $fpath)
autoload -Uz _mise
BUFFER='mise ta'
CURSOR=${#BUFFER}
typeset -A compstate
compdef() { :; }
compadd() { print -r -- completed; }
_mise
''')
        self.assertIn("completed", result.stdout)


if __name__ == "__main__":
    unittest.main()
