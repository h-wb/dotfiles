import importlib.machinery
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import tomllib
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
MISE = Path(os.environ.get("MISE_TEST_BIN") or shutil.which("mise")).resolve()
# Each machine class and the layers it loads: miserc.toml is the only list.
LAYERS = tomllib.loads((ROOT / "miserc.toml").read_text())["env_sets"]


class SetupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="dotfiles-test-")
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        self.repo = self.home / ".dotfiles"
        # symlinks=True: the catalogue's groups are links, as in a checkout.
        shutil.copytree(ROOT, self.repo, symlinks=True, ignore=shutil.ignore_patterns(
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
        # One class name; miserc.toml's [env_sets] expands it.
        (self.repo / "miserc.local.toml").write_text(
            "env = " + json.dumps([machine]) + "\n")

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
printf '%s\n' "$*${MISE_ENV:+ MISE_ENV=$MISE_ENV}" >> "$HOME/mise.calls"
case "$1" in
--version) echo "${TEST_VERSION:-2026.11.1}" ;;
self-update) exit "${TEST_UPDATE_EXIT:-0}" ;;
bootstrap) exit "${TEST_BOOTSTRAP_EXIT:-0}" ;;
config)
  case "${MISE_ENV:-$(cat "$HOME/.dotfiles/miserc.local.toml" 2>/dev/null)}" in
  *paseo*) echo "$HOME/.dotfiles/conf.d/paseo/mise.paseo.toml" ;;
  *) echo "$HOME/.dotfiles/config.workstation.toml" ;;
  esac ;;
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
                for layer in ("workstation", "pod", "fish"):
                    self.assertEqual(f".{layer}.toml" in configs, layer in layers, layer)
                self.assertEqual("conf.d/macos-miroir-collector/mise.personal.toml" in configs,
                                 machine == "personal")
                self.mise("tasks", "validate", "--errors-only")
                for line in self.mise("tasks", "--hidden", "--no-header").stdout.splitlines():
                    self.mise("tasks", "info", line.split()[0])

    # The envs each machine's own folders may use; `personal` is the MacBook.
    MACHINE_ENVS = {"macos": {"macos", "personal"}, "neko": {"neko"},
                    "cachyos": {"cachyos"}, "paseo": {"paseo", "paseo-overlay"},
                    "code-server": {"code-server"}}

    def test_conf_d_folder_names_say_where_they_load(self):
        # A folder that loads on one machine is named after it (`neko`,
        # `neko-anki`); one that loads on several carries no machine's name.
        for folder in sorted(p for p in (ROOT / "conf.d").iterdir() if p.is_dir()):
            with self.subTest(folder=folder.name):
                files = [f.name for f in folder.glob("mise*.toml") if not f.name.endswith(".local.toml")]
                self.assertTrue(files, "not a fragment: no mise.toml or mise.<env>.toml")
                envs = {name.split(".")[1] if name.count(".") == 2 else "" for name in files}
                owners = [m for m, own in self.MACHINE_ENVS.items() if envs <= own]
                named = [m for m in self.MACHINE_ENVS
                         if folder.name == m or folder.name.startswith(m + "-")]
                self.assertEqual(owners, named, f"loads for {sorted(envs)}")
        # Machines are folders, so the root holds only the shared layers.
        self.assertEqual({p.name for p in ROOT.glob("config*.toml")} - {"config.local.toml"},
                         {"config.toml", "config.workstation.toml"})

    def test_lockfiles_and_sidecars(self):
        self.mise("install", "--locked", "--dry-run", "npm:chrome-devtools-mcp")
        lock = tomllib.loads((self.repo / "mise.workstation.lock").read_text())
        bws = lock["tools"]["bitwarden-secrets-manager"][0]
        for key, value in bws.items():
            if key.startswith("platforms."):
                self.assertIn("/bws-v", value["url"])
                self.assertTrue(value["url"].endswith(".zip"))
        graph = next(self.repo.glob("locks/mise.paseo/**/aube-lock.yaml"))
        original = graph.read_text()
        graph.write_text(original + "\n# corrupted\n")
        result = self.mise("install", "--locked", "--dry-run", "npm:chrome-devtools-mcp", ok=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("digest mismatch", result.stderr)
        graph.unlink()
        result = self.mise("install", "--locked", "--dry-run", "npm:chrome-devtools-mcp", ok=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("dependency sidecar", result.stderr)

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
        bad = self.repo / "conf.d/paseo/mise.inactive.toml"
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

    RESOLVER = "/etc/resolver/k8s-gateway"
    DNS_SECRETS = {"SECRET_DOMAIN": "example.test",
                   "K8S_GATEWAY_IP_MAIN": "10.1.1.1", "K8S_GATEWAY_IP_EDGE": "10.9.9.9"}

    def sandbox_resolver(self):
        # The resolver is root-owned: point its entry into the sandbox, then
        # make sure no declared file is left that an apply would write for real.
        self.select("personal")
        out = self.home / "resolver"
        config = self.repo / "conf.d/macos-k8s-dns/mise.personal.toml"
        text = config.read_text()
        self.assertEqual(text.count(f'[bootstrap.files."{self.RESOLVER}"]'), 1)
        config.write_text(text.replace(f'[bootstrap.files."{self.RESOLVER}"]', f'[bootstrap.files."{out}"]')
                          .replace('owner = "root"\n', "").replace('group = "wheel"\n', ""))
        # This test applies only the resolver, not the other MacBook files.
        (self.repo / "conf.d/macos-miroir-collector/mise.personal.toml").unlink()
        status = self.mise("bootstrap", "files", "status", "--json", env={**self.env, **self.DNS_SECRETS})
        self.assertEqual([entry["id"]["name"] for entry in json.loads(status.stdout)], [str(out)])
        return out

    def test_k8s_dns_resolver_takes_zone_and_nameserver_from_secrets(self):
        # The zone is never committed: the file carries it as `domain`, and is
        # not named after it.
        config = tomllib.loads((ROOT / "conf.d/macos-k8s-dns/mise.personal.toml").read_text())
        self.assertEqual(list(config["bootstrap"]["files"]), [self.RESOLVER])
        self.assertEqual(config["bootstrap"]["secrets"]["k8s_dns_zone"], "SECRET_DOMAIN")
        out = self.sandbox_resolver()

        def apply(ok=True, **env):
            return self.mise("bootstrap", "files", "apply", "--yes", ok=ok,
                             env={**self.env, **self.DNS_SECRETS, **env})

        def want(address):
            return f"domain example.test\nnameserver {address}\n"

        # An unknown cluster falls back to main.
        for cluster, address in (("main", "10.1.1.1"), ("edge", "10.9.9.9"), ("typo", "10.1.1.1")):
            with self.subTest(cluster=cluster):
                apply(k8s_dns_cluster=cluster)
                self.assertEqual(out.read_text(), want(address))
        # The per-machine answer `dns:use` saves.
        self.mise("vars", "k8s_dns_cluster=edge")
        apply()
        self.assertEqual(out.read_text(), want("10.9.9.9"))
        self.mise("vars", "unset", "k8s_dns_cluster")
        apply()
        self.assertEqual(out.read_text(), want("10.1.1.1"))
        # A missing secret aborts and leaves the file alone. The address of the
        # cluster that is not selected is not needed.
        for missing in ("SECRET_DOMAIN", "K8S_GATEWAY_IP_MAIN"):
            with self.subTest(missing=missing):
                self.assertNotEqual(apply(ok=False, **{missing: ""}).returncode, 0)
                self.assertEqual(out.read_text(), want("10.1.1.1"))
        apply(K8S_GATEWAY_IP_EDGE="")
        self.assertEqual(out.read_text(), want("10.1.1.1"))

    def test_miroir_collector_config_requires_zone(self):
        self.select("personal")
        # Do not let the test apply the real /etc/resolver entry.
        (self.repo / "conf.d/macos-k8s-dns/mise.personal.toml").unlink()
        out = self.home / ".config/miroir-collector/config.json"

        def apply(ok=True, **env):
            return self.mise("bootstrap", "files", "apply", "--yes", ok=ok,
                             env={**self.env, **env})

        status = self.mise("bootstrap", "files", "status", "--json",
                           env={**self.env, "SECRET_DOMAIN": "example.test"})
        self.assertEqual({entry["id"]["name"] for entry in json.loads(status.stdout)},
                         {str(out), str(out.parent)})
        missing = apply(ok=False)
        self.assertNotEqual(missing.returncode, 0)
        self.assertIn("miroir_collector_zone", missing.stderr)
        self.assertFalse(out.parent.exists())
        apply(SECRET_DOMAIN="example.test")
        original = out.read_text()
        self.assertEqual(out.stat().st_mode & 0o777, 0o600)
        self.assertEqual(json.loads(original), {
            "state_dir": "~/Library/Application Support/miroir-collector",
            "sources": [{
                "id": "screen_macbook",
                "source": "screenmemory",
                "receive_url": "https://miroir.example.test/api/connections/screen_macbook/receive",
                "token_env": "MIROIR_TOKEN_SCREEN_MACBOOK",
                "options": {
                    "data_dir": "~/Nextcloud/Hugo/Images/ScreenMemory/ScreenMemoryData",
                    "since": "2026-10-20",
                    "media": True,
                },
            }, {
                "id": "messages",
                "source": "apple_messages",
                "receive_url": "https://miroir.example.test/api/connections/messages/receive",
                "token_env": "MIROIR_TOKEN_MESSAGES",
                "options": {"media": True, "names": True},
            }, {
                "id": "browser_macbook",
                "source": "zen_history",
                "receive_url": "https://miroir.example.test/api/connections/browser_macbook/receive",
                "token_env": "MIROIR_TOKEN_BROWSER_MACBOOK",
            }],
        })
        self.assertNotEqual(apply(ok=False, SECRET_DOMAIN="").returncode, 0)
        self.assertEqual(out.read_text(), original)

    def test_miroir_collector_schedule_and_fnox_handoff(self):
        self.select("personal")
        folder = self.repo / "conf.d/macos-miroir-collector"
        fragment = folder / "mise.personal.toml"
        text = fragment.read_text()
        config = tomllib.loads(text)
        self.assertNotIn("miroir.example.test", text)
        self.assertEqual(config["bootstrap"]["secrets"], {"miroir_collector_zone": "SECRET_DOMAIN"})
        tool = "pipx:git+https://github.com/h-wb/miroir#subdirectory=collector"
        lock = tomllib.loads((self.repo / "mise.personal.lock").read_text())
        self.assertEqual(lock["tools"][tool][0]["version"], config["tools"][tool])
        schema = self.mise("config", "explain", "--file", str(fragment)).stdout
        self.assertNotIn("not a key mise reads", schema)
        self.assertEqual(tomllib.loads((folder / "fnox.toml").read_text()), {
            "providers": {"protonpass": {"type": "proton-pass", "vault": "Machines"}},
            "secrets": {
                f"MIROIR_TOKEN_{name.upper()}": {
                    "provider": "protonpass", "value": f"pass://Machines/miroir-collector/{name}",
                } for name in ("screen_macbook", "messages", "browser_macbook")
            },
        })
        agent = config["bootstrap"]["macos"]["launchd"]["agents"]["miroir-collector"]
        self.assertEqual(agent, {
            "program": "~/.local/bin/mise",
            "args": ["run", "--quiet", "miroir:collect"],
            "stdout_path": "~/Library/Logs/miroir-collector.log",
            "stderr_path": "~/Library/Logs/miroir-collector.log",
            "run_at_load": True,
            "start_interval": 3600,
        })
        self.fake("fnox", '''
test "$#" = 11 && test "$1 $2 $3 $4 $5" = '--if-missing error --non-interactive exec -c' &&
  test "$6" = "$HOME/.dotfiles/conf.d/macos-miroir-collector/fnox.toml" &&
  test "$7" = -- && test "$8" = miroir-collector || exit 90
[ "$MISSING" != yes ] || exit 44
export MIROIR_TOKEN_SCREEN_MACBOOK=synthetic-secret-screen
export MIROIR_TOKEN_MESSAGES=synthetic-secret-messages
export MIROIR_TOKEN_BROWSER_MACBOOK=synthetic-secret-browser
shift 7
exec "$@"
''')
        self.fake("miroir-collector", '''
test "$#" = 3 && test "$1 $2" = 'run --config' &&
  test "$3" = "$HOME/.config/miroir-collector/config.json" || exit 91
test "$MIROIR_TOKEN_SCREEN_MACBOOK" = synthetic-secret-screen || exit 92
test "$MIROIR_TOKEN_MESSAGES" = synthetic-secret-messages || exit 93
test "$MIROIR_TOKEN_BROWSER_MACBOOK" = synthetic-secret-browser || exit 94
echo 'collector ran'
''')
        for missing, expected in (("no", 0), ("yes", 44)):
            with self.subTest(missing=missing):
                result = self.mise(*agent["args"][:2], "--skip-tools", agent["args"][2],
                                   ok=False, env={**self.env, "MISSING": missing})
                self.assertEqual(result.returncode, expected, result.stderr)
                self.assertEqual(result.stdout, "collector ran\n" if not expected else "")
                self.assertNotIn("synthetic-secret", result.stdout + result.stderr)

    def test_paseo_leaves_paseo_config_alone(self):
        # Only home-ops' overlay (paseo-overlay layer) merges into it.
        target = self.home / ".paseo/config.json"
        target.parent.mkdir()
        for content in ('{"version": 2, "theme": "dark"}', '{"unfinished":'):
            target.write_text(content)
            self.mise("bootstrap", "dotfiles", "apply", "--yes")
            self.assertEqual(target.read_text(), content)
        self.assertFalse((self.home / ".kube/main.yaml").exists())

    def apply_ai(self, **env):
        self.mise("bootstrap", "dotfiles", "apply", "--yes", env={**self.env, **env})

    def test_ai_paseo_general_renders_claude_and_opencode_mcp(self):
        # Keys present in the env must stay literal refs, never be rendered.
        self.apply_ai(MCP_API_KEY="secret-value", MEMINI_API_KEY="secret-value")
        target = self.home / ".claude/.claude.json"
        self.assertNotIn("secret-value", target.read_text())
        servers = json.loads(target.read_text())["mcpServers"]
        # In-cluster and keyless: the gateway's NetworkPolicy admits this pod.
        self.assertEqual(servers["toolhive"], {"type": "http", "url": "http://vmcp-mcp-general.llm.svc.cluster.local:4483/mcp"})
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
        self.assertEqual(oc["toolhive"], {"type": "remote", "url": "http://vmcp-mcp-general.llm.svc.cluster.local:4483/mcp"})
        self.assertEqual(set(oc), {"toolhive", "memini", "chrome-devtools"})
        self.assertEqual(opencode["plugins"][0]["options"]["base_url"],
                         "http://memini-general.llm.svc.cluster.local:8080")

    def test_ai_paseo_private_uses_the_private_gateway_and_memini(self):
        self.apply_ai(PASEO_DATA_SCOPE="private")
        servers = json.loads((self.home / ".claude/.claude.json").read_text())["mcpServers"]
        self.assertEqual(set(servers), {"toolhive", "memini", "chrome-devtools"})
        self.assertEqual(servers["toolhive"], {"type": "http", "url": "http://vmcp-mcp-private.llm.svc.cluster.local:4483/mcp"})
        self.assertEqual(servers["memini"]["url"],
                         "http://memini-private.llm.svc.cluster.local:8080/mcp")
        opencode = json.loads((self.home / ".config/opencode/opencode.json").read_text())
        self.assertEqual(set(opencode["mcp"]["servers"]),
                         {"toolhive", "memini", "chrome-devtools"})
        self.assertEqual(opencode["plugins"][0]["options"]["base_url"],
                         "http://memini-private.llm.svc.cluster.local:8080")

    def test_ai_paseo_private_reads_general_memory_when_the_pod_has_a_key(self):
        # home-ops gives the private pod a read-only key and the store's address.
        self.apply_ai(PASEO_DATA_SCOPE="private", MEMINI_GENERAL_API_KEY="secret-value",
                      MEMINI_GENERAL_URL="http://memini-general.llm.svc.cluster.local:8080")
        target = self.home / ".config/opencode/opencode.json"
        self.assertNotIn("secret-value", target.read_text())
        opencode = json.loads(target.read_text())["mcp"]["servers"]
        self.assertEqual(set(opencode), {"toolhive", "memini", "general_memory", "chrome-devtools"})
        self.assertEqual(opencode["general_memory"], {
            "type": "remote", "url": "http://memini-general.llm.svc.cluster.local:8080/mcp",
            "headers": {"Authorization": "Bearer {env:MEMINI_GENERAL_API_KEY}"}})
        self.assertEqual(opencode["memini"]["url"], "http://memini-private.llm.svc.cluster.local:8080/mcp")
        self.assertEqual(self.vibe_servers()["general_memory"], {
            "name": "general_memory", "transport": "streamable-http",
            "url": "http://memini-general.llm.svc.cluster.local:8080/mcp",
            "auth": {"type": "static", "api_key_env": "MEMINI_GENERAL_API_KEY"}})
        codex = tomllib.loads((self.home / ".codex/config.toml").read_text())["mcp_servers"]
        self.assertEqual(codex["general_memory"]["bearer_token_env_var"], "MEMINI_GENERAL_API_KEY")
        claude = json.loads((self.home / ".claude/.claude.json").read_text())["mcpServers"]
        self.assertEqual(claude["general_memory"]["headers"],
                         {"Authorization": "Bearer ${MEMINI_GENERAL_API_KEY}"})

    def vibe(self):
        return tomllib.loads((self.home / ".vibe/config.toml").read_text())

    def vibe_servers(self):
        return {v["name"]: v for v in self.vibe()["mcp_servers"]}

    def test_ai_claude_config_dir_is_the_same_everywhere(self):
        for machine in ("personal", "paseo"):
            with self.subTest(machine=machine):
                self.select(machine)
                out = json.loads(self.mise("env", "--json").stdout)
                self.assertEqual(f"{self.home}/.claude", out["CLAUDE_CONFIG_DIR"])

    def test_ai_paseo_urls_come_from_the_pod_env_when_set(self):
        # home-ops owns its service names; dotfiles only has the defaults.
        self.apply_ai(PASEO_DATA_SCOPE="private", TOOLHIVE_URL="http://gw.test/mcp",
                      MEMINI_BASE_URL="http://mem.test", CHROME_CDP_URL="http://127.0.0.1:1")
        servers = json.loads((self.home / ".claude/.claude.json").read_text())["mcpServers"]
        self.assertEqual("http://gw.test/mcp", servers["toolhive"]["url"])
        self.assertEqual("http://mem.test/mcp", servers["memini"]["url"])
        self.assertEqual(["--browserUrl", "http://127.0.0.1:1"], servers["chrome-devtools"]["args"])

    def test_ai_paseo_codex_and_vibe_follow_the_scope(self):
        self.apply_ai(PASEO_DATA_SCOPE="private")
        codex = tomllib.loads((self.home / ".codex/config.toml").read_text())["mcp_servers"]
        self.assertEqual(set(codex), {"toolhive", "memini", "chrome-devtools"})
        self.assertEqual(codex["toolhive"], {"url": "http://vmcp-mcp-private.llm.svc.cluster.local:4483/mcp"})
        self.assertEqual(set(self.vibe_servers()), {"toolhive", "memini", "chrome-devtools"})
        self.assertEqual(self.vibe_servers()["toolhive"]["startup_timeout_sec"], 300)
        self.apply_ai()
        general = self.vibe_servers()
        self.assertEqual(set(general), {"toolhive", "memini", "chrome-devtools"})
        self.assertEqual(general["toolhive"], {
            "name": "toolhive", "transport": "streamable-http", "url": "http://vmcp-mcp-general.llm.svc.cluster.local:4483/mcp",
            "startup_timeout_sec": 300})
        self.assertEqual(general["memini"]["url"],
                         "http://memini-general.llm.svc.cluster.local:8080/mcp")

    SKILL_DIRS = (".claude/skills", ".agents/skills")  # Claude Code; Codex, OpenCode and Vibe

    def skill_meta(self, path):
        head = path.read_text().split("---\n")
        self.assertEqual("", head[0], path)
        return dict(line.split(": ", 1) for line in head[1].splitlines())

    TAKES = {"conf.d/ai/mise.toml": "core",  # every machine and pod
             "conf.d/paseo/mise.paseo.toml": "workshop"}  # the pods also

    def group(self, name, root=None):
        return sorted(p.name for p in ((root or self.repo) / "vendor/skills/groups" / name).iterdir())

    def test_skills_are_declared_from_the_catalogue(self):
        gitmodules = (ROOT / ".gitmodules").read_text()
        self.assertIn("path = vendor/skills", gitmodules)
        self.assertIn("url = https://github.com/h-wb/skills.git", gitmodules)
        for config, group in self.TAKES.items():
            entries = {target: entry for target, entry in
                       tomllib.loads((ROOT / config).read_text())["dotfiles"].items()
                       if "/skills" in target}
            expected = {f"~/{folder}/*": {"source": f"../../vendor/skills/groups/{group}/*",
                                          "mode": "symlink"}
                        for folder in self.SKILL_DIRS}
            self.assertEqual(expected, entries, config)
            names = self.group(group, ROOT)
            self.assertTrue(names, group)
            for name in names:
                with self.subTest(skill=name):
                    meta = self.skill_meta(ROOT / "vendor/skills/groups" / group / name / "SKILL.md")
                    self.assertEqual(name, meta["name"])
                    self.assertGreater(len(meta["description"]), 40)

    def assert_skills(self, names, absent=()):
        for folder in self.SKILL_DIRS:
            for name in names:
                link = self.home / folder / name
                self.assertTrue(link.is_symlink(), link)
                self.assertEqual((self.repo / "vendor/skills/skills" / name).resolve(), link.resolve(), link)
                self.assertEqual(name, self.skill_meta(link / "SKILL.md")["name"])
            for name in absent:
                path = self.home / folder / name
                self.assertFalse(path.exists() or path.is_symlink(), path)

    def add_skill(self, name, group=None):
        folder = self.repo / "vendor/skills/skills" / name
        folder.mkdir()
        (folder / "SKILL.md").write_text(f"---\nname: {name}\ndescription: x\n---\n")
        if group:
            (self.repo / "vendor/skills/groups" / group / name).symlink_to(f"../../skills/{name}")

    def test_only_declared_skills_reach_the_agent_folders(self):
        self.add_skill("ungrouped")
        core, workshop = (self.group(g) for g in self.TAKES.values())
        for layers in (["paseo"], ["workstation"]):
            with self.subTest(layers=layers):
                (self.repo / "miserc.local.toml").write_text("env = " + json.dumps(layers) + "\n")
                self.apply_ai()
                self.assert_skills(core, absent=["ungrouped"])

    def test_paseo_skills_reach_the_pods_only(self):
        core, workshop = (self.group(g) for g in self.TAKES.values())
        (self.repo / "miserc.local.toml").write_text('env = ["workstation"]\n')
        self.apply_ai()
        self.assert_skills(core, absent=workshop)
        self.select("paseo")
        self.apply_ai()
        self.assert_skills(core + workshop)

    def test_group_changes_reach_the_folders_at_the_next_apply(self):
        core = self.group("core")
        self.apply_ai()
        self.add_skill("newcomer", group="core")
        self.apply_ai()
        self.assert_skills(core + ["newcomer"])
        for name in (core[0], "newcomer"):  # still in the catalogue, in no group
            (self.repo / "vendor/skills/groups/core" / name).unlink()
        self.apply_ai()
        self.assert_skills(core[1:], absent=[core[0], "newcomer"])

    def test_a_fresh_clone_gets_the_catalogue_at_main(self):
        env = {**self.env, "GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": "protocol.file.allow",
               "GIT_CONFIG_VALUE_0": "always", "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.test",
               "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.test"}
        catalogue = self.home / "skills"
        shutil.copytree(self.repo / "vendor/skills", catalogue, symlinks=True)
        self.git(catalogue, "init", "-q", "-b", "main", env=env)
        self.git(catalogue, "add", "-A", env=env)
        self.git(catalogue, "commit", "-qm", "catalogue", env=env)
        recorded = self.git(catalogue, "rev-parse", "HEAD", env=env).decode().strip()
        shutil.rmtree(self.repo / "vendor/skills")
        (self.repo / ".gitmodules").unlink()
        self.git(self.repo, "init", "-q", env=env)
        self.git(self.repo, "submodule", "--quiet", "add", "-b", "main", str(catalogue), "vendor/skills", env=env)
        self.git(self.repo, "add", "-A", env=env)
        self.git(self.repo, "commit", "-qm", "dotfiles", env=env)
        (catalogue / "skills/handbook/SKILL.md").write_text(
            (catalogue / "skills/handbook/SKILL.md").read_text() + "\nmerged later\n")
        self.git(catalogue, "commit", "-qam", "later", env=env)
        later = self.git(catalogue, "rev-parse", "HEAD", env=env).decode().strip()
        self.assertNotEqual(recorded, later)
        self.git(self.repo, "submodule", "--quiet", "deinit", "-f", "vendor/skills", env=env)
        self.assertEqual([], list((self.repo / "vendor/skills").iterdir()))
        self.mise("bootstrap", "dotfiles", "apply", "--yes", env=env)
        self.assertEqual(later, self.git(self.repo / "vendor/skills", "rev-parse", "HEAD", env=env).decode().strip())
        self.assert_skills(self.group("core"))

    def test_ai_skills_leave_other_skills_in_the_folder_alone(self):
        # Paseo installs and refreshes its own skills there; Claude keeps `synced`.
        theirs = [self.home / folder / "paseo-advisor/SKILL.md" for folder in self.SKILL_DIRS]
        theirs.append(self.home / ".claude/skills/synced/bucket/notes.md")
        for path in theirs:
            path.parent.mkdir(parents=True)
            path.write_text("theirs\n")
        for _ in range(2):
            self.apply_ai()
        for path in theirs:
            self.assertFalse(path.is_symlink(), path)
            self.assertEqual("theirs\n", path.read_text())
        self.assert_skills(self.group("core"))

    def test_ai_workstation_configs_reference_the_key_by_name(self):
        # `workstation` without a class.
        (self.repo / "miserc.local.toml").write_text('env = ["workstation"]\n')
        target = self.home / ".claude/.claude.json"
        target.parent.mkdir()
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
        self.assertEqual(servers["toolhive"]["startup_timeout_sec"], 300)
        self.assertEqual(servers["toolhive"]["auth"], {
            "type": "static", "api_key_env": "MCP_API_KEY",
            "api_key_header": "x-api-key", "api_key_format": "{token}"})
        self.assertFalse((self.home / ".claude.json").exists())

    def test_tn1_ssh_uses_proton_pass_agent_on_macos_only(self):
        self.select("personal" if sys.platform == "darwin" else "workstation")
        target = self.home / ".ssh/config"
        self.mise("bootstrap", "dotfiles", "apply", "--yes", str(target), env={
            **self.env, "SSH_TRUENAS_HOST": "tn.example", "SSH_TRUENAS_USER": "someone",
        })
        env = {**self.env, "SSH_AUTH_SOCK": str(self.home / "other-agent.sock")}
        result = self.run_cmd("ssh", "-G", "-F", str(target), "TN1", env=env)
        config = dict(line.split(" ", 1) for line in result.stdout.splitlines())
        self.assertEqual(config["hostname"], "tn.example")
        self.assertEqual(config["user"], "someone")
        if sys.platform == "darwin":
            self.assertEqual(os.path.expanduser(config["identityagent"]),
                             str(Path.home() / ".ssh/proton-pass-agent.sock"))
        else:
            self.assertNotIn("identityagent", config)

    def test_workstation_opencode_litellm_profile(self):
        (self.repo / "miserc.local.toml").write_text('env = ["workstation"]\n')
        profile = self.home / ".config/opencode/opencode.json"
        profile.parent.mkdir(parents=True)
        existing = {"providers": {"anthropic": {"settings": {"timeout": 60000}}}}
        profile.write_text(json.dumps(existing))
        self.apply_ai()
        self.assertEqual(json.loads(profile.read_text()), existing)

        self.apply_ai(SECRET_DOMAIN="example.test", LITELLM_API_KEY="test-only")
        self.apply_ai()  # Preserve the last endpoint when rendering without fnox.
        self.assertNotIn("test-only", profile.read_text())
        self.assertEqual(json.loads(profile.read_text())["providers"], {
            **existing["providers"],
            "openai": {"settings": {
                "baseURL": "https://litellm.example.test/v1",
                "apiKey": "{env:LITELLM_API_KEY}",
            }},
        })

    def test_ai_workstation_without_a_domain_leaves_servers_out(self):
        # The domain is never committed: fnox supplies SECRET_DOMAIN from Proton
        # Pass during `apply`. Any render without it leaves the gateway and memini
        # servers out, and the merge keeps what the last apply wrote.
        self.assertIn("SECRET_DOMAIN", tomllib.loads((self.repo / "fnox.toml").read_text())["secrets"])
        (self.repo / "miserc.local.toml").write_text('env = ["workstation"]\n')
        self.apply_ai()
        self.assertEqual({}, json.loads((self.home / ".claude/.claude.json").read_text()).get("mcpServers", {}))
        for path in (".codex/config.toml", ".vibe/config.toml"):
            target = self.home / path
            self.assertNotIn("mcp_servers", tomllib.loads(target.read_text()) if target.exists() else {})
        self.apply_ai(SECRET_DOMAIN="example.test")
        servers = {"toolhive", "memini"}
        self.assertEqual(servers, set(json.loads((self.home / ".claude/.claude.json").read_text())["mcpServers"]))
        self.apply_ai()
        self.assertEqual(servers, set(json.loads((self.home / ".claude/.claude.json").read_text())["mcpServers"]))
        self.assertEqual({"toolhive", "memini"}, set(self.vibe_servers()))

    def test_ai_wrappers_run_agents_under_the_ai_fnox_config(self):
        # Each wrapper's fnox profile is its agent's scope var.
        expected = {"conf.d/ai/mise.workstation.toml": {"claude": "claude", "codex": "codex", "vibe": "vibe"}}
        opencode = None
        for path, agents in expected.items():
            wrappers = tomllib.loads((self.repo / path).read_text())["wrappers"]
            if path.endswith("mise.workstation.toml"):
                opencode = wrappers.pop("opencode")
            self.assertEqual(set(wrappers), set(agents))
            for name, wrapper in wrappers.items():
                with self.subTest(wrapper=name):
                    self.assertEqual(wrapper["command"], "fnox")
                    self.assertEqual(wrapper["args"], [
                        "-c", "{{ mise_config_dir }}/conf.d/ai/fnox.toml",
                        "-P", "{{ vars.%s_scope }}" % agents[name],
                        "--if-missing", "warn", "--non-interactive", "exec", "--", name])
        self.assertEqual(opencode, {"command": "fnox", "args": [
            "-c", "{{ mise_config_dir }}/conf.d/ai/fnox.toml", "-P", "opencode",
            "--no-defaults", "--if-missing", "error", "--non-interactive", "exec", "--", "opencode",
        ]})
        # Pods take the key from their env: no wrapper outside workstations.
        self.assertNotIn("wrappers", (self.repo / "conf.d/ai/mise.paseo.toml").read_text())

    def test_ai_fnox_config_holds_only_the_agents_secrets(self):
        agents = tomllib.loads((self.repo / "conf.d/ai/fnox.toml").read_text())
        self.assertNotIn("secrets", agents)  # only named profiles
        self.assertEqual(set(agents["providers"]), {"protonpass"})
        profiles = {name: {k for k, v in p["secrets"].items() if v.get("env", True)}
                    for name, p in agents["profiles"].items()}
        self.assertEqual(profiles, {"general": {"MCP_API_KEY", "MEMINI_API_KEY"},
                                    "private": {"MCP_API_KEY", "MEMINI_API_KEY"},
                                    "opencode": {"LITELLM_API_KEY"}})
        self.assertEqual(agents["profiles"]["opencode"]["secrets"]["LITELLM_API_KEY"], {
            "provider": "protonpass", "value": "pass://Machines/litellm-workstation/password",
        })
        # A variable one scope holds is stripped from the others, never inherited.
        names = set().union(*profiles.values())
        for name, p in agents["profiles"].items():
            self.assertEqual(set(p["secrets"]), names, name)
        # Every scope an agent defaults to has a profile to run under.
        scopes = {v for k, v in tomllib.loads(
            (self.repo / "conf.d/ai/mise.toml").read_text())["vars"].items() if k.endswith("_scope")}
        self.assertEqual(scopes, set(profiles) - {"opencode"})
        repo = tomllib.loads((self.repo / "fnox.toml").read_text())
        self.assertNotIn("MCP_API_KEY", repo["secrets"])
        self.assertNotIn("profiles", repo)

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

    def test_paseo_login_and_session_dir_share_the_scope_name(self):
        # The pod's bootstrap logs in to the session its tools then read.
        self.mock_proton()
        for scope in ("general", "private"):
            with self.subTest(scope=scope):
                env = {**self.env, "PASEO_DATA_SCOPE": scope, "PROTON_PASS_TOKEN": "dummy-token"}
                result = self.mise("run", "--skip-tools", "paseo:pass-login", ok=False, env=env)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                session = self.home / f".local/state/pass-cli/paseo-{scope}"
                self.assertEqual((session / "authenticated").read_text(), "dummy-token")
                out = json.loads(self.mise("env", "--json", env=env).stdout)
                self.assertEqual(out["PROTON_PASS_SESSION_DIR"], str(session))
                self.assertEqual(out["PROTON_PASS_AGENT_REASON"], f"paseo-{scope} fnox")

    def test_proton_login_holds_one_lock_per_machine(self):
        # Two agents logging in at once would clear and rebuild a session under
        # each other. The template's lock reaches every task that extends it.
        project = self.home / "project"
        project.mkdir()
        (project / "mise.toml").write_text(
            '[tasks."pass:login"]\nextends = "proton-login"\nenv.PROTON_PASS_LOGIN_SESSION = "x"\n')
        for args in (("tasks", "info", "--json", "proton:login"),
                     ("-C", str(project), "tasks", "info", "--json", "pass:login")):
            with self.subTest(args=args):
                self.assertEqual(json.loads(self.mise(*args).stdout)["lock"], ["proton-pass-login"])

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

    def test_repo_checkouts_receive_no_host_copies(self):
        (self.home / "Repositories/miroir").mkdir(parents=True)
        (self.home / "Repositories/sento").mkdir(parents=True)
        self.mise("bootstrap", "dotfiles", "apply", "--yes")
        for path in ("Repositories/miroir/mise.local.toml",
                     "Repositories/sento/mise.local.toml",
                     "Repositories/sento/fnox.toml"):
            self.assertFalse((self.home / path).exists(), path)

    def test_paseo_overlay_layer_loads_only_when_declared(self):
        # The scope overlay (/etc/paseo/config/paseo.json, mounted by home-ops
        # pods) is merged into ~/.paseo/config.json by the `paseo-overlay`
        # layer, which the pods declare after their set. Undeclared — tests,
        # workstations — the entry must not load, so bootstrap never looks for
        # /etc/paseo. The pods' args are asserted in home-ops' tests/test_paseo.py.
        self.select("paseo")
        self.assertNotIn("paseo-overlay", self.mise("config").stdout)
        (self.repo / "miserc.local.toml").write_text(
            'env = ["paseo", "paseo-overlay"]\n')
        self.assertIn("conf.d/paseo/mise.paseo-overlay.toml", self.mise("config").stdout)

    def test_no_declared_environment_loads_the_base_only(self):
        # Nothing is detected: a machine that declares nothing gets config.toml
        # and the shared folders, whatever its paths, and the doctor says why.
        (self.repo / "miserc.local.toml").unlink()
        configs = self.mise("config").stdout
        self.assertNotIn("config.workstation.toml", configs)
        for layer in {name for layers in LAYERS.values() for name in layers} | set(LAYERS):
            self.assertNotIn(f".{layer}.toml", configs, layer)
        self.assertNotIn("is exists", (self.repo / "miserc.toml").read_text())
        self.mise("bootstrap", "dotfiles", "apply", "--yes")
        report = self.mise("doctor", "project", "--json", ok=False).stdout
        wiring = next(c for c in json.loads(report)["checks"] if c["name"] == "wiring")
        self.assertEqual(wiring["status"], "fail")
        self.assertIn("DOTFILES_ENV", wiring["hint"])

    def test_save_env_declares_a_set_and_extra_layers(self):
        # What install.sh and home-ops rely on: mise writes the declaration
        # itself, before it applies anything, so a failed run still leaves it.
        local = self.repo / "miserc.local.toml"
        local.unlink()
        (self.repo / "config.local.toml").write_text(
            '[bootstrap.repos]\n"~/nowhere" = { url = "file:///does/not/exist.git" }\n')
        result = self.mise("bootstrap", "--save-env", "--yes", "--only", "repos", ok=False,
                           env={**self.env, "MISE_ENV": "personal,fish"})
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(tomllib.loads(local.read_text()), {"env": ["personal", "fish"]})
        configs = self.mise("config").stdout
        self.assertIn("conf.d/macos/mise.personal.toml", configs)
        self.assertIn("conf.d/fish/mise.fish.toml", configs)

    URL = "https://github.com/h-wb/dotfiles.git"

    def install(self, ok=True, **extra):
        (self.home / "mise.calls").unlink(missing_ok=True)
        result = self.run_cmd("sh", str(self.repo / "install.sh"), ok=ok, env={**self.env, **extra})
        calls = self.home / "mise.calls"
        return result, calls.read_text().splitlines() if calls.exists() else []

    def test_installer_runs_the_two_steps(self):
        # The checkout with the declaration, then apply: what home-ops runs on the pods.
        self.fake_mise()
        (self.repo / "miserc.local.toml").unlink()
        for machine in ("personal", "cachyos", "cachyos,extra"):
            with self.subTest(machine=machine):
                _, calls = self.install(DOTFILES_ENV=machine, MISE_ENV="inherited")
                # The declared environment, never an activated shell's.
                self.assertEqual(calls, [
                    f"-E {machine} bootstrap --from {self.URL} --from-dir {self.repo} --config-dir . "
                    "--save-env --yes --only final-hook",
                    "run apply"])

    def test_installer_reuses_a_clone_and_its_declaration(self):
        # mise reuses a checkout only when --from is its origin, SSH or not. An
        # existing clone is never pulled: no ref, no --update.
        self.fake_mise()
        self.fake("git", 'echo "git@github.com:h-wb/dotfiles.git"')
        (self.repo / ".git").mkdir()
        _, calls = self.install(MISE_ENV="inherited")
        self.assertEqual(calls, [
            f"bootstrap --from git@github.com:h-wb/dotfiles.git --from-dir {self.repo} --config-dir . "
            "--yes --only final-hook",
            "run apply"])

    def test_installer_needs_an_environment_once_and_a_real_set(self):
        self.fake_mise()
        (self.repo / "miserc.local.toml").unlink()
        result, calls = self.install(ok=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("DOTFILES_ENV", result.stderr)
        self.assertEqual(calls, [])
        for bad in ('bogus"', "paseo,", ",paseo-overlay", "a,,b"):
            with self.subTest(env=bad):
                result, calls = self.install(ok=False, DOTFILES_ENV=bad)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(calls, [])
        # A well-formed name that is no set: the checkout is there, apply never runs.
        result, calls = self.install(ok=False, DOTFILES_ENV="bogus")
        self.assertIn("not a set", result.stderr)
        self.assertEqual(len(calls), 1)

    def test_installer_installs_mise_only_when_missing(self):
        (self.bin / "mise").unlink()
        self.fake("curl", '''
while [ "$1" != -o ]; do shift; done
printf 'touch "$HOME/partial-ran"\\n' > "$2"
exit 22
''')
        result, _ = self.install(ok=False, DOTFILES_ENV="personal")
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.home / "partial-ran").exists())
        # A downloaded installer runs and puts mise where install.sh looks.
        self.fake("curl", '''
while [ "$1" != -o ]; do shift; done
printf '%s\\n' 'cp "$HOME/fake-mise" "$HOME/.local/bin/mise"' > "$2"
''')
        self.fake_mise()
        (self.bin / "mise").rename(self.home / "fake-mise")
        _, calls = self.install(DOTFILES_ENV="personal")
        self.assertEqual(calls[-1], "run apply")

    def apply(self, *args, ok=False, **extra):
        for name in ("mise.calls", "fnox.calls", "pass-cli.calls"):
            (self.home / name).unlink(missing_ok=True)
        (self.home / "mise.calls").touch()
        status = self.home / ".local/state/dotfiles.status"
        status.unlink(missing_ok=True)
        result = self.run_cmd("sh", "-c", 'cd "$HOME/.dotfiles" && exec sh scripts/apply "$@"', "apply", *args,
                              ok=ok, env={**self.env, **extra})
        calls = (self.home / "mise.calls").read_text()
        return result, status.read_text().split()[:2] if status.exists() else None, calls

    FORCE = " --force-dotfiles" if sys.platform.startswith("linux") else ""

    def test_apply_modes(self):
        self.fake_mise()
        self.fake("fnox", 'printf "%s\\n" "$*" >> "$HOME/fnox.calls"\n'
                  'while [ "$1" != -- ]; do shift; done; shift; exec "$@"')
        kube = self.home / ".kube"
        kube.mkdir()
        unattended = f"bootstrap --yes --skip-dirty --locked{self.FORCE}\n"

        with self.subTest("a person without a session stops at the preflight"):
            result, status, calls = self.apply()
            self.assertEqual(result.returncode, 1)
            self.assertEqual(status, ["error", "none"])
            self.assertNotIn("bootstrap", calls)

        with self.subTest("fresh volume, no token"):
            result, status, calls = self.apply("--unattended")
            self.assertEqual(result.returncode, 1)
            self.assertEqual(status, ["degraded", "fresh"])
            self.assertIn(unattended, calls)
            self.assertFalse((self.home / "fnox.calls").exists())

        self.fake("pass-cli", 'printf "%s\\n" "$*" >> "$HOME/pass-cli.calls"; exit 1')
        with self.subTest("fresh volume, token rejected"):
            _, status, calls = self.apply("--unattended", PROTON_PASS_TOKEN="fixture-pat")
            self.assertEqual(status, ["degraded", "fresh"])
            self.assertEqual(calls.count("bootstrap --yes"), 1)
            self.assertIn("login --pat", (self.home / "pass-cli.calls").read_text())

        self.fake("pass-cli", '[ "$1" = login ] && [ "$2" = --pat ]')
        with self.subTest("the pod's token logs in: secrets, once"):
            result, status, calls = self.apply("--unattended", ok=True, PROTON_PASS_TOKEN="fixture-pat")
            self.assertEqual(status, ["ok", "secrets"])
            self.assertEqual(calls.count("bootstrap --yes"), 1)
            self.assertIn(unattended, calls)
            self.assertIn("--if-missing error exec -c fnox.toml -- mise bootstrap",
                          (self.home / "fnox.calls").read_text())

        (kube / "main.yaml").write_text("fixture credentials\n")
        self.fake("pass-cli", 'printf "%s\\n" "$*" >> "$HOME/pass-cli.calls"; exit 1')
        with self.subTest("secrets on disk, token rejected"):
            _, status, calls = self.apply("--unattended", PROTON_PASS_TOKEN="fixture-pat")
            self.assertEqual(status, ["degraded", "protect"])
            self.assertIn("bootstrap --yes --skip-dirty --locked --skip dotfiles\n", calls)
            self.assertFalse((self.home / "fnox.calls").exists())

        (kube / "main.yaml").unlink()
        (kube / "edge.yaml").write_text("fixture credentials\n")
        with self.subTest("either kubeconfig protects"):
            _, status, calls = self.apply("--unattended")
            self.assertEqual(status, ["degraded", "protect"])

        with self.subTest("bootstrap fails"):
            _, status, _ = self.apply("--unattended", TEST_BOOTSTRAP_EXIT="3")
            self.assertEqual(status, ["error", "protect"])

    def test_apply_for_a_person(self):
        # What `mise run apply`, `diff` and `upgrade` always did on the Mac.
        self.fake_mise()
        self.fake("pass-cli", "exit 0")
        self.fake("fnox", 'while [ "$1" != -- ]; do shift; done; shift; exec "$@"')
        _, status, calls = self.apply(ok=True)
        self.assertEqual(status, ["ok", "secrets"])
        self.assertEqual(calls, f"bootstrap --yes{self.FORCE}\n")
        _, status, calls = self.apply("--dry-run", ok=True)
        self.assertEqual(calls, f"bootstrap --dry-run{self.FORCE}\n")
        self.assertIsNone(status)  # a dry run reports nothing
        _, _, calls = self.apply("--upgrade", ok=True)
        self.assertEqual(calls, f"self-update --yes\nbootstrap --yes --upgrade{self.FORCE}\n")
        result, _, _ = self.apply("--pull")
        self.assertEqual(result.returncode, 2)

    def test_apply_task_passes_its_flags(self):
        self.select("code-server")
        (self.repo / "scripts/apply").write_text('echo "$*" > "$HOME/apply.args"; pwd >> "$HOME/apply.args"\n')
        # Offline here: a real `mise run` installs the machine's tools first.
        env = {**self.env, "MISE_TASK_RUN_AUTO_INSTALL": "false"}
        self.mise("run", "apply", "--unattended", "--upgrade", env=env)
        self.assertEqual((self.home / "apply.args").read_text(), f"--upgrade --unattended\n{self.repo}\n")
        self.mise("run", "diff", env=env)
        self.assertEqual((self.home / "apply.args").read_text().splitlines()[0], "--dry-run")

    def test_apply_reports_the_commit_and_a_stale_one(self):
        self.fake_mise()
        git = lambda *a: self.run_cmd("git", "-C", str(self.repo), *a).stdout.strip()
        git("init", "-q")
        git("add", ".")
        git("-c", "user.name=t", "-c", "user.email=t@example.test", "commit", "-qm", "pin")
        pinned = git("rev-parse", "HEAD")
        _, status, _ = self.apply("--unattended", DOTFILES_REF=pinned)
        self.assertEqual(status, ["degraded", "fresh"])
        self.assertTrue((self.home / ".local/state/dotfiles.status").read_text().rstrip().endswith(pinned))
        # home-ops asked for another commit: its fetch failed, this one ran.
        _, status, _ = self.apply("--unattended", DOTFILES_REF="b" * 40)
        self.assertEqual(status, ["stale", "fresh"])
        # neko's session has no git before its apt step: the commit comes from .git/HEAD.
        git("checkout", "-q", "--detach")
        self.fake("git", "exit 127")
        self.apply("--unattended")
        self.assertTrue((self.home / ".local/state/dotfiles.status").read_text().rstrip().endswith(pinned))

    def test_git_credential_follows_the_class(self):
        # The class decides, as miserc.toml picks it, so a pinned class renders
        # its own branch on any machine.
        expect = {
            "neko": "helper = %s/.local/bin/git-credential-fnox" % self.home,
            "paseo": "helper = !gh auth git-credential",
            "code-server": "helper = !%s/.local/share/mise/shims/gh auth git-credential" % self.home,
            "cachyos": "helper = store",
            "personal": None,
        }
        for machine, helper in expect.items():
            with self.subTest(machine=machine):
                self.select(machine)
                self.mise("bootstrap", "dotfiles", "apply", "--yes", "--force")
                config = (self.home / ".config/git/config").read_text()
                if helper is None:
                    self.assertNotIn("helper =", config)
                    continue
                self.assertIn(helper, config)
                self.assertEqual(config.count("helper ="), 1, config)
                self.assertEqual("[safe]" in config, machine == "paseo")

    def test_pod_doctor_reports_the_last_pod_start(self):
        for machine in ("code-server", "neko"):
            with self.subTest(machine=machine):
                self.select(machine)
                self.mise("bootstrap", "dotfiles", "apply", "--yes", "--force")
                state = self.home / ".local/state"
                state.mkdir(parents=True, exist_ok=True)
                (state / "dotfiles.status").unlink(missing_ok=True)
                self.assertEqual(self.doctor()["pod-start"], "fail")
                for line, want in (("ok secrets 2026-11-16 abc", "pass"), ("ok fresh 2026-11-16 abc", "fail"),
                                   ("ok protect 2026-11-16 abc", "fail"),
                                   ("degraded protect 2026-11-16 abc", "fail"),
                                   ("stale secrets 2026-11-16 abc", "fail"),
                                   ("error secrets 2026-11-16 abc", "fail")):
                    with self.subTest(status=line):
                        (state / "dotfiles.status").write_text(line + "\n")
                        self.assertEqual(self.doctor()["pod-start"], want)

    def test_code_server_terminal_and_shell(self):
        self.select("code-server")
        self.mise("bootstrap", "dotfiles", "apply", "--yes")
        settings = json.loads((self.home / ".local/share/code-server/Machine/settings.json").read_text())
        profile = settings["terminal.integrated.defaultProfile.linux"]
        self.assertEqual(settings["terminal.integrated.profiles.linux"][profile]["path"],
                         str(self.home / ".local/share/mise/installs/github-fish-shell-fish-shell/latest/fish"))
        self.assertEqual((self.home / ".config/fish/config.fish").resolve(),
                         (self.repo / "conf.d/fish/config.fish").resolve())
        self.assertEqual((self.home / ".config/starship.toml").resolve(),
                         (self.repo / "conf.d/fish/starship.toml").resolve())
        self.assertFalse((self.home / ".zshrc").exists())

    def test_neko_and_cachyos_use_the_fish_layer(self):
        for machine in ("neko", "cachyos"):
            with self.subTest(machine=machine):
                self.select(machine)
                self.mise("bootstrap", "dotfiles", "apply", "--yes", "--force")
                for target, source in ((".config/fish/config.fish", "conf.d/fish/config.fish"),
                                       (".config/starship.toml", "conf.d/fish/starship.toml")):
                    self.assertEqual((self.home / target).resolve(), (self.repo / source).resolve())
                self.assertIn("ef", self.mise("shell-alias", "ls").stdout)
        machine_file = self.home / ".config/fish/conf.d/cachyos.fish"
        self.assertIn("cachyos-config.fish", machine_file.read_text())
        self.assertIn("dotfiles_native_prompt", machine_file.read_text())

    def test_fish_config_loads(self):
        # The fish layer's config.fish, in both branches: scripts get mise's shims,
        # an interactive shell activates mise (starship only once installed).
        if not shutil.which("fish"):
            self.skipTest("fish is not installed")
        config = self.home / ".config/fish/config.fish"
        config.parent.mkdir(parents=True)
        config.symlink_to(self.repo / "conf.d/fish/config.fish")
        # fish_add_path skips a directory that does not exist yet.
        (self.home / ".local/share/mise/shims").mkdir(parents=True)
        env = {**self.env, "PATH": f"{Path(shutil.which('fish')).parent}:/usr/bin:/bin"}
        result = self.run_cmd("fish", "-c", "command -v mise; string join : $PATH", env=env)
        self.assertEqual(result.stdout.splitlines()[0], str(self.bin / "mise"))
        self.assertIn(str(self.home / ".local/share/mise/shims"), result.stdout)
        self.assertEqual(result.stderr, "")
        result = self.run_cmd("fish", "-i", "-c", "functions -q __mise_env_eval; and echo activated", env=env)
        self.assertIn("activated", result.stdout)

    def test_zsh_noninteractive_path(self):
        if not shutil.which("zsh"):
            self.skipTest("zsh is not installed")
        (self.home / ".zshenv").symlink_to(self.repo / "conf.d/macos/zsh/zshenv")
        result = self.run_cmd("zsh", "-c", "command -v mise; print -r -- $PATH",
                             env={**self.env, "PATH": "/usr/bin:/bin"})
        self.assertEqual(result.stdout.splitlines()[0], str(self.bin / "mise"))
        self.assertIn(str(self.home / ".local/share/mise/shims"), result.stdout)

    def test_zsh_completion_autoload(self):
        if not shutil.which("zsh"):
            self.skipTest("zsh is not installed")
        result = self.run_cmd("zsh", "-f", "-c", '''
fpath=("$HOME/.dotfiles/conf.d/macos/zsh/config/completions" $fpath)
autoload -Uz _mise
BUFFER='mise ta'
CURSOR=${#BUFFER}
typeset -A compstate
compdef() { :; }
compadd() { print -r -- completed; }
_mise
''')
        self.assertIn("completed", result.stdout)

    LAND = ROOT / "scripts" / "land"
    MARKER = "<!-- bot-tintin:land v1 -->"
    GOOD_PATCH = (
        "diff --git a/.github/workflows/ci.yml b/.github/workflows/ci.yml\n"
        "--- a/.github/workflows/ci.yml\n"
        "+++ b/.github/workflows/ci.yml\n"
        "@@ -1 +1,2 @@\n"
        "-old\n"
        "+new\n")

    def comment_body(self, patch, marker=MARKER, fence="````"):
        return f"{marker}\nOne line explaining the change.\n{fence}diff\n{patch}{fence}\n"

    def land_validate(self, body, ok=True):
        comment = self.home / "comment.md"
        comment.write_text(body)
        return self.run_cmd(sys.executable, str(self.LAND), "--validate", str(comment), ok=ok)

    def test_land_validate_accepts_good_comments_and_rejects_bad_ones(self):
        good = (self.GOOD_PATCH,
                "diff --git a/.github/workflows/new.yml b/.github/workflows/new.yml\n"
                "new file mode 100755\n"
                "--- /dev/null\n"
                "+++ b/.github/workflows/new.yml\n"
                "@@ -0,0 +1 @@\n"
                "+x\n",
                # A removed hunk line `--- foo` is not a file header.
                "diff --git a/.github/workflows/ci.yml b/.github/workflows/ci.yml\n"
                "--- a/.github/workflows/ci.yml\n"
                "+++ b/.github/workflows/ci.yml\n"
                "@@ -1,3 +1,3 @@\n"
                " keep\n"
                "--- foo\n"
                "+bar\n",
                # A rename inside .github/workflows/.
                "diff --git a/.github/workflows/old.yml b/.github/workflows/new.yml\n"
                "similarity index 100%\n"
                "rename from .github/workflows/old.yml\n"
                "rename to .github/workflows/new.yml\n")
        for patch in good:
            with self.subTest(patch=patch.splitlines()[0]):
                result = self.land_validate(self.comment_body(patch))
                self.assertIn("diff --git a/.github/workflows/", result.stdout)
        bad = [
            ("path outside .github/workflows/", self.comment_body(
                "diff --git a/README.md b/README.md\n--- a/README.md\n+++ b/README.md\n"
                "@@ -1 +1 @@\n-a\n+b\n")),
            ("'..' component", self.comment_body(
                "diff --git a/.github/workflows/../x b/.github/workflows/../x\n"
                "--- a/.github/workflows/../x\n+++ b/.github/workflows/../x\n"
                "@@ -1 +1 @@\n-a\n+b\n")),
            ("rename out of the dir", self.comment_body(
                "diff --git a/.github/workflows/x.yml b/README.md\n"
                "rename from .github/workflows/x.yml\nrename to README.md\n")),
            ("binary patch", self.comment_body(
                "diff --git a/.github/workflows/blob b/.github/workflows/blob\n"
                "GIT binary patch\n")),
            ("symlink mode", self.comment_body(
                "diff --git a/.github/workflows/link b/.github/workflows/link\n"
                "new file mode 120000\n")),
            ("missing marker", self.comment_body(self.GOOD_PATCH, marker="no marker")),
            ("3-backtick fence", self.comment_body(self.GOOD_PATCH, fence="```")),
        ]
        for name, body in bad:
            with self.subTest(case=name):
                result = self.land_validate(body, ok=False)
                self.assertNotEqual(result.returncode, 0, result.stdout)
                self.assertTrue(result.stderr.startswith("land:"), result.stderr)

    def test_land_validate_rejects_hidden_characters_and_stray_sections(self):
        # What the owner reads must be what git applies: no terminal
        # escapes, CR, bidi controls or non-"\n" line breaks, and no file
        # section outside a diff --git block.
        hunk = self.GOOD_PATCH.replace("+new\n", "+new{}\n")
        bad = [
            ("escape sequence", hunk.format("\x1b[2K\x1b[1A")),
            ("carriage return", hunk.format("\rname: harmless")),
            ("CRLF", self.GOOD_PATCH.replace("\n", "\r\n")),
            ("bidi override", hunk.format("‮")),
            ("bidi isolate", hunk.format("⁦")),
            ("form feed line break", hunk.format("\x0c+++ b/README.md")),
            ("NEL", hunk.format("\x85")),
            ("line separator", hunk.format(" ")),
            ("bare ---/+++ section after a workflow hunk", self.GOOD_PATCH.replace(
                "@@ -1 +1,2 @@", "@@ -1 +1 @@")
                + "--- a/README.md\n+++ b/README.md\n@@ -1 +1 @@\n-a\n+b\n"),
            # The hunk claims two new lines; git ends it at the `---` anyway.
            ("bare section ending a short hunk", self.GOOD_PATCH
                + "--- a/README.md\n+++ b/README.md\n@@ -1 +1 @@\n-a\n+b\n"),
            ("bare rename after a workflow hunk", self.GOOD_PATCH.replace(
                "@@ -1 +1,2 @@", "@@ -1 +1 @@")
                + "rename from .github/workflows/ci.yml\nrename to README.md\n"),
            ("section before the first diff --git", "--- a/README.md\n+++ b/README.md\n"
                "@@ -1 +1 @@\n-a\n+b\n" + self.GOOD_PATCH),
            ("bare mode line", self.GOOD_PATCH.replace("@@ -1 +1,2 @@", "@@ -1 +1 @@")
                + "new mode 120000\n"),
        ]
        for name, patch in bad:
            with self.subTest(case=name):
                result = self.land_validate(self.comment_body(patch), ok=False)
                self.assertNotEqual(result.returncode, 0, result.stdout)
                self.assertTrue(result.stderr.startswith("land:"), result.stderr)
                self.assertEqual(result.stdout, "")
        # Non-ASCII letters and symbols are fine in workflow comments/strings.
        result = self.land_validate(self.comment_body(hunk.format(" # café ✓ 日本")))
        self.assertIn("café ✓ 日本", result.stdout)

    def land_module(self):
        loader = importlib.machinery.SourceFileLoader("land", str(self.LAND))
        spec = importlib.util.spec_from_loader("land", loader)
        module = importlib.util.module_from_spec(spec)
        loader.exec_module(module)
        return module

    def land_git_env(self, global_config=""):
        # No network, no real gh: stubs in self.bin, a throwaway git config.
        config = self.home / "land-gitconfig"
        config.write_text(global_config)
        return {"HOME": str(self.home), "PATH": f"{self.bin}:/usr/bin:/bin",
                "GIT_CONFIG_GLOBAL": str(config), "GIT_CONFIG_NOSYSTEM": "1",
                "GIT_TERMINAL_PROMPT": "0",
                "GIT_AUTHOR_NAME": "Owner", "GIT_AUTHOR_EMAIL": "owner@example.test",
                "GIT_COMMITTER_NAME": "Owner", "GIT_COMMITTER_EMAIL": "owner@example.test"}

    def git(self, cwd, *args, env, input=None):
        result = subprocess.run(["git", "-C", str(cwd), *args], env=env, input=input,
                                capture_output=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout

    def test_land_applies_real_patches_byte_for_byte_despite_gitattributes(self):
        # A modified and a new workflow, generated by git, extracted by land
        # and applied in a clone of a branch whose .gitattributes asks for
        # ident and a filter the owner's global config defines: the
        # committed blob must be exactly the patch result.
        land = self.land_module()
        plain = self.land_git_env()
        origin = self.home / "origin"
        workflows = origin / ".github/workflows"
        workflows.mkdir(parents=True)
        self.git(origin, "init", "-q", "-b", "feature", env=plain)
        (workflows / "ci.yml").write_bytes(b"name: ci\non: push\n")
        self.git(origin, "add", "-A", env=plain)
        self.git(origin, "commit", "-qm", "base", env=plain)
        changes = {
            "modify": {".github/workflows/ci.yml":
                       "name: ci x\n# $Id$ café\non: push\n".encode()},
            "add": {".github/workflows/new.yml": b"on: x\n# $Id$\n"},
        }
        patches = {}
        for name, files in changes.items():
            for path, data in files.items():
                (origin / path).write_bytes(data)
            self.git(origin, "add", "-A", env=plain)
            patches[name] = self.git(origin, "diff", "--cached", env=plain).decode()
            self.git(origin, "reset", "-q", "--hard", env=plain)
        (origin / ".gitattributes").write_text("*.yml ident filter=evil eol=crlf\n")
        self.git(origin, "add", "-A", env=plain)
        self.git(origin, "commit", "-qm", "attributes", env=plain)
        base = self.git(origin, "rev-parse", "HEAD", env=plain).decode().strip()

        evil = self.land_git_env(
            '[filter "evil"]\n\tclean = sed s/x/CLEAN/\n\tsmudge = sed s/x/SMUDGE/\n')
        for name, files in changes.items():
            with self.subTest(patch=name), mock.patch.dict(os.environ, evil, clear=True):
                patch = land.extract_patch(self.comment_body(patches[name]))
                self.assertEqual(patch, patches[name])
                paths = land.validate_patch(patch)
                self.assertEqual(paths, sorted(files))
                clone = str(self.home / f"clone-{name}")
                self.assertEqual(land.clone_branch(str(origin), "feature", clone), base)
                self.assertIn(paths[0], land.check_in_clone(clone, patch, paths))
                land.commit_patch(clone, patch, "7")
                self.assertEqual(os.listdir(clone), [".git"])
                self.assertEqual(self.git(clone, "rev-parse", "HEAD~1", env=evil).decode().strip(),
                                 base)
                for path, data in files.items():
                    self.assertEqual(self.git(clone, "show", f"HEAD:{path}", env=evil), data)
                changed = self.git(clone, "diff", "--name-only", "HEAD~1", "HEAD", env=evil)
                self.assertEqual(changed.decode().split(), sorted(files))

    def stub_gh(self, script):
        gh = self.bin / "gh"
        gh.write_text("#!/bin/sh\n" + script)
        gh.chmod(0o755)

    def test_land_refuses_the_default_branch(self):
        land = self.land_module()
        for head, expected in (("main", "default branch"), ("feature", "no bot-tintin")):
            with self.subTest(head=head):
                self.stub_gh(f"""case "$1 $2" in
  "pr view") echo '{{"state":"OPEN","isCrossRepository":false,"headRefName":"{head}","headRefOid":"abc"}}' ;;
  "repo view") echo main ;;
  "api --paginate") echo '[]' ;;
  *) echo "unexpected gh $*" >&2; exit 1 ;;
esac
""")
                with mock.patch.dict(os.environ, self.land_git_env(), clear=True):
                    with self.assertRaisesRegex(land.LandError, expected):
                        land.land("7", "owner/repo")

    def test_land_pushes_with_gh_credential_not_the_global_helper(self):
        # The prompt shows gh's login, so git must ask gh, whatever helper
        # the global config names; and an insteadOf rewrite is refused.
        land = self.land_module()
        self.stub_gh('[ "$1 $2 $3" = "auth git-credential get" ] || exit 1\n'
                     'echo username=x-access-token; echo password=from-gh-stub\n')
        env = self.land_git_env(
            '[credential]\n\thelper = "!f() { echo password=from-global-helper; }; f"\n')
        fill = subprocess.run(["git", *land.GH_CREDENTIAL, "credential", "fill"],
                              input="protocol=https\nhost=github.com\n\n", env=env,
                              text=True, capture_output=True, timeout=60)
        self.assertEqual(fill.returncode, 0, fill.stderr)
        self.assertIn("password=from-gh-stub", fill.stdout)
        self.assertNotIn("from-global-helper", fill.stdout)

        env = self.land_git_env(
            '[url "ssh://git@example.invalid/"]\n\tinsteadOf = https://github.com/\n')
        clone = self.home / "rewritten"
        self.git(self.home, "init", "-q", str(clone), env=env)
        self.git(clone, "remote", "add", "origin", "https://github.com/owner/repo.git", env=env)
        with mock.patch.dict(os.environ, env, clear=True):
            with self.assertRaisesRegex(land.LandError, "insteadOf"):
                land.push(str(clone), "owner/repo", "feature")

    def test_land_is_not_on_the_paseo_layer(self):
        # `land` pushes as the owner, so its task lives in the workstation
        # layer, which Paseo pods never load (mirrors
        # test_paseo_skills_reach_the_pods_only).
        def task_names():
            return {line.split()[0] for line in
                    self.mise("tasks", "--no-header").stdout.splitlines() if line.strip()}
        self.select("workstation")
        self.assertIn("land", task_names())
        self.select("paseo")
        self.assertNotIn("land", task_names())

    def test_land_task_passes_a_repo_value(self):
        # Declared as `flag "--repo"`, mise took it for a switch and refused
        # `--repo OWNER/NAME` with "unexpected word".
        self.select("workstation")
        result = self.mise("run", "--dry-run", "--skip-tools", "land", "38", "--repo", "owner/name")
        self.assertIn("scripts/land", result.stdout + result.stderr)
        # The dry run prints the command, cut short after the flag.
        self.assertIn("'38' --repo", result.stdout + result.stderr)
        result = self.mise("run", "--dry-run", "--skip-tools", "land", "38")
        self.assertNotIn("--repo", result.stdout + result.stderr)

    def test_paseo_general_pod_commits_as_the_bot(self):
        # The general pod's rendered git identity is the bot (static, from the
        # paseo layer's [vars]); the private pod shares the class but keeps the
        # owner's identity, and so does an unset PASEO_DATA_SCOPE.
        self.select("paseo")
        for scope, name, email in (("general", "bot-tintin[bot]",
                                    "356770504+bot-tintin[bot]@users.noreply.github.com"),
                                   ("private", "h-wb", "owner@example.test"),
                                   (None, "h-wb", "owner@example.test")):
            with self.subTest(scope=scope):
                env = {**self.env, "GIT_EMAIL": "owner@example.test"}
                if scope is None:
                    env.pop("PASEO_DATA_SCOPE", None)
                else:
                    env["PASEO_DATA_SCOPE"] = scope
                self.mise("bootstrap", "dotfiles", "apply", "--yes", env=env)
                lines = (self.home / ".config/git/config").read_text().splitlines()
                section = []
                for line in lines[lines.index("[user]") + 1:]:
                    if line.startswith("["):
                        break
                    section.append(line)
                user = "\n".join(section)
                self.assertIn(f"name = {name}", user)
                self.assertIn(f"email = {email}", user)


if __name__ == "__main__":
    unittest.main()
