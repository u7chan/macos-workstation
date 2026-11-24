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
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
CLAUDE_SOURCE = ROOT / "home" / "private_dot_claude"
SCRIPT = CLAUDE_SOURCE / "statusline" / "statusline.sh"
CHEZMOI = shutil.which("chezmoi")
GIT = shutil.which("git")
JQ = shutil.which("jq")

CSI = re.compile(r"\x1b\[[0-9;]*m")
OSC8 = re.compile(r"\x1b\]8;;([^\x1b]*)\x1b\\")


def isolated_env(home):
    """GIT_*を引き継がず、ユーザー設定や親リポジトリを参照しない環境を返す。"""
    inherited = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    return {
        **inherited, "HOME": str(home), "TZ": "UTC",
        "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CEILING_DIRECTORIES": str(home),
    }


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
        self.env = isolated_env(self.root)
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
            "feature/123_foo": "#123", "fix/863-2fa": "#863",
            "release/2025-01-update": None, "release/1-2-0": None,
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

    def test_bar_cells(self):
        """使用率がセル境界でも空白を出さず、常に5セル幅で描く。"""
        cases = {0: "░░░░░", 20: "█░░░░", 40: "██░░░", 50: "██▌░░", 80: "████░", 100: "█████"}
        for pct, bar in cases.items():
            with self.subTest(pct=pct):
                text = plain(self.render(self.payload(context_window={"used_percentage": pct})).stdout)
                self.assertTrue(text.endswith(f" {bar} {pct}%"), text)

    def test_token_units(self):
        """トークン数は丸めてから単位を選び、1000kのような繰り上がり漏れを出さない。"""
        cases = {999: "999", 1000: "1k", 999499: "999k", 999600: "1M", 1230000: "1.2M"}
        for tokens, expected in cases.items():
            with self.subTest(tokens=tokens):
                text = plain(self.render(self.payload(prompt_cache={
                    "warm": False, "expires_at": time.time() - 10,
                    "recache_tokens_if_cold": tokens})).stdout)
                self.assertTrue(text.endswith(f" {expected}"), text)

    def test_rate_limit_suffix(self):
        """5時間枠は残り時間、7日枠はリセット曜日を表示する。"""
        now = time.time()
        text = plain(self.render(self.payload(rate_limits={
            "five_hour": {"used_percentage": 10, "resets_at": now + 5430},
            "seven_day": {"used_percentage": 20, "resets_at": now + 86400},
        })).stdout)
        self.assertIn("(1h30m)", text)
        self.assertIn(f"({time.strftime('%a', time.gmtime(now + 86400))})", text)

    def test_warning_color_follows_ttl(self):
        """キャッシュ残り時間の警告色は、TTLに応じた閾値で切り替わる。"""
        warning = "\x1b[1;38;2;255;90;60m"
        for ttl, expected in (("5m", False), ("1h", True)):
            with self.subTest(ttl=ttl):
                result = self.render(self.payload(prompt_cache={
                    "warm": True, "ttl": ttl, "expires_at": time.time() + 500}))
                self.assertEqual(warning in result.stdout, expected)

    def test_links_depend_on_available_data(self):
        """リポジトリ情報やPRのURLがなければ番号だけを表示し、GitLabはIssue経路を切り替える。"""
        self.checkout("fix/123-foo")
        result = self.render({"workspace": {"current_dir": str(self.repo)}, "pr": {"number": 7}})
        self.assertEqual(plain(result.stdout).split(" │ ")[:2], ["#123", "PR#7"])
        self.assertEqual(OSC8.findall(result.stdout), [])
        result = self.render({"workspace": {"current_dir": str(self.repo), "repo": {
            "host": "gitlab.com", "owner": "owner", "name": "name"}}})
        self.assertEqual(OSC8.findall(result.stdout)[0], "https://gitlab.com/owner/name/-/issues/123")

    def test_detached_head(self):
        """ブランチ名がないdetached HEADでは、Issue表示を省く。"""
        self.checkout("fix/123-foo")
        identity = {f"GIT_{role}_{field}": value for role in ("AUTHOR", "COMMITTER")
                    for field, value in (("NAME", "test"), ("EMAIL", "test@example.invalid"))}
        for command in (["commit", "--allow-empty", "--quiet", "-m", "init"],
                        ["checkout", "--detach", "--quiet"]):
            subprocess.run([GIT, *command], cwd=self.repo, env={**self.env, **identity}, check=True)
        result = self.render(self.payload(model={"display_name": "M"}))
        self.assertEqual(plain(result.stdout), "M")

    def test_control_characters_are_removed_from_links(self):
        """リンクに入るURLの制御文字を除去し、端末へ任意のエスケープを渡さない。"""
        self.checkout("fix/123-foo")
        result = self.render({
            "workspace": {"current_dir": str(self.repo), "repo": {
                "host": "github.com", "owner": "owner\x1b[2J", "name": "name"}},
            "pr": {"number": 7, "url": "https://example.com/pull/7\x1b[2J\x07"},
        })
        self.assertNotIn("\x1b[2J", result.stdout)
        self.assertNotIn("\x07", result.stdout)
        self.assertEqual(len(OSC8.findall(result.stdout)), 4)

    def test_environment_ignores_inherited_git_variables(self):
        """親プロセスのGIT_DIRがあっても、隔離した一時リポジトリだけを操作する。"""
        outer = self.root / "outer"
        outer.mkdir()
        subprocess.run([GIT, "init", "--quiet"], cwd=outer, env=self.env, check=True)
        before = (outer / ".git/HEAD").read_text()
        with mock.patch.dict(os.environ, {"GIT_DIR": str(outer / ".git")}):
            env = isolated_env(self.root)
        subprocess.run([GIT, "symbolic-ref", "HEAD", "refs/heads/fix/123-foo"],
                       cwd=self.repo, env=env, check=True)
        self.assertEqual((outer / ".git/HEAD").read_text(), before)

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
            env = isolated_env(home)
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
