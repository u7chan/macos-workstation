"""一時HOMEで日次更新の範囲、停止条件、既存設定の保持、bootstrapからの委譲を確認する。

miseとPiの外部インストールは模擬し、Gitの参照解決とchezmoiによる配置には実物を使う。
実ユーザーのツール・設定は変更せず、macOSでの実更新とExtensionのロードは別途確認する。
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
SCRIPT = ROOT / "home/dot_local/bin/executable_myupdate"
GIT = shutil.which("git")
JQ = shutil.which("jq")
CHEZMOI = shutil.which("chezmoi")
MYPI = "git:github.com/u7chan/mypi@main"
PACKAGES = ("npm:pi-web-access", "npm:@ogulcancelik/pi-session-recall", MYPI)
SKILLS = "git:github.com/u7chan/agent-harness"
PI_TOOL = "npm:@earendil-works/pi-coding-agent"


@unittest.skipUnless(GIT and JQ, "git and jq are required for update tests")
class MyupdateFixture(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="daily update ")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.home = self.root / "home"
        self.bin = self.root / "bin"
        self.project = self.root / "unrelated project"
        for path in (self.home, self.bin, self.project):
            path.mkdir()
        self.log = self.root / "calls.jsonl"
        self.settings = self.home / ".pi/agent/settings.json"
        self.lock = self.home / ".local/state/macos-workstation/myupdate.lock"
        self.config = self.home / ".config/mise/config.toml"
        self.config.parent.mkdir(parents=True)
        self.config.write_bytes((ROOT / "home/dot_config/mise/config.toml").read_bytes())
        self.project_settings = self.project / ".pi/settings.json"
        self.project_settings.parent.mkdir()
        self.project_settings.write_text('{"packages":["npm:project-only"]}\n')
        (self.project / "mise.toml").write_text('[tools]\nnode = "18"\n')
        self.env = {
            key: value for key, value in os.environ.items()
            if not key.startswith(("PI_", "MISE_", "GIT_", "XDG_", "BASH_FUNC_"))
        }
        self.env.update(
            HOME=str(self.home), PATH=str(self.bin), TEST_CALLS=str(self.log),
            REAL_GIT=GIT, GIT_CONFIG_NOSYSTEM="1",
            GIT_CONFIG_GLOBAL=str(self.root / "gitconfig"),
        )
        Path(self.env["GIT_CONFIG_GLOBAL"]).write_text("")
        for name in ("mkdir", "rmdir", "cut", "bash"):
            (self.bin / name).symlink_to(shutil.which(name))
        (self.bin / "jq").symlink_to(JQ)
        self.remote = self.root / "skill remote"
        self.git("init", "-b", "main", str(self.remote))
        self.commit_skills()
        self.git(
            "config", "--file", self.env["GIT_CONFIG_GLOBAL"],
            f"url.{self.remote.as_uri()}.insteadOf",
            "https://github.com/u7chan/agent-harness.git",
        )
        self.revision = self.git("-C", str(self.remote), "rev-parse", "HEAD")
        self.write_command("git", '''
record("git", sys.argv[1:])
if "TEST_GIT_OUTPUT" in os.environ:
    print(os.environ["TEST_GIT_OUTPUT"], end="")
    sys.exit(int(os.environ.get("TEST_GIT_STATUS", "0")))
os.execv(os.environ["REAL_GIT"], [os.environ["REAL_GIT"], *sys.argv[1:]])
''')
        self.write_command("mise", '''
args = sys.argv[1:]
record("mise", args)
if args == ["upgrade", "--no-prune", "npm:@earendil-works/pi-coding-agent"]:
    sys.exit(int(os.environ.get("TEST_UPGRADE_STATUS", "0")))
if args == ["install"]:
    sys.exit(0)
if args[:2] == ["exec", "--"]:
    if args[2] == "pi":
        target = os.path.join(os.environ["HOME"], "fresh pi")
        os.execv(target, [target, *args[3:]])
    sys.exit(0)
sys.exit(99)
''')
        self.write_command("pi", '''
record("stale-pi", sys.argv[1:])
sys.exit(99)
''')
        self.write_python(self.home / "fresh pi", '''
from pathlib import Path
args = sys.argv[1:]
record("pi", args)
if args[0] == "--version":
    print("1.4.0")
    sys.exit(0)
if args == ["list", "--no-approve"]:
    print("User packages:")
    sys.exit(0)
if args[0] != "install" or args[2:] != ["--no-approve"]:
    sys.exit(99)
source = args[1]
if source == os.environ.get("TEST_FAILED_PACKAGE"):
    sys.exit(7)
settings = Path(os.environ.get("PI_CODING_AGENT_DIR", str(Path.home() / ".pi/agent"))) / "settings.json"
data = json.loads(settings.read_text()) if settings.exists() else {}
packages = data.setdefault("packages", [])
def identity(value):
    return value.rsplit("@", 1)[0] if value.startswith("git:") else value
for index, package in enumerate(packages):
    existing = package if isinstance(package, str) else package["source"]
    if identity(existing) == identity(source):
        packages[index] = source if isinstance(package, str) else {**package, "source": source}
        break
else:
    packages.append(source)
settings.parent.mkdir(parents=True, exist_ok=True)
settings.write_text(json.dumps(data) + "\\n")
''')

    def write_python(self, path, body):
        path.write_text(
            f"#!{sys.executable}\n"
            "import json, os, sys\n"
            "def record(command, args):\n"
            "    with open(os.environ['TEST_CALLS'], 'a') as log:\n"
            "        log.write(json.dumps({'command': command, 'args': args,\n"
            "            'cwd': os.getcwd(), 'config': os.environ.get('MISE_CONFIG_FILE')}) + '\\n')\n"
            + body
        )
        path.chmod(0o755)

    def write_command(self, name, body):
        self.write_python(self.bin / name, body)

    def git(self, *args):
        result = subprocess.run(
            [GIT, *args], env=self.env, capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout.strip()

    def commit_skills(self):
        self.git(
            "-C", str(self.remote), "-c", "user.name=Fixture",
            "-c", "user.email=fixture@example.invalid", "commit", "--allow-empty", "-m", "fixture",
        )

    def run_update(self, *args):
        return subprocess.run(
            ["/bin/bash", str(SCRIPT), *args], cwd=self.project, env=self.env,
            capture_output=True, text=True, check=False,
        )

    def calls(self, command=None):
        calls = [json.loads(line) for line in self.log.read_text().splitlines()] if self.log.exists() else []
        return [call for call in calls if command is None or call["command"] == command]

    def installs(self):
        return [call["args"][1] for call in self.calls("pi") if call["args"][0] == "install"]

    def assert_success(self, result):
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("all updates completed successfully", result.stdout)
        self.assertIn("Start Pi to begin work.", result.stdout)
        self.assertIn("Exit all Pi sessions before the next update.", result.stdout)
        self.assertNotIn("/reload", result.stdout)
        self.assertFalse(self.lock.exists())
        self.assertEqual(self.calls("stale-pi"), [])
        self.assertEqual(self.project_settings.read_text(), '{"packages":["npm:project-only"]}\n')

class MyupdateTests(MyupdateFixture):
    def test_installs_only_managed_packages_after_upgrading_pi(self):
        result = self.run_update()
        self.assert_success(result)
        self.assertEqual(self.installs(), [*PACKAGES, f"{SKILLS}@{self.revision}"])
        self.assertEqual(self.calls()[0]["args"], ["upgrade", "--no-prune", PI_TOOL])
        for call in self.calls():
            self.assertEqual(Path(call["cwd"]), self.home.resolve())
            self.assertEqual(call["config"], str(self.config))
        self.assertIn(self.revision, result.stdout)

    def test_repeated_runs_preserve_unmanaged_settings_and_resource_filters(self):
        existing = {
            "theme": "custom", "unmanaged": {"keep": True},
            "packages": ["npm:unrelated", {"source": PACKAGES[0], "extensions": ["selected.ts"]},
                         {"source": f"{SKILLS}@{'1' * 40}", "skills": ["gh"]},
                         {"source": f"{MYPI.rsplit('@', 1)[0]}@{'2' * 40}",
                          "extensions": ["extensions/index.ts"], "skills": []}],
        }
        self.settings.parent.mkdir(parents=True)
        self.settings.write_text(json.dumps(existing))
        self.assert_success(self.run_update())
        first = json.loads(self.settings.read_text())
        self.assert_success(self.run_update())
        self.assertEqual(json.loads(self.settings.read_text()), first)
        self.assertEqual(first["unmanaged"], existing["unmanaged"])
        self.assertEqual(first["theme"], "custom")
        self.assertEqual(first["packages"][0:2], existing["packages"][0:2])
        self.assertEqual(first["packages"][2], {"source": f"{SKILLS}@{self.revision}", "skills": ["gh"]})
        self.assertEqual(first["packages"][3], {
            "source": MYPI, "extensions": ["extensions/index.ts"], "skills": [],
        })
        self.assertEqual(first["packages"][4:], [PACKAGES[1]])
        self.assertEqual(self.installs(), [*PACKAGES, f"{SKILLS}@{self.revision}"] * 2)

    def test_resolves_latest_skill_commit_on_every_run(self):
        self.assert_success(self.run_update())
        self.commit_skills()
        next_revision = self.git("-C", str(self.remote), "rev-parse", "HEAD")
        self.assertNotEqual(self.revision, next_revision)
        result = self.run_update()
        self.assert_success(result)
        self.assertEqual(self.installs()[-1], f"{SKILLS}@{next_revision}")
        self.assertIn(next_revision, result.stdout)

    def test_upgrade_failure_stops_before_package_operations_and_releases_lock(self):
        self.env["TEST_UPGRADE_STATUS"] = "9"
        result = self.run_update()
        self.assertEqual(result.returncode, 9)
        self.assertEqual(self.calls("pi"), [])
        self.assertEqual(self.calls("git"), [])
        self.assertFalse(self.lock.exists())
        self.assertNotIn("all updates completed", result.stdout)

    def test_package_failure_stops_remaining_updates_without_retry(self):
        for source in (*PACKAGES, f"{SKILLS}@{self.revision}"):
            with self.subTest(source=source):
                self.log.unlink(missing_ok=True)
                self.env["TEST_FAILED_PACKAGE"] = source
                result = self.run_update()
                self.assertEqual(result.returncode, 7)
                self.assertEqual(self.installs()[-1], source)
                self.assertEqual(self.installs().count(source), 1)
                self.assertFalse(self.lock.exists())
                self.assertNotIn("all updates completed", result.stdout)

    def test_missing_skill_branch_stops_without_installing_skills(self):
        self.git("-C", str(self.remote), "branch", "-m", "other")
        result = self.run_update()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.installs(), list(PACKAGES))
        self.assertFalse(self.lock.exists())
        self.assertNotIn("all updates completed", result.stdout)

    def test_invalid_or_failed_remote_response_does_not_install_skills(self):
        for output, status in (("", "128"), ("invalid\trefs/heads/main\n", "0"),
                               (f"{self.revision}\trefs/heads/main\n" * 2, "0")):
            with self.subTest(output=output, status=status):
                self.log.unlink(missing_ok=True)
                self.env.update(TEST_GIT_OUTPUT=output, TEST_GIT_STATUS=status)
                result = self.run_update()
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(self.installs(), list(PACKAGES))
                self.assertFalse(self.lock.exists())

    def test_invalid_settings_stop_before_updates_and_preserve_original(self):
        self.settings.parent.mkdir(parents=True)
        for content in ("", "{", "{}\n{}", "null", "[]", '{"packages":null}', '{"packages":{}}',
                        '{"packages":[{}]}', '{"packages":[42]}'):
            with self.subTest(content=content):
                self.settings.write_text(content)
                result = self.run_update()
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("invalid Pi settings", result.stderr)
                self.assertEqual(self.settings.read_text(), content)
                self.assertEqual(self.calls(), [])
                self.assertFalse(self.lock.exists())

    def test_nonregular_settings_path_is_not_replaced(self):
        self.settings.mkdir(parents=True)
        result = self.run_update()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("not a regular file", result.stderr)
        self.assertTrue(self.settings.is_dir())
        self.assertEqual(self.calls(), [])

    def test_custom_agent_directory_and_state_directory_are_respected(self):
        agent = self.root / "private agent"
        state = self.root / "state"
        self.env.update(PI_CODING_AGENT_DIR=str(agent), XDG_STATE_HOME=str(state))
        self.assert_success(self.run_update())
        self.assertTrue((agent / "settings.json").is_file())
        self.assertFalse(self.settings.exists())
        self.assertFalse((state / "macos-workstation/myupdate.lock").exists())
        self.assertEqual((state / "macos-workstation").stat().st_mode & 0o077, 0)

    def test_caller_mise_config_does_not_override_global_configuration(self):
        self.env["MISE_CONFIG_FILE"] = str(self.project / "mise.toml")
        self.assert_success(self.run_update())
        self.assertTrue(all(call["config"] == str(self.config) for call in self.calls()))

    def test_existing_lock_is_not_removed_and_no_updates_run(self):
        self.lock.mkdir(parents=True)
        result = self.run_update()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("update lock exists", result.stderr)
        self.assertTrue(self.lock.is_dir())
        self.assertEqual(self.calls(), [])

    def test_missing_configuration_and_dependencies_stop_before_updates(self):
        self.config.unlink()
        result = self.run_update()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("run bootstrap first", result.stderr)
        self.config.write_text("[tools]\n")
        for name in ("mise", "git", "jq"):
            with self.subTest(name=name):
                target = self.bin / name
                backup = target.with_name(name + ".saved")
                target.rename(backup)
                result = self.run_update()
                backup.rename(target)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(f"{name} is required", result.stderr)
        self.assertEqual(self.calls(), [])

    def test_help_and_invalid_arguments_do_not_update(self):
        result = self.run_update("--help")
        self.assertEqual(result.returncode, 0)
        self.assertIn("Usage: myupdate", result.stdout)
        result = self.run_update("unexpected")
        self.assertEqual(result.returncode, 2)
        self.assertIn("Usage: myupdate", result.stderr)
        self.assertEqual(self.calls(), [])
        self.assertFalse(self.lock.exists())


@unittest.skipUnless(CHEZMOI and GIT and JQ, "chezmoi, git and jq are required for bootstrap tests")
class MyupdateBootstrapTests(MyupdateFixture):
    def prepare_bootstrap(self):
        checkout = self.root / "bootstrap checkout"
        checkout.mkdir()
        bin_source = checkout / "home/dot_local/bin"
        bin_source.mkdir(parents=True)
        (bin_source / SCRIPT.name).write_bytes(SCRIPT.read_bytes())
        ports = checkout / "macports/ports.txt"
        ports.parent.mkdir()
        ports.write_text("git\nchezmoi\njq\n")
        defaults = checkout / "macos/defaults.sh"
        defaults.parent.mkdir()
        self.write_python(defaults, 'record("defaults", [])\n')
        bootstrap = checkout / "bootstrap.sh"
        bootstrap.write_text((ROOT / "bootstrap.sh").read_text().replace("/opt/local/bin", str(self.bin)))
        chezmoi_config = self.root / "chezmoi.toml"
        chezmoi_config.write_text("")
        self.env.update(
            REAL_CHEZMOI=CHEZMOI, TEST_CHEZMOI_CONFIG=str(chezmoi_config),
            TEST_ROOT=str(self.root),
        )
        self.write_command("xcode-select", 'sys.exit(0)\n')
        self.write_command("port", 'record("port", sys.argv[1:])\n')
        self.write_command("sudo", '''
args = sys.argv[1:]
if args[0] != "port":
    sys.exit(99)
os.execv(os.path.join(os.path.dirname(sys.argv[0]), "port"), args)
''')
        self.write_command("chezmoi", '''
record("chezmoi", sys.argv[1:])
root = os.environ["TEST_ROOT"]
args = [os.environ["REAL_CHEZMOI"], "--destination", os.environ["HOME"],
        "--config", os.environ["TEST_CHEZMOI_CONFIG"], "--cache", root + "/cache",
        "--persistent-state", root + "/state.boltdb", "--no-tty", *sys.argv[1:]]
os.execv(args[0], args)
''')
        return bootstrap, checkout

    def test_bootstrap_installs_command_and_delegates_updates_once(self):
        """実際のchezmoiで配置し、初期導入後の更新をmyupdateへ一度だけ委譲する。"""
        bootstrap, checkout = self.prepare_bootstrap()
        result = subprocess.run(
            ["/bin/bash", str(bootstrap)], cwd=checkout, env=self.env,
            capture_output=True, text=True,
        )
        self.assert_success(result)
        installed = self.home / ".local/bin/myupdate"
        self.assertEqual(installed.read_bytes(), SCRIPT.read_bytes())
        self.assertTrue(os.access(installed, os.X_OK))
        self.assertEqual(self.installs(), [*PACKAGES, f"{SKILLS}@{self.revision}"])
        calls = self.calls()
        apply_index = next(i for i, call in enumerate(calls) if call["command"] == "chezmoi")
        install_index = next(i for i, call in enumerate(calls) if call["command"] == "mise" and call["args"] == ["install"])
        upgrades = [i for i, call in enumerate(calls) if call["command"] == "mise" and call["args"][0] == "upgrade"]
        self.assertEqual(len(upgrades), 1)
        self.assertLess(apply_index, install_index)
        self.assertLess(install_index, upgrades[0])
        self.assertEqual(calls[-1]["command"], "defaults")
        self.assertNotIn("sync-skills.sh", bootstrap.read_text())

    def test_bootstrap_stops_before_defaults_when_daily_update_fails(self):
        """更新失敗をbootstrapにも伝播し、後続の実機設定へ進まないことを確認する。"""
        bootstrap, checkout = self.prepare_bootstrap()
        self.env["TEST_FAILED_PACKAGE"] = PACKAGES[0]
        result = subprocess.run(
            ["/bin/bash", str(bootstrap)], cwd=checkout, env=self.env,
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 7)
        self.assertEqual(self.installs(), [PACKAGES[0]])
        self.assertEqual(self.calls("defaults"), [])
        self.assertFalse(self.lock.exists())
        self.assertNotIn("all updates completed", result.stdout)


if __name__ == "__main__":
    unittest.main()
