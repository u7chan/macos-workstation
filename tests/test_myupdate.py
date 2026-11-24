"""一時HOMEで日次更新の範囲、停止条件、既存設定の保持、bootstrapからの委譲を確認する。

mise・Pi・Herdrの外部インストールと上流のdist.sh（配布の取得・検証・切替・link）は模擬し、
初回取得のgit cloneとchezmoiによる配置、GNU用PATHを限定するランチャーには実物を使う。
実ユーザーのツール・設定は変更せず、macOSでの実更新、実スキルの配布、
Pi・Claude Codeのスキル一覧への反映とExtensionのロードは別途確認する。
"""

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import tomllib
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "home/dot_local/bin/executable_myupdate"
GIT = shutil.which("git")
JQ = shutil.which("jq")
CHEZMOI = shutil.which("chezmoi")
MYPI = "git:github.com/u7chan/mypi@main"
PACKAGES = ("npm:pi-web-access", "npm:@ogulcancelik/pi-session-recall", MYPI)
SKILLS = "git:github.com/u7chan/agent-harness"
LEGACY_SKILLS = f"{SKILLS}@{'1' * 40}"
LAUNCHER = ROOT / "home/dot_local/bin/executable_agent-harness-exec"
GNU_TOOLS = ("grep", "stat", "mktemp", "sort", "head", "mv", "readlink")
PI_TOOL = "npm:@earendil-works/pi-coding-agent"
HERDR_TOOL = "aqua:herdrdev/herdr"
EXTRA_TOOLS = ("aqua:anthropics/claude-code", "bun", "npm:pnpm")
INVENTORY_ARGS = ["config", "ls", "--json"]

