"""Run the actual fnox Lua host against a fake, credential-free pass-cli."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
FNOX = os.environ.get("FNOX_TEST_BIN") or shutil.which("fnox")


@unittest.skipUnless(FNOX, "fnox is required for native Lua provider tests")
class ProtonItemTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="proton-items-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.env = {
            "HOME": str(self.root), "PATH": str(self.bin) + os.pathsep + os.defpath,
            "FNOX_CONFIG_DIR": str(self.root / "global"),
            "FNOX_DATA_DIR": str(self.root / "data"), "FNOX_CACHE_DIR": str(self.root / "cache"),
            "FAKE_PASS_ROOT": str(self.root),
        }
        plugin = ROOT / "conf.d/proton-pass/provider.lua"
        (self.root / "fnox.toml").write_text(f'''if_missing = "error"
[providers.pass]
type = "lua"
plugin = {json.dumps(str(plugin))}
options = {{ vault = "Personal", agent_reason = "test named item provider" }}
[secrets]
EMAIL = {{ provider = "pass", value = "Obsidian/email" }}
PASSWORD = {{ provider = "pass", value = "Obsidian/password" }}
''')
        self.state = {
            "vaults": [],
            "shares": [{"id": "-item-share", "name": "Obsidian", "share_type": "Item"}],
            "items": {"-item-share": [{"id": "item-id", "title": "Obsidian"}]},
            "fields": {"email": "dummy@example.invalid", "password": "dummy-password"},
        }
        cli = self.bin / "pass-cli"
        cli.write_text(f"#!{sys.executable}\n" + '''import json, os, pathlib, sys
p = pathlib.Path(os.environ["FAKE_PASS_ROOT"])
args = sys.argv[1:]
state = json.loads((p / "state.json").read_text())
with (p / "calls.jsonl").open("a") as out:
    out.write(json.dumps({"args": args, "reason": os.getenv("PROTON_PASS_AGENT_REASON")}) + "\\n")
if args == ["info"]:
    sys.exit(1 if state.get("expired") else 0)
elif args[:2] == ["vault", "list"]:
    print(json.dumps({"vaults": state["vaults"]}))
elif args[:2] == ["share", "list"]:
    print(json.dumps({"shares": state["shares"]}))
elif args[:2] == ["item", "list"]:
    share = next(arg.split("=", 1)[1] for arg in args if arg.startswith("--share-id="))
    print(json.dumps({"items": state["items"].get(share, [])}))
elif args[:2] == ["item", "view"]:
    if state.get("read_error"):
        print("private-diagnostic-marker", file=sys.stderr)
        sys.exit(1)
    field = args[args.index("--field") + 1]
    if field not in state["fields"]:
        print("Field does not exist: " + field, file=sys.stderr)
        sys.exit(1)
    print(state["fields"][field])
else:
    sys.exit("Unexpected CLI operation")
''')
        cli.chmod(0o755)

    def invoke(self, *args):
        (self.root / "state.json").write_text(json.dumps(self.state))
        return subprocess.run(
            [FNOX, "--no-daemon", "--non-interactive", *args],
            cwd=self.root, env=self.env, text=True, capture_output=True, timeout=20,
        )

    def calls(self):
        return [json.loads(line) for line in (self.root / "calls.jsonl").read_text().splitlines()]

    def test_item_only_grant_resolves_readable_name_and_checks_each_session(self):
        result = self.invoke("get", "EMAIL")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "dummy@example.invalid")
        calls = self.calls()
        for i, call in enumerate(calls):
            if call["args"] != ["info"]:
                self.assertEqual(calls[i - 1]["args"], ["info"])
            if call["args"][:2] == ["item", "view"]:
                self.assertEqual(call["reason"], "test named item provider")
                self.assertIn("--share-id=-item-share", call["args"])
                self.assertIn("--item-id=item-id", call["args"])
        self.assertEqual(sum(c["args"][:2] == ["item", "view"] for c in calls), 1)

    def test_account_access_uses_only_the_named_vault(self):
        self.state["vaults"] = [{"name": "Personal", "share_id": "personal-share"},
                                 {"name": "Other", "share_id": "other-share"}]
        self.state["items"]["personal-share"] = [{"id": "account-item", "title": "Obsidian"}]
        result = self.invoke("get", "EMAIL")
        self.assertEqual(result.returncode, 0, result.stderr)
        calls = self.calls()
        self.assertFalse(any(c["args"][:2] == ["share", "list"] for c in calls))
        self.assertIn("--share-id=personal-share", calls[-1]["args"])

    def test_batch_discovers_item_once_and_fetches_only_requested_fields(self):
        result = self.invoke("exec", "--", sys.executable, "-c",
                             "import os; print(os.environ['EMAIL'], os.environ['PASSWORD'])")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("dummy@example.invalid dummy-password", result.stdout)
        calls = self.calls()
        self.assertEqual(sum(c["args"][:2] == ["item", "list"] for c in calls), 1)
        self.assertEqual(sum(c["args"][:2] == ["item", "view"] for c in calls), 2)

    def test_duplicate_item_names_fail_before_reading_values(self):
        self.state["shares"].append({"id": "second-share", "name": "Obsidian", "share_type": "Item"})
        self.state["items"]["second-share"] = [{"id": "second-item", "title": "Obsidian"}]
        result = self.invoke("get", "EMAIL")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Ambiguous", result.stderr)
        self.assertFalse(any(c["args"][:2] == ["item", "view"] for c in self.calls()))

    def test_missing_field_is_fatal(self):
        del self.state["fields"]["email"]
        result = self.invoke("get", "EMAIL")
        self.assertNotEqual(result.returncode, 0)

    def test_expired_session_stops_before_metadata_or_value_access(self):
        self.state["expired"] = True
        result = self.invoke("get", "EMAIL")
        self.assertNotEqual(result.returncode, 0)
        self.assertTrue(all(c["args"] == ["info"] for c in self.calls()))

    def test_folder_grants_are_not_used_as_item_grants(self):
        self.state["shares"][0]["share_type"] = "Folder"
        result = self.invoke("get", "EMAIL")
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(any(c["args"][:2] == ["item", "view"] for c in self.calls()))

    def test_raw_cli_errors_are_not_logged(self):
        self.state["read_error"] = True
        result = self.invoke("get", "EMAIL")
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("private-diagnostic-marker", result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
