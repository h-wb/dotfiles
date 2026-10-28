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
        target = self.home / ".paseo/config.json"
        target.parent.mkdir()
        before = {"version": 2, "theme": "dark", "agents": {"providers": {
            "claude": {"enabled": True, "custom": "keep"},
            "codex": {"enabled": True}}}}
        target.write_text(json.dumps(before))
        self.mise("bootstrap", "dotfiles", "apply", "--yes")
        after = json.loads(target.read_text())
        providers = after["agents"]["providers"]
        self.assertIn("VIBE_MCP_SERVERS", providers.pop("mistral-vibe")["env"])
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
        self.assertTrue(config["agents"]["providers"]["claude"]["enabled"])

    def test_paseo_merge_refuses_invalid_json(self):
        target = self.home / ".paseo/config.json"
        target.parent.mkdir()
        target.write_text('{"unfinished":')
        result = self.mise("bootstrap", "dotfiles", "apply", "--yes", ok=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(target.read_text(), '{"unfinished":')

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