# 上流dist.shの模擬。実物の挙動（取得・main到達ゲート・切替・link）は上流のテストと実機で確認する。
# 呼び出しを記録し、updateが成功したら配布先にdist.sh自身を置く（初回導入後は配布先のものが使われる）。
DIST_STUB = '''
import shutil
from pathlib import Path
args = sys.argv[1:]
command = args[0] if args else ""
record("dist", args, script=os.path.realpath(sys.argv[0]), root=os.environ.get("AGENT_HARNESS_HOME"))
if "TEST_DIST_OCCUPY_LOCK" in os.environ:
    (Path(os.environ["HOME"]) / ".local/state/macos-workstation/myupdate.lock/occupied").write_text("")
status = int(os.environ.get("TEST_DIST_" + command.upper() + "_STATUS", "0"))
if status:
    sys.stderr.write("error: dist fixture failure\\n")
    sys.exit(status)
root = Path(os.environ.get("AGENT_HARNESS_HOME") or Path(os.environ["HOME"]) / ".local/share/agent-harness")
installed = root / "current/scripts/skill-distribution/dist.sh"
if command == "update":
    print("state=" + ("already-current" if installed.exists() else "updated"))
    if Path(__file__).resolve() != installed.resolve():
        installed.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(__file__, installed)
elif command != "status":
    sys.exit(99)
print("revision=" + os.environ["TEST_DIST_REVISION"])
'''


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
        (self.project / "mise.toml").write_text(
            '[tools]\nnode = "18"\nbun = "1.0.0"\n"npm:project-only" = "latest"\n'
        )
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
        for name in ("mkdir", "rmdir", "rm", "mktemp", "bash"):
            (self.bin / name).symlink_to(shutil.which(name))
        (self.bin / "jq").symlink_to(JQ)
        # 実物のランチャーをmacOS相当で動かす。GNU用ディレクトリだけを一時領域へ差し替える。
        self.gnu = self.root / "gnubin"
        for name in GNU_TOOLS:
            self.executable(
                self.gnu / name,
                '#!/bin/bash\n[ "$1" = --version ] && echo "fixture (GNU coreutils)"\nexit 0\n',
            )
        self.executable(self.bin / "uname", '#!/bin/bash\necho Darwin\n')
        self.launcher = self.home / ".local/bin/agent-harness-exec"
        self.executable(self.launcher, self.launcher_source())
        self.remote = self.root / "skill remote"
        self.git("init", "-b", "main", str(self.remote))
        self.executable(
            self.remote / "scripts/skill-distribution/dist.sh",
            self.python_source(DIST_STUB),
        )
        self.git("-C", str(self.remote), "add", "scripts/skill-distribution/dist.sh")
        self.commit_skills()
        self.git(
            "config", "--file", self.env["GIT_CONFIG_GLOBAL"],
            f"url.{self.remote.as_uri()}.insteadOf",
            "https://github.com/u7chan/agent-harness.git",
        )
        self.revision = self.git("-C", str(self.remote), "rev-parse", "HEAD")
        self.env["TEST_DIST_REVISION"] = self.revision
        self.write_command("git", '''
record("git", sys.argv[1:])
if "TEST_GIT_OUTPUT" in os.environ:
    print(os.environ["TEST_GIT_OUTPUT"], end="")
    sys.exit(int(os.environ.get("TEST_GIT_STATUS", "0")))
os.execv(os.environ["REAL_GIT"], [os.environ["REAL_GIT"], *sys.argv[1:]])
''')
        self.write_command("mise", '''
from pathlib import Path
import tomllib
args = sys.argv[1:]
record("mise", args)
if args == ["config", "ls", "--json"]:
    if "TEST_INVENTORY_OUTPUT" in os.environ:
        print(os.environ["TEST_INVENTORY_OUTPUT"], end="")
    else:
        config = Path(os.environ["MISE_CONFIG_FILE"])
        tools = tomllib.loads(config.read_text())["tools"]
        print(json.dumps([{"path": str(config.resolve()), "tools": list(tools)}]))
    sys.exit(int(os.environ.get("TEST_INVENTORY_STATUS", "0")))
# 旧方式へ戻した場合の回帰検出用。実物mise同様、版解決失敗を警告だけで省略する。
if args == ["ls", "--global", "--json"]:
    tools = tomllib.loads(Path(os.environ["MISE_CONFIG_FILE"]).read_text())["tools"]
    omitted = os.environ.get("TEST_OMITTED_TOOL")
    print(json.dumps({name: [{"installed": False}] for name in tools if name != omitted}))
    sys.exit(0)
if args[:2] == ["upgrade", "--no-prune"]:
    if args[2:] == ["npm:@earendil-works/pi-coding-agent"]:
        sys.exit(int(os.environ.get("TEST_UPGRADE_STATUS", "0")))
    if args[2:] == ["aqua:herdrdev/herdr"]:
        sys.exit(int(os.environ.get("TEST_HERDR_UPGRADE_STATUS", "0")))
    if len(args) == 3 and (args[2] in ("bun", "pnpm", "aqua:pnpm/pnpm", "aqua:anthropics/claude-code") or args[2].startswith("npm:")):
        sys.exit(5 if args[2] == os.environ.get("TEST_FAILED_TOOL") else 0)
    sys.exit(99)
if args == ["install"]:
    sys.exit(0)
if args[:2] == ["exec", "--"]:
    if args[2] in ("pi", "herdr"):
        target = os.path.join(os.environ["HOME"], "fresh " + args[2])
        os.execv(target, [target, *args[3:]])
    sys.exit(0)
sys.exit(99)
''')
        for name in ("pi", "herdr"):
            self.write_command(name, f'''
record("stale-{name}", sys.argv[1:])
sys.exit(99)
''')
        self.write_python(self.home / "fresh herdr", '''
args = sys.argv[1:]
record("herdr", args)
if args != ["--version"]:
    sys.exit(99)
print("herdr fixture")
sys.exit(int(os.environ.get("TEST_HERDR_VERSION_STATUS", "0")))
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
settings = Path(os.environ.get("PI_CODING_AGENT_DIR", str(Path.home() / ".pi/agent"))) / "settings.json"
if args[0] == "remove" and args[2:] == ["--no-approve"]:
    if args[1] == os.environ.get("TEST_FAILED_REMOVE"):
        sys.exit(7)
    if "TEST_REMOVE_NOOP" not in os.environ:
        data = json.loads(settings.read_text())
        data["packages"] = [
            package for package in data["packages"]
            if (package if isinstance(package, str) else package["source"]) != args[1]
        ]
        settings.write_text(json.dumps(data) + "\\n")
    sys.exit(0)
if args[0] != "install" or args[2:] != ["--no-approve"]:
    sys.exit(99)
source = args[1]
if source == os.environ.get("TEST_FAILED_PACKAGE"):
    sys.exit(7)
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

    @staticmethod
    def python_source(body):
        return (
            f"#!{sys.executable}\n"
            "import json, os, sys\n"
            "def record(command, args, **extra):\n"
            "    with open(os.environ['TEST_CALLS'], 'a') as log:\n"
            "        log.write(json.dumps({'command': command, 'args': args,\n"
            "            'cwd': os.getcwd(), 'config': os.environ.get('MISE_CONFIG_FILE'),\n"
            "            'path': os.environ.get('PATH'), **extra}) + '\\n')\n"
            + body
        )

    @staticmethod
    def executable(path, content):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        path.chmod(0o755)

    def launcher_source(self):
        source = LAUNCHER.read_text()
        self.assertEqual(source.count("/opt/local/libexec/gnubin"), 1)
        return source.replace("/opt/local/libexec/gnubin", str(self.gnu))

    def write_python(self, path, body):
        self.executable(path, self.python_source(body))

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

    def upgrades(self):
        return [call["args"] for call in self.calls("mise") if call["args"][0] == "upgrade"]

    def removals(self):
        return [call["args"][1] for call in self.calls("pi") if call["args"][0] == "remove"]

    def link_args(self):
        return ["--link-dir", str(self.home / ".agents/skills"),
                "--link-dir", str(self.home / ".claude/skills")]

    def seed_settings(self, packages):
        self.settings.parent.mkdir(parents=True, exist_ok=True)
        self.settings.write_text(json.dumps({"theme": "custom", "packages": packages}))
        return self.settings.read_text()

    def installed_dist(self, root=None):
        base = root or self.home / ".local/share/agent-harness"
        return base / "current/scripts/skill-distribution/dist.sh"

    def seed_installed_distribution(self):
        """配布先が導入済みの状態を、模擬dist.shの配置だけで作る。"""
        target = self.installed_dist()
        target.parent.mkdir(parents=True)
        shutil.copy(self.remote / "scripts/skill-distribution/dist.sh", target)

    def bootstrap_leftovers(self):
        return sorted(path.name for path in self.lock.parent.glob("agent-skills-bootstrap.*"))

    def assert_success(self, result):
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("all updates completed successfully", result.stdout)
        self.assertIn("Start Pi to begin work.", result.stdout)
        self.assertIn("Exit all Pi sessions before the next update.", result.stdout)
        self.assertNotIn("/reload", result.stdout)
        self.assertFalse(self.lock.exists())
        self.assertEqual(self.calls("stale-pi"), [])
        self.assertEqual(self.calls("stale-herdr"), [])
        self.assertIn("herdr fixture", result.stdout)
        self.assertEqual(self.project_settings.read_text(), '{"packages":["npm:project-only"]}\n')

class MyupdateTests(MyupdateFixture):
    def test_updates_only_selected_global_tools_before_managed_packages(self):
        """グローバルの対象だけを更新し、プロジェクト依存と他のツールは変更しない。"""
        result = self.run_update()
        self.assert_success(result)
        self.assertEqual(self.installs(), list(PACKAGES))
        self.assertEqual([call["args"] for call in self.calls()[:3]], [
            INVENTORY_ARGS,
            ["upgrade", "--no-prune", PI_TOOL],
            ["upgrade", "--no-prune", HERDR_TOOL],
        ])
        self.assertEqual(self.upgrades(), [
            ["upgrade", "--no-prune", tool] for tool in (PI_TOOL, HERDR_TOOL, *EXTRA_TOOLS)
        ])
        self.assertEqual([call["args"] for call in self.calls("herdr")], [["--version"]])
        for call in self.calls():
            self.assertEqual(Path(call["cwd"]), self.home.resolve())
            self.assertEqual(call["config"], str(self.config))
        self.assertIn(self.revision, result.stdout)

    def test_repeated_runs_preserve_unmanaged_settings_and_resource_filters(self):
        """旧agent-harness登録だけを解除し、他の設定・パッケージ・フィルターは繰り返しても保持する。"""
        existing = {
            "theme": "custom", "unmanaged": {"keep": True},
            "packages": ["npm:unrelated", {"source": PACKAGES[0], "extensions": ["selected.ts"]},
                         {"source": LEGACY_SKILLS, "skills": ["gh"]},
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
        self.assertEqual(first["packages"], [
            "npm:unrelated",
            {"source": PACKAGES[0], "extensions": ["selected.ts"]},
            {"source": MYPI, "extensions": ["extensions/index.ts"], "skills": []},
            PACKAGES[1],
        ])
        self.assertEqual(self.installs(), list(PACKAGES) * 2)
        self.assertEqual(len(self.removals()), 1)

    def test_each_run_delegates_revision_selection_to_the_distribution_command(self):
        """版の解決はdist.shに任せ、2回目以降は取得し直さず配布先のdist.shで更新する。"""
        self.assert_success(self.run_update())
        result = self.run_update()
        self.assert_success(result)
        self.assertEqual([call["args"][0] for call in self.calls("dist")],
                         ["update", "status", "update", "status"])
        self.assertEqual(len([c for c in self.calls("git") if c["args"][0] == "clone"]), 1)
        self.assertEqual([c for c in self.calls("git") if c["args"][0] == "ls-remote"], [])
        self.assertEqual(self.installs(), list(PACKAGES) * 2)
        self.assertIn(self.revision, result.stdout)

    def test_upgrade_failure_stops_before_package_operations_and_releases_lock(self):
        self.env["TEST_UPGRADE_STATUS"] = "9"
        result = self.run_update()
        self.assertEqual(result.returncode, 9)
        self.assertEqual([call["args"] for call in self.calls()], [
            INVENTORY_ARGS,
            ["upgrade", "--no-prune", PI_TOOL],
        ])
        self.assertFalse(self.lock.exists())
        self.assertNotIn("all updates completed", result.stdout)

    def test_herdr_upgrade_failure_stops_before_packages_and_releases_lock(self):
        """Herdr更新失敗後はパッケージ更新へ進まず、既存設定を保持する。"""
        self.settings.parent.mkdir(parents=True)
        original = '{"theme":"custom","packages":["npm:unrelated"]}\n'
        self.settings.write_text(original)
        self.env["TEST_HERDR_UPGRADE_STATUS"] = "8"
        result = self.run_update()
        self.assertEqual(result.returncode, 8)
        self.assertEqual([call["args"] for call in self.calls()], [
            INVENTORY_ARGS,
            ["upgrade", "--no-prune", PI_TOOL],
            ["upgrade", "--no-prune", HERDR_TOOL],
        ])
        self.assertEqual(self.settings.read_text(), original)
        self.assertFalse(self.lock.exists())
        self.assertNotIn("all updates completed", result.stdout)

    def test_additional_global_npm_clis_are_discovered_without_updater_changes(self):
        """npm製CLIの宣言だけで更新対象になり、Piは重複更新しない。"""
        with self.config.open("a") as config:
            config.write('"npm:@fixture/cli" = "2"\n"npm:prettier" = "3"\n')
        original = self.config.read_bytes()
        self.assert_success(self.run_update())
        self.assertEqual(self.upgrades(), [
            ["upgrade", "--no-prune", tool]
            for tool in (PI_TOOL, HERDR_TOOL, *sorted((*EXTRA_TOOLS, "npm:@fixture/cli", "npm:prettier")))
        ])
        self.assertEqual(self.config.read_bytes(), original)

    def test_version_resolution_failure_cannot_silently_omit_declared_cli(self):
        """版解決一覧から欠落するCLIも宣言から対象にし、更新失敗を成功扱いしない。"""
        with self.config.open("a") as config:
            config.write('"npm:prettier" = "3"\n')
        self.env.update(TEST_OMITTED_TOOL="npm:prettier", TEST_FAILED_TOOL="npm:prettier")
        self.settings.parent.mkdir(parents=True)
        original = '{"theme":"custom"}\n'
        self.settings.write_text(original)
        result = self.run_update()
        self.assertEqual(result.returncode, 5)
        self.assertEqual(self.upgrades(), [
            ["upgrade", "--no-prune", tool]
            for tool in (PI_TOOL, HERDR_TOOL, *EXTRA_TOOLS, "npm:prettier")
        ])
        self.assertEqual(self.calls("mise")[0]["args"], INVENTORY_ARGS)
        self.assertEqual(self.calls("pi"), [])
        self.assertEqual(self.settings.read_text(), original)
        self.assertFalse(self.lock.exists())
        self.assertNotIn("all updates completed", result.stdout)

    def test_declarations_from_other_configurations_are_not_update_targets(self):
        """一覧に他の設定が含まれていても、指定グローバル設定以外は取り込まない。"""
        other = self.home / "mise.toml"
        other.write_text('[tools]\n"npm:unmanaged" = "latest"\n')
        tools = list(tomllib.loads(self.config.read_text())["tools"])
        self.env["TEST_INVENTORY_OUTPUT"] = json.dumps([
            {"path": str(other), "tools": ["npm:unmanaged"]},
            {"path": str(self.config), "tools": tools},
        ])
        self.assert_success(self.run_update())
        self.assertEqual(self.upgrades(), [
            ["upgrade", "--no-prune", tool] for tool in (PI_TOOL, HERDR_TOOL, *EXTRA_TOOLS)
        ])

    def test_symlinked_global_configuration_matches_physical_metadata_path(self):
        """設定ファイルがシンボリックリンクでも、物理パスとの同一性で宣言を特定する。"""
        target = self.root / "linked global config.toml"
        self.config.rename(target)
        self.config.symlink_to(target)
        self.assert_success(self.run_update())
        self.assertEqual(self.upgrades(), [
            ["upgrade", "--no-prune", tool] for tool in (PI_TOOL, HERDR_TOOL, *EXTRA_TOOLS)
        ])
        self.assertTrue(self.config.is_symlink())

    def test_missing_or_duplicate_global_metadata_stops_before_all_updates(self):
        """指定設定が一覧にない場合や一意でない場合は、全更新前に停止する。"""
        entry = {"path": str(self.config), "tools": [*EXTRA_TOOLS]}
        for entries, message in (([], "not found"), ([entry, entry], "duplicate")):
            with self.subTest(entries=entries):
                self.log.unlink(missing_ok=True)
                self.env["TEST_INVENTORY_OUTPUT"] = json.dumps(entries)
                result = self.run_update()
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(message, result.stderr)
                self.assertEqual([call["args"] for call in self.calls()], [INVENTORY_ARGS])
                self.assertFalse(self.lock.exists())
                self.assertNotIn("all updates completed", result.stdout)

    def test_invalid_global_configuration_stops_before_all_updates(self):
        """設定の構文エラーも一覧取得失敗として扱い、更新前に停止する。"""
        self.config.write_text('[tools]\nbun = [')
        result = self.run_update()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual([call["args"] for call in self.calls()], [INVENTORY_ARGS])
        self.assertEqual(self.config.read_text(), '[tools]\nbun = [')
        self.assertFalse(self.lock.exists())
        self.assertNotIn("all updates completed", result.stdout)

    def test_empty_extra_selection_never_upgrades_all_tools(self):
        """対象が空でも引数なしのupgradeを呼ばず、全ツール更新を防ぐ。"""
        self.config.write_text(
            f'[tools]\n"{PI_TOOL}" = "latest"\n"{HERDR_TOOL}" = "latest"\n'
            'node = "26"\npython = "3.13"\nuv = "latest"\n'
        )
        self.assert_success(self.run_update())
        self.assertEqual(self.upgrades(), [
            ["upgrade", "--no-prune", PI_TOOL],
            ["upgrade", "--no-prune", HERDR_TOOL],
        ])

    def test_aqua_and_shorthand_pnpm_overrides_are_selected_by_declared_name(self):
        """利用者が別方式を指定した場合も宣言上の識別子で選択する。実インストール可否は別途確認する。"""
        self.config.write_text(self.config.read_text().replace(
            '"npm:pnpm" = { version = "latest", allow_builds = ["pnpm"] }',
            'pnpm = "latest"\n"aqua:pnpm/pnpm" = "latest"'
        ))
        self.assert_success(self.run_update())
        self.assertEqual(self.upgrades(), [
            ["upgrade", "--no-prune", tool]
            for tool in (PI_TOOL, HERDR_TOOL, "aqua:anthropics/claude-code", "aqua:pnpm/pnpm", "bun", "pnpm")
        ])

    def test_inventory_failure_stops_before_all_updates_and_releases_lock(self):
        """有効な一覧が出力されても取得失敗なら更新を始めない。"""
        self.env.update(TEST_INVENTORY_STATUS="4", TEST_INVENTORY_OUTPUT=json.dumps([
            {"path": str(self.config), "tools": ["bun"]},
        ]))
        result = self.run_update()
        self.assertEqual(result.returncode, 4)
        self.assertEqual([call["args"] for call in self.calls()], [INVENTORY_ARGS])
        self.assertFalse(self.lock.exists())
        self.assertNotIn("all updates completed", result.stdout)

    def test_invalid_inventory_stops_before_all_updates(self):
        """壊れたJSONや形式の異なる設定メタデータで更新範囲を拡大しない。"""
        for output in ("", "{", "null", "{}", '"bun"', '[]\n[]', '[]\ninvalid',
                       '[{}]', '[{"path":42,"tools":[]}]',
                       '[{"path":"config.toml","tools":null}]',
                       '[{"path":"config.toml","tools":[42]}]'):
            with self.subTest(output=output):
                self.log.unlink(missing_ok=True)
                self.env["TEST_INVENTORY_OUTPUT"] = output
                result = self.run_update()
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual([call["args"] for call in self.calls()], [INVENTORY_ARGS])
                self.assertFalse(self.lock.exists())
                self.assertNotIn("all updates completed", result.stdout)

    def test_extra_tool_failure_stops_before_packages_and_preserves_settings(self):
        """追加ツール更新の失敗時は再試行せず、Pi設定と後続処理を保護する。"""
        with self.config.open("a") as config:
            config.write('"npm:fixture-cli" = "latest"\n')
        self.settings.parent.mkdir(parents=True)
        original = '{"theme":"custom","packages":["npm:unrelated"]}\n'
        self.settings.write_text(original)
        tools = (PI_TOOL, HERDR_TOOL, *sorted((*EXTRA_TOOLS, "npm:fixture-cli")))
        for tool in tools[2:]:
            with self.subTest(tool=tool):
                self.log.unlink(missing_ok=True)
                self.env["TEST_FAILED_TOOL"] = tool
                result = self.run_update()
                self.assertEqual(result.returncode, 5)
                self.assertEqual(self.upgrades(), [
                    ["upgrade", "--no-prune", name] for name in tools[:tools.index(tool) + 1]
                ])
                self.assertEqual(self.calls("pi"), [])
                self.assertEqual(self.settings.read_text(), original)
                self.assertFalse(self.lock.exists())
                self.assertNotIn("all updates completed", result.stdout)

    def test_javascript_tools_are_declared_in_global_mise_configuration(self):
        """npm版pnpmと本体だけのスクリプト許可を固定し、Intel非対応や起動不能への回帰を防ぐ。"""
        tools = tomllib.loads(self.config.read_text())["tools"]
        self.assertEqual(tools["bun"], "latest")
        self.assertEqual(tools["npm:pnpm"], {"version": "latest", "allow_builds": ["pnpm"]})
        self.assertNotIn("aqua:pnpm/pnpm", tools)
        self.assertNotIn("pnpm", tools)

    def test_claude_code_is_declared_in_global_mise_configuration(self):
        """ネイティブ版Claude Codeをmiseで導入し、更新対象に含める。"""
        tools = tomllib.loads(self.config.read_text())["tools"]
        self.assertEqual(tools["aqua:anthropics/claude-code"], "latest")
        self.assertNotIn("npm:@anthropic-ai/claude-code", tools)

    def test_herdr_version_failure_does_not_report_success(self):
        """更新後のHerdr確認に失敗した場合も成功と報告しない。"""
        self.env["TEST_HERDR_VERSION_STATUS"] = "6"
        result = self.run_update()
        self.assertEqual(result.returncode, 6)
        self.assertEqual(self.installs(), list(PACKAGES))
        self.assertFalse(self.lock.exists())
        self.assertNotIn("all updates completed", result.stdout)

    def test_herdr_is_declared_in_global_mise_configuration(self):
        """bootstrapが利用するグローバル定義にHerdrの制約があることを確認する。"""
        config = tomllib.loads(self.config.read_text())
        self.assertEqual(config["tools"][HERDR_TOOL], "latest")

    def test_package_failure_stops_remaining_updates_without_retry(self):
        for source in PACKAGES:
            with self.subTest(source=source):
                self.log.unlink(missing_ok=True)
                self.env["TEST_FAILED_PACKAGE"] = source
                result = self.run_update()
                self.assertEqual(result.returncode, 7)
                self.assertEqual(self.installs()[-1], source)
                self.assertEqual(self.installs().count(source), 1)
                self.assertEqual(self.calls("dist"), [])
                self.assertFalse(self.lock.exists())
                self.assertNotIn("all updates completed", result.stdout)

    def test_first_install_clones_main_then_installs_through_gnu_launcher(self):
        """初回は上流mainを一時取得し、その中のdist.shで共有スキル置き場を作って状態を確認する。"""
        agents = self.home / ".agents/skills"
        claude = self.home / ".claude/skills"
        (agents / "own skill").mkdir(parents=True)
        (agents / "own skill/SKILL.md").write_text("mine\n")
        claude.mkdir(parents=True)
        (claude / "note.txt").write_text("keep\n")
        result = self.run_update()
        self.assert_success(result)
        clones = [c["args"] for c in self.calls("git") if c["args"][0] == "clone"]
        self.assertEqual(len(clones), 1)
        self.assertEqual(clones[0][:6], ["clone", "--quiet", "--depth", "1", "--branch", "main"])
        self.assertEqual(clones[0][6], "https://github.com/u7chan/agent-harness.git")
        update, status = self.calls("dist")
        self.assertEqual(update["args"], ["update", *self.link_args()])
        self.assertEqual(status["args"], ["status", *self.link_args()])
        self.assertIn("agent-skills-bootstrap.", update["script"])
        self.assertEqual(status["script"], str(self.installed_dist().resolve()))
        self.assertEqual((agents / "own skill/SKILL.md").read_text(), "mine\n")
        self.assertEqual((claude / "note.txt").read_text(), "keep\n")
        self.assertEqual(self.bootstrap_leftovers(), [])
        self.assertIn(self.revision, result.stdout)

    def test_distribution_runs_only_with_gnu_path_and_never_exposes_it_elsewhere(self):
        """GNU用PATHはdist.shとその子だけに限定し、他のコマンドや呼び出し元には広げない。"""
        self.assert_success(self.run_update())
        self.assert_success(self.run_update())
        for call in self.calls():
            directories = call["path"].split(os.pathsep)
            if call["command"] == "dist":
                self.assertEqual(directories[0], str(self.gnu))
            else:
                self.assertNotIn(str(self.gnu), directories, call)

    def test_distribution_is_independent_of_pi_when_nothing_is_registered(self):
        """旧登録がなければ、スキル配布はPiを一切呼ばず、Piはパッケージ更新と確認だけに使われる。"""
        self.assert_success(self.run_update())
        pi = [call["args"][0] for call in self.calls("pi")]
        self.assertEqual(pi, ["install"] * len(PACKAGES) + ["--version", "list"])
        calls = [call["command"] for call in self.calls()]
        first_dist = calls.index("dist")
        last_dist = len(calls) - 1 - calls[::-1].index("dist")
        self.assertNotIn("pi", calls[first_dist:last_dist + 1])
        self.assertNotIn("--no-link", SCRIPT.read_text())
        self.assertNotIn("--replace-links", SCRIPT.read_text())

    def test_legacy_pi_registration_is_removed_only_after_distribution_is_verified(self):
        """検証済みの配布後に旧登録だけを解除し、他のパッケージ・設定・似た名前の登録は残す。"""
        lookalike = "git:github.com/u7chan/agent-harness-other@abc"
        self.seed_settings([
            "npm:unrelated", LEGACY_SKILLS, lookalike,
            {"source": f"{SKILLS}@{'3' * 40}", "skills": ["gh"]},
            {"source": PACKAGES[0], "extensions": ["selected.ts"]},
        ])
        result = self.run_update()
        self.assert_success(result)
        settings = json.loads(self.settings.read_text())
        self.assertEqual(settings["theme"], "custom")
        self.assertEqual(settings["packages"], [
            "npm:unrelated", lookalike,
            {"source": PACKAGES[0], "extensions": ["selected.ts"]},
            PACKAGES[1], PACKAGES[2],
        ])
        self.assertEqual(self.removals(), [LEGACY_SKILLS, f"{SKILLS}@{'3' * 40}"])
        for call in self.calls("pi"):
            if call["args"][0] == "remove":
                self.assertEqual(call["args"][2:], ["--no-approve"])
        order = [call["command"] + ":" + call["args"][0] for call in self.calls()
                 if call["command"] in ("dist", "pi") and call["args"][0] != "--version"]
        self.assertLess(order.index("dist:status"), order.index("pi:remove"))
        self.assertIn('"skills":["gh"]', result.stdout)

    def test_distribution_failure_keeps_legacy_registration_and_stops(self):
        """配布の失敗は握りつぶさず、旧登録を残して停止し、一時取得物も残さない。"""
        original = self.seed_settings([LEGACY_SKILLS])
        for installed in (False, True):
            with self.subTest(installed=installed):
                shutil.rmtree(self.home / ".local/share", ignore_errors=True)
                self.settings.write_text(original)
                if installed:
                    self.seed_installed_distribution()
                self.log.unlink(missing_ok=True)
                self.env["TEST_DIST_UPDATE_STATUS"] = "4"
                result = self.run_update()
                del self.env["TEST_DIST_UPDATE_STATUS"]
                self.assertEqual(result.returncode, 4)
                self.assertIn("dist fixture failure", result.stderr)
                self.assertEqual([c["args"][0] for c in self.calls("dist")], ["update"])
                self.assertEqual(self.removals(), [])
                self.assertEqual(json.loads(self.settings.read_text())["packages"][0], LEGACY_SKILLS)
                self.assertEqual(self.calls("herdr"), [])
                self.assertEqual(self.bootstrap_leftovers(), [])
                self.assertFalse(self.lock.exists())
                self.assertNotIn("all updates completed", result.stdout)

    def test_status_failure_keeps_legacy_registration_and_stops(self):
        """更新後の整合確認に失敗した場合は、旧登録を解除せず成功と報告しない。"""
        self.seed_settings([LEGACY_SKILLS])
        self.env["TEST_DIST_STATUS_STATUS"] = "3"
        result = self.run_update()
        self.assertEqual(result.returncode, 3)
        self.assertEqual([c["args"][0] for c in self.calls("dist")], ["update", "status"])
        self.assertEqual(self.removals(), [])
        self.assertIn(LEGACY_SKILLS, json.loads(self.settings.read_text())["packages"])
        self.assertEqual(self.bootstrap_leftovers(), [])
        self.assertFalse(self.lock.exists())
        self.assertNotIn("all updates completed", result.stdout)

    def test_legacy_removal_failures_are_reported_and_keep_distribution(self):
        """旧登録の解除失敗は成功扱いにせず、検証済みの配布は維持し、復旧用の手動コマンドを示す。"""
        for env, status, message in (
            ({"TEST_FAILED_REMOVE": LEGACY_SKILLS}, 7, f"pi remove {LEGACY_SKILLS} --no-approve"),
            ({"TEST_REMOVE_NOOP": "1"}, 1, "still present"),
        ):
            with self.subTest(env=env):
                self.log.unlink(missing_ok=True)
                self.seed_settings(["npm:unrelated", LEGACY_SKILLS])
                self.env.update(env)
                result = self.run_update()
                for key in env:
                    del self.env[key]
                self.assertEqual(result.returncode, status)
                self.assertIn(message, result.stderr)
                self.assertTrue(self.installed_dist().exists())
                self.assertEqual(json.loads(self.settings.read_text())["packages"][:2],
                                 ["npm:unrelated", LEGACY_SKILLS])
                self.assertEqual(self.calls("herdr"), [])
                self.assertFalse(self.lock.exists())
                self.assertNotIn("all updates completed", result.stdout)

    def test_failed_first_fetch_stops_before_distribution_and_registration_changes(self):
        """初回取得の失敗（mainなし・取得エラー）は配布を始めず、旧登録と設定を保持する。"""
        original = self.seed_settings([LEGACY_SKILLS, "npm:unrelated"])
        for failure in ("missing-main", "fetch-error"):
            with self.subTest(failure=failure):
                self.log.unlink(missing_ok=True)
                self.settings.write_text(original)
                if failure == "missing-main":
                    self.git("-C", str(self.remote), "branch", "-m", "other")
                else:
                    self.env.update(TEST_GIT_OUTPUT="", TEST_GIT_STATUS="128")
                result = self.run_update()
                if failure == "missing-main":
                    self.git("-C", str(self.remote), "branch", "-m", "main")
                else:
                    del self.env["TEST_GIT_OUTPUT"], self.env["TEST_GIT_STATUS"]
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(self.calls("dist"), [])
                self.assertEqual(self.removals(), [])
                self.assertEqual(self.installs(), list(PACKAGES))
                self.assertIn(LEGACY_SKILLS, json.loads(self.settings.read_text())["packages"])
                self.assertFalse(self.installed_dist().exists())
                self.assertEqual(self.bootstrap_leftovers(), [])
                self.assertFalse(self.lock.exists())
                self.assertNotIn("all updates completed", result.stdout)

    def test_custom_distribution_root_is_respected(self):
        """AGENT_HARNESS_HOMEを指定した場合は、その配布先のdist.shで更新する。"""
        custom = self.root / "custom distribution"
        self.env["AGENT_HARNESS_HOME"] = str(custom)
        self.assert_success(self.run_update())
        self.assert_success(self.run_update())
        self.assertTrue(self.installed_dist(custom).exists())
        self.assertFalse(self.installed_dist().exists())
        self.assertEqual([call["root"] for call in self.calls("dist")], [str(custom)] * 4)
        self.assertEqual(self.calls("dist")[3]["script"], str(self.installed_dist(custom).resolve()))

    def test_temporary_clone_is_removed_even_when_lock_release_fails(self):
        """ロック解除（rmdir）が失敗しても、初回取得の一時ディレクトリを残さない。"""
        self.env.update(TEST_DIST_OCCUPY_LOCK="1", TEST_DIST_UPDATE_STATUS="4")
        result = self.run_update()
        self.assertNotEqual(result.returncode, 0)
        self.assertTrue((self.lock / "occupied").exists())
        self.assertEqual(self.bootstrap_leftovers(), [])

    def test_relative_distribution_or_state_paths_stop_before_any_update(self):
        """ランチャーとdist.shは絶対パスを要するため、相対指定はPiの更新前に拒否する。"""
        for name, message in (("AGENT_HARNESS_HOME", "must be absolute"),
                              ("XDG_DATA_HOME", "must be absolute"),
                              ("XDG_STATE_HOME", "must be an absolute")):
            with self.subTest(name=name):
                self.env[name] = "relative/path"
                result = self.run_update()
                del self.env[name]
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(message, result.stderr)
                self.assertEqual(self.calls(), [])
                self.assertFalse(self.lock.exists())

    def test_unusable_current_release_is_reported_as_repair(self):
        """currentがあるのにdist.shが使えない場合は、黙って再構築せず修復することを表示する。"""
        self.seed_installed_distribution()
        self.installed_dist().chmod(0o644)
        result = self.run_update()
        self.assert_success(result)
        self.assertIn("repairing agent skills", result.stdout)
        self.assertIn("agent-skills-bootstrap.", self.calls("dist")[0]["script"])
        self.log.unlink()
        clean = self.run_update()
        self.assert_success(clean)
        self.assertNotIn("repairing", clean.stdout)

    def test_missing_launcher_stops_before_any_update(self):
        """GNU用ランチャーがなければ、更新を始める前に停止する。"""
        self.launcher.unlink()
        result = self.run_update()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("run bootstrap first", result.stderr)
        self.assertEqual(self.calls(), [])
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

    def test_custom_mise_configuration_directory_is_respected(self):
        """空白を含むXDG設定先でも、そのグローバル宣言だけを参照する。"""
        config_home = self.root / "custom config"
        destination = config_home / "mise/config.toml"
        destination.parent.mkdir(parents=True)
        self.config.rename(destination)
        self.config = destination
        self.env["XDG_CONFIG_HOME"] = str(config_home)
        self.assert_success(self.run_update())
        self.assertTrue(all(call["config"] == str(self.config) for call in self.calls()))
        self.assertEqual(self.upgrades(), [
            ["upgrade", "--no-prune", tool] for tool in (PI_TOOL, HERDR_TOOL, *EXTRA_TOOLS)
        ])

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
        self.assertIn("Claude Code", result.stdout)
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
        (bin_source / LAUNCHER.name).write_text(self.launcher_source())
        (bin_source / LAUNCHER.name).chmod(0o755)
        # 配置前の状態から始め、ランチャーをchezmoiが導入することを確認する。
        self.launcher.unlink()
        config_source = checkout / "home/dot_config/mise/config.toml"
        config_source.parent.mkdir(parents=True)
        config_source.write_bytes((ROOT / "home/dot_config/mise/config.toml").read_bytes())
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
        self.config.unlink()
        result = subprocess.run(
            ["/bin/bash", str(bootstrap)], cwd=checkout, env=self.env,
            capture_output=True, text=True,
        )
        self.assert_success(result)
        installed = self.home / ".local/bin/myupdate"
        self.assertEqual(installed.read_bytes(), SCRIPT.read_bytes())
        self.assertTrue(os.access(installed, os.X_OK))
        self.assertEqual(self.launcher.read_text(), self.launcher_source())
        self.assertTrue(os.access(self.launcher, os.X_OK))
        self.assertEqual(self.config.read_bytes(), (ROOT / "home/dot_config/mise/config.toml").read_bytes())
        self.assertEqual(self.installs(), list(PACKAGES))
        self.assertEqual([call["args"][0] for call in self.calls("dist")], ["update", "status"])
        calls = self.calls()
        apply_index = next(i for i, call in enumerate(calls) if call["command"] == "chezmoi")
        install_index = next(i for i, call in enumerate(calls) if call["command"] == "mise" and call["args"] == ["install"])
        upgrades = [i for i, call in enumerate(calls) if call["command"] == "mise" and call["args"][0] == "upgrade"]
        self.assertEqual([calls[i]["args"] for i in upgrades], [
            ["upgrade", "--no-prune", tool] for tool in (PI_TOOL, HERDR_TOOL, *EXTRA_TOOLS)
        ])
        self.assertLess(apply_index, install_index)
        self.assertLess(install_index, upgrades[0])
        self.assertEqual(calls[-1]["command"], "defaults")
        self.assertNotIn("sync-skills.sh", bootstrap.read_text())

    def test_bootstrap_stops_before_defaults_when_herdr_update_fails(self):
        """Herdr更新失敗をbootstrapへ伝播し、後続の実機設定を変更しない。"""
        bootstrap, checkout = self.prepare_bootstrap()
        self.env["TEST_HERDR_UPGRADE_STATUS"] = "8"
        result = subprocess.run(
            ["/bin/bash", str(bootstrap)], cwd=checkout, env=self.env,
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 8)
        self.assertEqual(self.calls("pi"), [])
        self.assertEqual(self.calls("defaults"), [])
        self.assertFalse(self.lock.exists())
        self.assertNotIn("all updates completed", result.stdout)

    def test_bootstrap_stops_before_defaults_when_javascript_tool_update_fails(self):
        """追加ツール更新失敗をbootstrapへ伝播し、後続の実機設定を変更しない。"""
        bootstrap, checkout = self.prepare_bootstrap()
        self.env["TEST_FAILED_TOOL"] = "bun"
        result = subprocess.run(
            ["/bin/bash", str(bootstrap)], cwd=checkout, env=self.env,
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 5)
        self.assertEqual(self.calls("pi"), [])
        self.assertEqual(self.calls("defaults"), [])
        self.assertFalse(self.lock.exists())
        self.assertNotIn("all updates completed", result.stdout)

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
