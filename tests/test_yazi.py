"""一時HOMEと実際のzshで、Yazi終了時のディレクトリ移動と失敗時の保護を確認する。

外部ツールの起動だけを模擬し、実ユーザーの設定・ツール・ディレクトリは変更しない。
端末上の描画と実際のプレビュー依存の検出は、別途実機で確認する。
"""

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
ZSH = shutil.which("zsh")


@unittest.skipUnless(ZSH, "zsh is required for Yazi shell tests")
class YaziShellTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="yazi shell ")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.home = self.root / "home"
        self.bin = self.home / ".local/bin"
        self.temp = self.root / "tmp"
        self.start = self.root / "start"
        self.target = self.root / "selected directory"
        for path in (self.bin, self.temp, self.start, self.target):
            path.mkdir(parents=True)
        self.log = self.root / "launch.json"
        self.cwd_result = self.root / "cwd"
        (self.home / ".zshrc").write_bytes((ROOT / "home/dot_zshrc").read_bytes())
        for name in ("mise", "starship", "zoxide"):
            self.write_command(name, "#!/bin/sh\nexit 0\n")
        for name in ("mktemp", "rm"):
            (self.bin / name).symlink_to(shutil.which(name))
        self.write_command("yazi", f'''#!{sys.executable}
import json, os, pathlib, stat, sys
args = sys.argv[1:]
cwd_file = pathlib.Path(args[-1].removeprefix("--cwd-file="))
pathlib.Path(os.environ["TEST_LOG"]).write_text(json.dumps({{
    "args": args[:-1], "cwd_file": str(cwd_file),
    "mode": stat.S_IMODE(cwd_file.stat().st_mode), "cwd": os.getcwd(),
}}))
cwd_file.write_text(os.environ["TEST_TARGET"])
sys.exit(int(os.environ.get("TEST_YAZI_EXIT", "0")))
''')
        self.env = {
            key: value for key, value in os.environ.items()
            if not key.startswith(("XDG_", "MISE_", "ZDOTDIR"))
        }
        self.env.update(
            HOME=str(self.home), PATH=str(self.bin), TMPDIR=str(self.temp),
            TEST_LOG=str(self.log), TEST_TARGET=str(self.target),
            TEST_CWD_RESULT=str(self.cwd_result),
        )

    def write_command(self, name, content):
        path = self.bin / name
        path.write_text(content)
        path.chmod(0o755)

    def run_y(self, *args, strict=False):
        invocation = 'y "$@"' if strict else 'if y "$@"; then result=0; else result=$?; fi'
        script = '\n'.join([
            'source "$HOME/.zshrc"',
            'setopt err_exit nounset' if strict else 'result=0',
            invocation,
            'print -rn -- "$PWD" > "$TEST_CWD_RESULT"',
            'exit 0' if strict else 'exit "$result"',
        ])
        return subprocess.run(
            [ZSH, "-df", "-c", script, "yazi-test", *args],
            cwd=self.start, env=self.env, capture_output=True, text=True,
        )

    def assert_cwd(self, expected):
        self.assertEqual(self.cwd_result.read_text(), str(expected))
        self.assertEqual(list(self.temp.iterdir()), [])

    def test_follows_directory_and_forwards_arguments_without_word_splitting(self):
        args = ("--hidden", "path with spaces", "*.txt", "-leading-dash")
        result = self.run_y(*args)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assert_cwd(self.target)
        launch = json.loads(self.log.read_text())
        self.assertEqual(launch["args"], list(args))
        self.assertEqual(launch["cwd"], str(self.start))
        self.assertEqual(launch["mode"], 0o600)
        self.assertEqual(Path(launch["cwd_file"]).parent, self.temp)

    def test_preserves_backslashes_and_newlines_in_directory_names(self):
        target = self.root / "back\\slash\nand trailing newline\n"
        target.mkdir()
        self.env["TEST_TARGET"] = str(target)
        result = self.run_y()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assert_cwd(target)

    def test_empty_exit_file_leaves_directory_unchanged(self):
        self.env["TEST_TARGET"] = ""
        result = self.run_y()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assert_cwd(self.start)

    def test_invalid_or_unchanged_destination_does_not_change_directory(self):
        regular_file = self.root / "not a directory"
        regular_file.write_text("fixture\n")
        for target in (self.start, self.root / "missing", regular_file):
            with self.subTest(target=target):
                self.env["TEST_TARGET"] = str(target)
                result = self.run_y()
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assert_cwd(self.start)

    def test_failed_launch_ignores_written_directory_and_preserves_exit_status(self):
        self.env["TEST_YAZI_EXIT"] = "7"
        result = self.run_y()
        self.assertEqual(result.returncode, 7, result.stderr)
        self.assert_cwd(self.start)

    def test_missing_yazi_cleans_up_without_changing_directory(self):
        (self.bin / "yazi").unlink()
        result = self.run_y()
        self.assertEqual(result.returncode, 127, result.stderr)
        self.assert_cwd(self.start)
        self.assertFalse(self.log.exists())

    def test_mktemp_failure_stops_before_launch(self):
        (self.bin / "mktemp").unlink()
        self.write_command("mktemp", "#!/bin/sh\nexit 9\n")
        result = self.run_y()
        self.assertEqual(result.returncode, 9, result.stderr)
        self.assert_cwd(self.start)
        self.assertFalse(self.log.exists())

    def test_unterminated_cwd_file_works_with_errexit_and_nounset(self):
        result = self.run_y(strict=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assert_cwd(self.target)

    def test_repeated_runs_use_distinct_temporary_files_and_leave_no_files(self):
        files = []
        for _ in range(2):
            result = self.run_y()
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assert_cwd(self.target)
            files.append(json.loads(self.log.read_text())["cwd_file"])
        self.assertNotEqual(files[0], files[1])


if __name__ == "__main__":
    unittest.main()
