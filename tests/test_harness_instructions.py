"""chezmoiによる利用ルール更新が、既存の指示・設定を保持し、アクセス権を広げないことを確認する。

一時ホームで実際のchezmoiを動かし、繰り返し適用・管理部分だけの更新・不正マーカー時の停止を検証する。
実際のユーザーホームは変更しない。
"""

import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


HOME_SOURCE = Path(__file__).resolve().parents[1] / "home"
CHEZMOI = shutil.which("chezmoi")
BEGIN = "<!-- macos-workstation:agent-harness:begin -->"
END = "<!-- macos-workstation:agent-harness:end -->"


@unittest.skipUnless(CHEZMOI, "chezmoi is required for instruction integration tests")
class HarnessInstructionsTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.home = self.root / "home"
        self.source = self.root / "source"
        self.home.mkdir()
        for name in (
            "private_dot_pi/private_agent/modify_private_AGENTS.md",
            "dot_local/bin/executable_agent-harness-exec",
        ):
            target = self.source / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(HOME_SOURCE / name, target)
        self.target = self.home / ".pi/agent/AGENTS.md"
        self.target.parent.mkdir(parents=True)
        self.settings = self.target.with_name("settings.json")
        self.settings.write_text('{"unrelated": true}\n')
        self.config = self.root / "chezmoi.toml"
        self.config.write_text("")

    def apply(self):
        return subprocess.run(
            [
                CHEZMOI, "--source", str(self.source),
                "--destination", str(self.home), "--config", str(self.config),
                "--cache", str(self.root / "cache"),
                "--persistent-state", str(self.root / "state.boltdb"),
                "apply", "--force", "--no-tty",
            ],
            env={**os.environ, "HOME": str(self.home)},
            capture_output=True, text=True, check=False,
        )

    def assert_applied(self):
        result = self.apply()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.settings.read_text(), '{"unrelated": true}\n')
        self.assertTrue(os.access(self.home / ".local/bin/agent-harness-exec", os.X_OK))
        content = self.target.read_text()
        self.assertEqual(content.count(BEGIN), 1)
        self.assertEqual(content.count(END), 1)
        self.assertIn('"$HOME/.local/bin/agent-harness-exec"', content)
        self.assertIn("review-target tests", content)
        self.assertIn("actual installed skill", content)
        return content

    def test_creates_missing_instructions_and_executable_launcher(self):
        content = self.assert_applied()
        self.assertTrue(content.startswith(BEGIN))
        self.assertTrue(content.endswith(f"{END}\n"))

    def test_does_not_widen_access_to_private_pi_data(self):
        paths = (self.home / ".pi", self.target.parent, self.settings)
        for path in paths:
            path.chmod(0o700 if path.is_dir() else 0o600)
        self.assert_applied()
        for path in (*paths, self.target):
            self.assertEqual(path.stat().st_mode & 0o077, 0)

    def test_preserves_existing_content_and_is_idempotent(self):
        for existing in ("# Existing instructions\n\nKeep $HOME and 日本語.\n", "No final newline"):
            with self.subTest(existing=existing):
                self.target.write_text(existing)
                first = self.assert_applied()
                self.assertTrue(first.startswith(existing))
                self.assertEqual(self.assert_applied(), first)

    def test_updates_only_managed_block_preserving_prefix_and_suffix(self):
        before = "# Existing instructions\n\n"
        after = "\n\n## Unrelated settings\nKeep $1, backticks `here`, and 日本語."
        self.target.write_text(f"{before}{BEGIN}\nStale rule\n{END}{after}")
        content = self.assert_applied()
        self.assertTrue(content.startswith(before + BEGIN))
        self.assertTrue(content.endswith(END + after))
        self.assertNotIn("Stale rule", content)
        self.assertEqual(self.assert_applied(), content)

    def test_malformed_markers_fail_without_overwriting_instructions(self):
        for existing in (
            f"Keep this\n{BEGIN}\nMissing end\n",
            f"Keep this\n{END}\nMissing begin\n",
            f"{BEGIN}\nOld\n{END}\n{BEGIN}\nOld\n{END}\n",
            f"{END}\nReversed\n{BEGIN}\n",
        ):
            with self.subTest(existing=existing):
                self.target.write_text(existing)
                result = self.apply()
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("instruction markers", result.stderr)
                self.assertEqual(self.target.read_text(), existing)


if __name__ == "__main__":
    unittest.main()
