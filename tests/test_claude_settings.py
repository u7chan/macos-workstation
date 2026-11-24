"""chezmoiでClaude設定をマージし、既存データと不正な設定を保護する。"""

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
CHEZMOI = shutil.which("chezmoi")
JQ = shutil.which("jq")


@unittest.skipUnless(CHEZMOI and JQ, "chezmoi and jq are required")
class ClaudeSettingsTests(unittest.TestCase):
    def test_merge_and_invalid_settings(self):
        """管理対象以外を維持し、繰り返し適用と不正なJSONの停止を確認する。"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home, source = root / "home", root / "source"
            home.mkdir()
            name = "private_dot_claude/modify_private_settings.json.tmpl"
            (source / name).parent.mkdir(parents=True)
            shutil.copyfile(ROOT / "home" / name, source / name)
            config = root / "chezmoi.toml"
            config.write_text("")
            target = home / ".claude/settings.json"

            def apply():
                return subprocess.run(
                    [CHEZMOI, "--source", str(source), "--destination", str(home),
                     "--config", str(config), "--cache", str(root / "cache"),
                     "--persistent-state", str(root / "state"), "apply", "--force", "--no-tty"],
                    env={**os.environ, "HOME": str(home)}, capture_output=True, text=True,
                )

            result = apply()
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(target.read_text()), {
                "theme": "dark", "permissions": {"defaultMode": "auto"},
                "syncClaudeAiSkills": False, "syncClaudeAiPlugins": False,
            })
            target.write_text('{"permissions":{"allow":["Read"]},"statusLine":{"command":"custom"}}')
            for _ in range(2):
                result = apply()
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(json.loads(target.read_text()), {
                    "theme": "dark", "permissions": {"allow": ["Read"], "defaultMode": "auto"},
                    "syncClaudeAiSkills": False, "syncClaudeAiPlugins": False,
                    "statusLine": {"command": "custom"},
                })
            for invalid in ("", "not json", "{} {}", '{"permissions":null}'):
                target.write_text(invalid)
                self.assertNotEqual(apply().returncode, 0)
                self.assertEqual(target.read_text(), invalid)


if __name__ == "__main__":
    unittest.main()
