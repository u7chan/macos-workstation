import os
from pathlib import Path
import subprocess
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "agents" / "sync-skills.sh"


class SyncSkillsTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.git_args = self.root / "git-args"
        self.pi_args = self.root / "pi-args"
        for name, body in {
            "git": 'printf "%s\\n" "$@" > "$GIT_ARGS"\n'
            'printf "%s" "$GIT_OUTPUT"\nexit "$GIT_STATUS"\n',
            "pi": 'printf "%s\\n" "$@" > "$PI_ARGS"\nexit "$PI_STATUS"\n',
        }.items():
            executable = self.root / name
            executable.write_text("#!/bin/bash\nset -eu\n" + body)
            executable.chmod(0o755)
        self.revision = "1" * 40
        self.env = {
            **os.environ,
            "PATH": f"{self.root}{os.pathsep}{os.environ['PATH']}",
            "GIT_ARGS": str(self.git_args),
            "PI_ARGS": str(self.pi_args),
            "GIT_OUTPUT": f"{self.revision}\trefs/heads/main\n",
            "GIT_STATUS": "0",
            "PI_STATUS": "0",
        }

    def run_script(self):
        return subprocess.run(
            ["/bin/bash", str(SCRIPT)],
            cwd=self.root,
            env=self.env,
            capture_output=True,
            text=True,
            check=False,
        )

    def test_installs_resolved_commit_globally(self):
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stderr)
        git_args = self.git_args.read_text().splitlines()
        self.assertEqual(git_args[:2], ["ls-remote", "--exit-code"])
        self.assertEqual(git_args[3:], ["refs/heads/main"])
        repository = git_args[2].removeprefix("https://").removesuffix(".git")
        self.assertEqual(
            self.pi_args.read_text().splitlines(),
            ["install", f"git:{repository}@{self.revision}"],
        )
        self.assertIn(self.revision, result.stdout)
        self.assertIn("/reload", result.stdout)

    def test_resolves_the_branch_again_on_each_run(self):
        self.assertEqual(self.run_script().returncode, 0)
        next_revision = "2" * 40
        self.env["GIT_OUTPUT"] = f"{next_revision}\trefs/heads/main\n"
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(
            self.pi_args.read_text().splitlines()[1].endswith(f"@{next_revision}")
        )
        self.assertIn(next_revision, result.stdout)

    def test_lookup_failure_does_not_install(self):
        self.env.update(GIT_STATUS="128", GIT_OUTPUT="")
        result = self.run_script()
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.pi_args.exists())

    def test_missing_branch_does_not_install(self):
        self.env.update(GIT_STATUS="2", GIT_OUTPUT="")
        result = self.run_script()
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.pi_args.exists())

    def test_invalid_revision_does_not_install(self):
        outputs = (
            "",
            "main\trefs/heads/main\n",
            "abc123\trefs/heads/main\n",
            f"{self.revision}\trefs/heads/main\n{self.revision}\trefs/heads/other\n",
        )
        for output in outputs:
            with self.subTest(output=output):
                self.env["GIT_OUTPUT"] = output
                result = self.run_script()
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("ERROR:", result.stderr)
                self.assertFalse(self.pi_args.exists())

    def test_install_failure_propagates(self):
        self.env["PI_STATUS"] = "7"
        result = self.run_script()
        self.assertEqual(result.returncode, 7)
        self.assertNotIn("/reload", result.stdout)


if __name__ == "__main__":
    unittest.main()
