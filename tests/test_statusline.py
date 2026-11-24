"""Claude Codeのstatusline表示を、実際のjq・gitと一時リポジトリで確認する。

表示色やNerd Fontのアイコンが端末で正しく見えるかは対象外とし、実機で確認する。
"""

import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
CLAUDE_SOURCE = ROOT / "home" / "private_dot_claude"
SCRIPT = CLAUDE_SOURCE / "statusline" / "statusline.sh"
CHEZMOI = shutil.which("chezmoi")
GIT = shutil.which("git")
JQ = shutil.which("jq")

CSI = re.compile(r"\x1b\[[0-9;]*m")
OSC8 = re.compile(r"\x1b\]8;;([^\x1b]*)\x1b\\")


def plain(text):
    """色とハイパーリンクの制御列を取り除いた表示文字列を返す。"""
    return OSC8.sub("", CSI.sub("", text))


@unittest.skipUnless(GIT and JQ, "git and jq are required")
class StatusLineTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        # 実際のユーザー設定や親ディレクトリのリポジトリを参照しない。
        self.env = {
            **os.environ, "HOME": str(self.root),
            "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CEILING_DIRECTORIES": str(self.root),
        }
        subprocess.run([GIT, "init", "--quiet"], cwd=self.repo, env=self.env, check=True)

    def checkout(self, branch):
        subprocess.run([GIT, "symbolic-ref", "HEAD", f"refs/heads/{branch}"],
                       cwd=self.repo, env=self.env, check=True)

    def render(self, payload, text=None):
        return subprocess.run(
            ["bash", str(SCRIPT)], env=self.env, capture_output=True, text=True,
            input=text if text is not None else json.dumps(payload),
        )

    def payload(self, **extra):
        return {"workspace": {"current_dir": str(self.repo), "repo": {
            "host": "github.com", "owner": "owner", "name": "name"}}, **extra}

    def test_all_parts(self):
        """ブランチ由来のIssue・PR・モデル・使用量・キャッシュ・レート制限をすべて表示する。"""
        self.checkout("fix/123-foo")
        now = time.time()
        result = self.render(self.payload(
            pr={"number": 7, "url": "https://github.com/owner/name/pull/7"},
            model={"display_name": "Sonnet 5.5 (1M context)"}, effort={"level": "xhigh"},
            context_window={"used_percentage": 42.4},
            prompt_cache={"warm": True, "ttl": "5m", "expires_at": now + 200},
            rate_limits={"five_hour": {"used_percentage": 12, "resets_at": now + 5400},
                         "seven_day": {"used_percentage": 63, "resets_at": now + 86400}},
        ))
        self.assertEqual(result.returncode, 0, result.stderr)
        text = plain(result.stdout)
        for part in ("#123", "PR#7", "Sonnet 5.5 (1M)", "xhigh", "42%", "5h", "12%", "7d", "63%"):
            self.assertIn(part, text)
        self.assertRegex(text, r"\d+m\d\ds")
        self.assertEqual(OSC8.findall(result.stdout), [
            "https://github.com/owner/name/issues/123", "",
            "https://github.com/owner/name/pull/7", "",
        ])

    def test_issue_number_from_branch(self):
        """明示的な形のブランチ名だけをIssue番号として扱い、誤検出しない。"""
        cases = {
            "fix/123-foo": "#123", "issue-820": "#820", "issues/45": "#45",
            "main": None, "feature/02-parts": None, "reissue-401": None,
        }
        for branch, expected in cases.items():
            with self.subTest(branch=branch):
                self.checkout(branch)
                result = self.render(self.payload(model={"display_name": "M"}))
                self.assertEqual(result.returncode, 0, result.stderr)
                if expected:
                    self.assertIn(expected, plain(result.stdout))
                else:
                    self.assertNotIn("#", plain(result.stdout))

    def test_prompt_cache_states(self):
        """キャッシュが切れた場合と圧縮直後の場合を、残り時間とは別の表示にする。"""
        cold = self.render(self.payload(
            prompt_cache={"warm": False, "expires_at": time.time() - 10,
                          "recache_tokens_if_cold": 89000}))
        self.assertIn("89k", plain(cold.stdout))
        compacted = self.render(self.payload(
            prompt_cache={"warm": True, "expires_at": time.time() + 100,
                          "recache_tokens_if_cold": None}))
        self.assertIn("compacted", plain(compacted.stdout))

    def test_minimal_input(self):
        """項目が何もない入力でも、モデル名の既定値だけを表示して成功する。"""
        result = self.render({})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(plain(result.stdout), "Claude")

    def test_outside_git_repository(self):
        """gitリポジトリ外でもエラーにせず、Issue表示を省く。"""
        outside = self.root / "outside"
        outside.mkdir()
        result = self.render({"workspace": {"current_dir": str(outside)},
                              "model": {"display_name": "M"}})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(plain(result.stdout), "M")

    def test_invalid_input_prints_nothing(self):
        """不正なJSONでは壊れた表示を出さず、失敗として終了する。"""
        result = self.render(None, text="not json")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")


@unittest.skipUnless(CHEZMOI and GIT and JQ, "chezmoi, git and jq are required")
class StatusLineDeploymentTests(unittest.TestCase):
    def test_configured_command_runs_after_apply(self):
        """chezmoi適用後のHOMEで、設定されたstatusLineコマンドがそのまま実行できる。"""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            home, source = root / "home", root / "source"
            home.mkdir()
            shutil.copytree(CLAUDE_SOURCE, source / "private_dot_claude")
            (root / "chezmoi.toml").write_text("")
            env = {**os.environ, "HOME": str(home)}
            applied = subprocess.run(
                [CHEZMOI, "--source", str(source), "--destination", str(home),
                 "--config", str(root / "chezmoi.toml"), "--cache", str(root / "cache"),
                 "--persistent-state", str(root / "state"), "apply", "--force", "--no-tty"],
                env=env, capture_output=True, text=True,
            )
            self.assertEqual(applied.returncode, 0, applied.stderr)
            settings = json.loads((home / ".claude/settings.json").read_text())
            result = subprocess.run(
                settings["statusLine"]["command"], shell=True, cwd=home, env=env,
                capture_output=True, text=True, input=json.dumps({"model": {"display_name": "M"}}),
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(plain(result.stdout), "M")


if __name__ == "__main__":
    unittest.main()
