"""chezmoiでClaude設定をマージし、既存データと不正な設定を保護する。"""

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
STATUS_LINE = {
    "type": "command",
    "command": "bash ~/.claude/statusline/statusline.sh",
    "refreshInterval": 1,
}
CHEZMOI = shutil.which("chezmoi")
JQ = shutil.which("jq")


@unittest.skipUnless(CHEZMOI and JQ, "chezmoi and jq are required")
class ClaudeSettingsTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.home, self.source = self.root / "home", self.root / "source"
        self.home.mkdir()
        name = "private_dot_claude/modify_private_settings.json.tmpl"
        (self.source / name).parent.mkdir(parents=True)
        shutil.copyfile(ROOT / "home" / name, self.source / name)
        self.config = self.root / "chezmoi.toml"
        self.config.write_text("")
        self.target = self.home / ".claude/settings.json"

    def apply(self):
        return subprocess.run(
            [CHEZMOI, "--source", str(self.source), "--destination", str(self.home),
             "--config", str(self.config), "--cache", str(self.root / "cache"),
             "--persistent-state", str(self.root / "state"), "apply", "--force", "--no-tty"],
            env={**os.environ, "HOME": str(self.home)}, capture_output=True, text=True,
        )

    def test_create(self):
        """未作成の場合に管理対象を作成し、非公開の権限にする。"""
        result = self.apply()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(self.target.read_text()), {
            "theme": "dark", "permissions": {"defaultMode": "auto"},
            "syncClaudeAiSkills": False, "syncClaudeAiPlugins": False,
            "statusLine": STATUS_LINE,
        })
        self.assertEqual(self.target.stat().st_mode & 0o077, 0)

    def test_merge_and_repeat(self):
        """対象外の設定を保持し、繰り返し適用しても内容が変わらない。"""
        self.target.parent.mkdir(parents=True)
        self.target.write_text('{"permissions":{"allow":["Read"]},"hooks":{"keep":"custom"}}')
        for _ in range(2):
            result = self.apply()
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(self.target.read_text()), {
                "theme": "dark", "permissions": {"allow": ["Read"], "defaultMode": "auto"},
                "syncClaudeAiSkills": False, "syncClaudeAiPlugins": False,
                "statusLine": STATUS_LINE, "hooks": {"keep": "custom"},
            })

    def test_status_line_is_replaced(self):
        """既存のstatusLineは管理対象の定義へ置き換え、残りの余分なキーも消す。"""
        self.target.parent.mkdir(parents=True)
        self.target.write_text('{"statusLine":{"type":"command","command":"old","padding":2}}')
        result = self.apply()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(self.target.read_text())["statusLine"], STATUS_LINE)

    def test_invalid_settings_are_preserved(self):
        """不正なJSONや権限設定は変更せず停止する。"""
        self.target.parent.mkdir(parents=True)
        for invalid in ("", "not json", "[]", "{} {}", '{"permissions":null}', '{"permissions":"bad"}'):
            with self.subTest(invalid=invalid):
                self.target.write_text(invalid)
                self.assertNotEqual(self.apply().returncode, 0)
                self.assertEqual(self.target.read_text(), invalid)

    def test_dangling_symlink_is_preserved(self):
        """リンク先がない設定ファイルを上書きせず停止する。"""
        self.target.parent.mkdir(parents=True)
        self.target.symlink_to("missing.json")
        self.assertNotEqual(self.apply().returncode, 0)
        self.assertTrue(self.target.is_symlink())
        self.assertFalse((self.target.parent / "missing.json").exists())


if __name__ == "__main__":
    unittest.main()
