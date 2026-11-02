import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import tomllib
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "conf.d/paseo/tasks/policy.py"


class PaseoPolicy(unittest.TestCase):
    def test_generated_configs_and_scope_transition(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            policy = {
                "scopes": {
                    "general": {"providers": ["claude", "codex", "mistral-vibe"], "mcp_url": "https://mcp-general.example/mcp", "memory_url": "http://memini-general/mcp"},
                    "private": {"providers": ["mistral-vibe"], "mcp_url": "https://mcp-private.example/mcp", "memory_url": "http://memini-private/mcp", "metadata_provider": "mistral-vibe"},
                },
                "providers": {"claude": {"allowed_data_scopes": ["general"]}, "codex": {"allowed_data_scopes": ["general"]}, "mistral-vibe": {"allowed_data_scopes": ["general", "private"]}},
            }
            policy_file = home / "policy.json"
            policy_file.write_text(json.dumps(policy))
            (home / ".paseo").mkdir()
            (home / ".paseo/config.json").write_text(json.dumps({"daemon": {"port": 9999}, "agents": {"providers": {"custom-cloud": {"enabled": True}}}}))
            (home / ".codex").mkdir()
            (home / ".codex/config.toml").write_text('model = "keep-me"\n[mcp_servers.unrelated]\nurl = "https://keep.example"\n')
            env = dict(os.environ, HOME=tmp, PASEO_HOME=str(home / ".paseo"), CODEX_HOME=str(home / ".codex"), PASEO_DATA_POLICY=str(policy_file), PASEO_DATA_SCOPE="general")
            def run():
                return subprocess.run([sys.executable, str(SCRIPT)], env=env, capture_output=True, text=True)
            self.assertEqual(0, run().returncode)
            codex = tomllib.loads((home / ".codex/config.toml").read_text())
            self.assertEqual("keep-me", codex["model"])
            self.assertIn("unrelated", codex["mcp_servers"])
            self.assertEqual({"x-api-key": "MCP_API_KEY"}, codex["mcp_servers"]["toolhive-general"]["env_http_headers"])
            first = (home / ".codex/config.toml").read_text()
            self.assertEqual(0, run().returncode)
            self.assertEqual(first, (home / ".codex/config.toml").read_text())
            env["PASEO_DATA_SCOPE"] = "private"
            self.assertEqual(0, run().returncode)
            result = json.loads((home / ".paseo/config.json").read_text())
            self.assertEqual(9999, result["daemon"]["port"])
            providers = result["agents"]["providers"]
            self.assertFalse(providers["claude"]["enabled"])
            self.assertFalse(providers["codex"]["enabled"])
            self.assertFalse(providers["custom-cloud"]["enabled"])
            self.assertTrue(providers["mistral-vibe"]["enabled"])
            self.assertEqual([{"provider": "mistral-vibe"}], result["agents"]["metadataGeneration"]["providers"])
            servers = json.loads(providers["mistral-vibe"]["env"]["VIBE_MCP_SERVERS"])
            self.assertEqual(["toolhive-private"], [s["name"] for s in servers])
            before = (home / ".paseo/config.json").read_text()
            env["PASEO_DATA_SCOPE"] = "typo"
            self.assertNotEqual(0, run().returncode)
            self.assertEqual(before, (home / ".paseo/config.json").read_text())
            policy_file.unlink()
            self.assertNotEqual(0, run().returncode)
            self.assertEqual(before, (home / ".paseo/config.json").read_text())


if __name__ == "__main__":
    unittest.main()
