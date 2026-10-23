"""GNU用PATHをハーネス配下に限定し、引数・入出力・終了コードを保って起動できることを確認する。

OS判定用コマンド・依存コマンド・ハーネスは模擬し、自作ランチャーの分岐や停止条件を検証する。
実際のGNUコマンドと上流ハーネスのmacOS互換性は、別途実機で確認する。
"""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "home/dot_local/bin/executable_agent-harness-exec"
)
ENTRYPOINTS = (
    "gh/scripts/gh.sh",
    "review/scripts/validate-review-payload.sh",
    "review/scripts/recheck-state.sh",
    "review/scripts/recheck-state.py",
)


class AgentHarnessExecTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="harness test ")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.bin = self.root / "bin"
        self.gnu = self.root / "gnubin"
        self.bin.mkdir()
        self.gnu.mkdir()
        self.script = self.root / "agent-harness-exec"
        # Substitute only the fixed installation path; no test-only production API.
        source = SCRIPT.read_text()
        self.assertEqual(source.count("/opt/local/libexec/gnubin"), 1)
        self.executable(
            self.script,
            source.replace("/opt/local/libexec/gnubin", str(self.gnu)),
        )
        self.env = {
            **os.environ,
            "PATH": f"{self.bin}{os.pathsep}{os.environ['PATH']}",
            "TEST_OS": "Darwin",
            "HARNESS_STATUS": "0",
            "HARNESS_STDERR": "",
            "UNAME_STATUS": "0",
            "GNU_VERSION": "test (GNU utilities)",
            "GNU_VERSION_STATUS": "0",
            "GREP_PCRE_STATUS": "0",
            "JQ_STATUS": "0",
        }
        self.executable(
            self.bin / "uname",
            '#!/bin/bash\nprintf "%s\\n" "$TEST_OS"\nexit "$UNAME_STATUS"\n',
        )
        self.executable(self.bin / "jq", '#!/bin/bash\nexit "$JQ_STATUS"\n')
        for name in ("grep", "stat", "mktemp", "sort", "head"):
            self.executable(
                self.gnu / name,
                '#!/bin/bash\n'
                'if [ "$1" = --version ]; then\n'
                '  printf "%s\\n" "$GNU_VERSION"\n'
                '  exit "$GNU_VERSION_STATUS"\n'
                'fi\n'
                'exit "$GREP_PCRE_STATUS"\n',
            )
        capture = (
            f"#!{sys.executable}\n"
            "import json, os, shutil, subprocess, sys\n"
            "print(json.dumps({\n"
            "  'args': sys.argv[1:], 'path': os.environ['PATH'],\n"
            "  'cwd': os.getcwd(), 'stdin': sys.stdin.read(),\n"
            "  'grep': shutil.which('grep'), 'stat': shutil.which('stat'),\n"
            "  'sed': shutil.which('sed'),\n"
            "  'child_path': subprocess.check_output([sys.executable, '-c',\n"
            "    'import os; print(os.environ[\"PATH\"])'], text=True).strip(),\n"
            "}))\n"
            "sys.stderr.write(os.environ['HARNESS_STDERR'])\n"
            "sys.exit(int(os.environ['HARNESS_STATUS']))\n"
        )
        self.targets = []
        for name in ENTRYPOINTS:
            target = self.root / "installed skills" / name
            self.executable(target, capture)
            self.targets.append(target)
        self.ordinary_test = self.root / "ordinary-test.py"
        self.executable(self.ordinary_test, capture)

    @staticmethod
    def executable(path, content):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        path.chmod(0o755)

    def run_launcher(self, *args):
        return subprocess.run(
            [str(self.script), *map(str, args)],
            cwd=self.root,
            env=self.env,
            input="input for harness\n",
            capture_output=True,
            text=True,
            check=False,
        )

    def test_mac_dispatch_preserves_arguments_streams_and_working_directory(self):
        args = ["with spaces", "", "--flag", "quote'\"", "line\nbreak"]
        for target in self.targets:
            with self.subTest(target=target):
                result = self.run_launcher(target, *args)
                self.assertEqual(result.returncode, 0, result.stderr)
                data = json.loads(result.stdout)
                self.assertEqual(data["args"], args)
                self.assertEqual(data["stdin"], "input for harness\n")
                self.assertEqual(data["cwd"], str(self.root.resolve()))
                self.assertEqual(data["path"], f"{self.gnu}:{self.env['PATH']}")
                self.assertEqual(data["child_path"], data["path"])
                self.assertEqual(data["grep"], str(self.gnu / "grep"))
                self.assertEqual(data["stat"], str(self.gnu / "stat"))
                self.assertNotEqual(data["sed"], str(self.gnu / "sed"))
                self.assertEqual(result.stderr, "")

    def test_non_mac_does_not_check_macports_or_modify_path(self):
        for name in self.gnu.iterdir():
            name.unlink()
        self.gnu.rmdir()
        self.env.update(TEST_OS="Linux", JQ_STATUS="1", GNU_VERSION_STATUS="1")
        result = self.run_launcher(self.targets[0], "unchanged")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["path"], self.env["PATH"])

    def test_os_detection_failure_stops_before_harness(self):
        for setting in ({"UNAME_STATUS": "1"}, {"TEST_OS": ""}):
            with self.subTest(setting=setting):
                original = self.env.copy()
                self.env.update(setting)
                result = self.run_launcher(self.targets[0])
                self.env = original
                self.assertEqual(result.returncode, 1)
                self.assertIn("ERROR:", result.stderr)
                self.assertEqual(result.stdout, "")

    def test_harness_failure_and_stderr_propagate(self):
        self.env.update(HARNESS_STATUS="7", HARNESS_STDERR="harness error\n")
        result = self.run_launcher(self.targets[0])
        self.assertEqual(result.returncode, 7)
        self.assertTrue(result.stdout)
        self.assertEqual(result.stderr, "harness error\n")

    def test_missing_gnu_dependency_stops_before_harness(self):
        for name in ("grep", "stat", "mktemp", "sort", "head"):
            with self.subTest(name=name):
                tool = self.gnu / name
                tool.chmod(0o644)
                result = self.run_launcher(self.targets[0])
                tool.chmod(0o755)
                self.assertEqual(result.returncode, 1)
                self.assertIn(f"missing GNU {name}", result.stderr)
                self.assertEqual(result.stdout, "")

    def test_broken_or_non_gnu_tool_stops_before_harness(self):
        for setting in (
            {"GNU_VERSION": "BSD utilities"},
            {"GNU_VERSION_STATUS": "1"},
            {"GREP_PCRE_STATUS": "2"},
            {"JQ_STATUS": "1"},
        ):
            with self.subTest(setting=setting):
                original = self.env.copy()
                self.env.update(setting)
                result = self.run_launcher(self.targets[0])
                self.env = original
                self.assertEqual(result.returncode, 1)
                self.assertIn("ERROR:", result.stderr)
                self.assertEqual(result.stdout, "")

    def test_missing_jq_on_path_stops_before_harness(self):
        self.env["PATH"] = str(self.bin)
        (self.bin / "jq").unlink()
        result = self.run_launcher(self.targets[0])
        self.assertEqual(result.returncode, 1)
        self.assertIn("jq must be usable on PATH", result.stderr)
        self.assertEqual(result.stdout, "")

    def test_rejects_missing_relative_and_general_commands(self):
        for args in (
            (),
            ("pi",),
            ("/bin/bash", "-c", "true"),
            ("gh/scripts/gh.sh",),
            (self.ordinary_test,),
        ):
            with self.subTest(args=args):
                result = self.run_launcher(*args)
                self.assertEqual(result.returncode, 2)
                self.assertIn("Usage:", result.stderr)
                self.assertEqual(result.stdout, "")

    def test_missing_or_nonexecutable_entrypoint_stops(self):
        self.targets[0].unlink()
        self.targets[1].chmod(0o644)
        for target in self.targets[:2]:
            with self.subTest(target=target):
                result = self.run_launcher(target)
                self.assertEqual(result.returncode, 1)
                self.assertIn("not an executable file", result.stderr)

    def test_caller_and_separately_launched_test_keep_original_path(self):
        result = subprocess.run(
            [
                "/bin/bash", "-c",
                'before=$PATH; "$1" "$2" </dev/null >/dev/null || exit; '
                '[ "$PATH" = "$before" ] || exit 99; exec "$3"',
                "bash", str(self.script), str(self.targets[0]), str(self.ordinary_test),
            ],
            cwd=self.root, env=self.env, input="", capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["path"], self.env["PATH"])

    def test_sourcing_is_rejected_without_changing_shell(self):
        result = subprocess.run(
            [
                "/bin/bash", "-c",
                'before=$PATH; options=$-; source "$1"; status=$?; '
                '[ "$PATH" = "$before" ] && [ "$-" = "$options" ] || exit 99; '
                'exit "$status"',
                "bash", str(self.script),
            ],
            env=self.env, capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("do not source", result.stderr)


if __name__ == "__main__":
    unittest.main()
