"""CI の action 固定が外れたままマージされるのを防ぐ静的テスト。

workflow を YAML として構造で読み、`jobs.*.steps[*].uses` だけを対象にする。
`run:` 内の文字列やコメントに `uses:` が現れても参照として扱わない。
lockfile・Dependabot・verify ステップとの対応関係を検査し、ネットワークや
実リポジトリの状態には触れない。
"""

import re
import tempfile
from pathlib import Path
import textwrap
import unittest

import yaml


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_DIR = ROOT / ".github/workflows"
LOCKFILE = WORKFLOW_DIR / "actions.lock"
DEPENDABOT = ROOT / ".github/dependabot.yml"

# ローカル action と container は lockfile の対象外
LOCAL_PREFIXES = ("./", "$/", "docker://")
# major のみ (`v4`) や major.minor のみ (`v4.2`) の可変 ref は固定漏れとみなす
MUTABLE_VERSION_RE = re.compile(r"^v?\d+(?:\.\d+)?$")
FULL_SHA_RE = re.compile(r"^[0-9a-f]{40}$")


def load_workflow(path):
    """workflow の YAML を構造として読む。"""
    with Path(path).open(encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def iter_jobs(document):
    """`jobs` 配下の job 定義を列挙する。"""
    jobs = document.get("jobs")
    if not isinstance(jobs, dict):
        return
    for job in jobs.values():
        if isinstance(job, dict):
            yield job


def step_uses(document):
    """`jobs.*.steps[*].uses` の外部 action 参照を列挙する。"""
    refs = []
    for job in iter_jobs(document):
        steps = job.get("steps")
        if not isinstance(steps, list):
            continue
        for step in steps:
            if not isinstance(step, dict):
                continue
            uses = step.get("uses")
            if not isinstance(uses, str) or uses.startswith(LOCAL_PREFIXES):
                continue
            refs.append(uses)
    return refs


def reusable_workflow_uses(document):
    """job 直下の `uses`（reusable workflow 呼び出し）を列挙する。"""
    return [job["uses"] for job in iter_jobs(document) if isinstance(job.get("uses"), str)]


def workflow_files(directory=WORKFLOW_DIR):
    """workflow 定義ファイルを列挙する。"""
    return sorted(Path(directory).glob("*.y*ml"))


def references_by_workflow(directory=WORKFLOW_DIR):
    """`workflow の相対パス -> 外部 action 参照一覧` を返す。"""
    collected = {}
    for path in workflow_files(directory):
        refs = step_uses(load_workflow(path))
        if refs:
            collected[Path(path).name] = refs
    return collected


def lockfile_workflows(text):
    """lockfile の workflows 節を `workflow パス -> 参照一覧` として読む。"""
    locked = {}
    current = None
    in_section = False
    for line in text.splitlines():
        if not line.strip():
            continue
        if not line.startswith((" ", "\t")):
            in_section = line.strip() == "workflows:"
            current = None
            continue
        if not in_section:
            continue
        item = line.strip()
        if item.startswith("- "):
            if current is not None:
                locked[current].append(item[2:].strip().strip("'\""))
        else:
            current = item.rstrip(":").strip("'\"")
            locked[current] = []
    return locked


class UsesExtractionTests(unittest.TestCase):
    """取りこぼしと誤検出が再発しないよう、抽出の反例を固定する。"""

    def test_block_mapping_is_detected(self):
        document = yaml.safe_load("jobs:\n  a:\n    steps:\n      - uses: actions/cache@v4.2.3\n")
        self.assertEqual(step_uses(document), ["actions/cache@v4.2.3"])

    def test_flow_mapping_is_detected(self):
        document = yaml.safe_load("jobs:\n  a:\n    steps:\n      - {uses: actions/cache@v4.2.3}\n")
        self.assertEqual(step_uses(document), ["actions/cache@v4.2.3"])

    def test_quoted_key_is_detected(self):
        document = yaml.safe_load('jobs:\n  a:\n    steps:\n      - "uses": actions/cache@v4.2.3\n')
        self.assertEqual(step_uses(document), ["actions/cache@v4.2.3"])

    def test_value_on_following_line_is_detected(self):
        document = yaml.safe_load("jobs:\n  a:\n    steps:\n      - uses:\n          actions/cache@v4.2.3\n")
        self.assertEqual(step_uses(document), ["actions/cache@v4.2.3"])

    def test_uses_text_inside_run_is_not_a_reference(self):
        document = yaml.safe_load(
            textwrap.dedent(
                """\
                jobs:
                  a:
                    steps:
                      - run: |
                          echo "uses: actions/cache@v4.2.3"
                """
            )
        )
        self.assertEqual(step_uses(document), [])

    def test_local_and_container_targets_are_ignored(self):
        document = yaml.safe_load(
            textwrap.dedent(
                """\
                jobs:
                  a:
                    steps:
                      - uses: ./local
                      - uses: $/local
                      - uses: docker://alpine:3.19
                """
            )
        )
        self.assertEqual(step_uses(document), [])

    def test_reusable_workflow_call_is_separated_from_step_uses(self):
        document = yaml.safe_load(
            "jobs:\n  a:\n    uses: u7chan/macos-workstation/.github/workflows/x.yml@main\n"
        )
        self.assertEqual(step_uses(document), [])
        self.assertEqual(reusable_workflow_uses(document), ["u7chan/macos-workstation/.github/workflows/x.yml@main"])

    def test_unregistered_reference_in_temp_workflow_is_reported(self):
        with tempfile.TemporaryDirectory(prefix="ci actions ") as temporary:
            workflow = Path(temporary) / "regression.yml"
            workflow.write_text(
                textwrap.dedent(
                    """\
                    on: pull_request
                    jobs:
                      a:
                        runs-on: ubuntu-24.04
                        steps:
                          - {uses: actions/cache@v4.2.3}
                    """
                ),
                encoding="utf-8",
            )
            self.assertEqual(references_by_workflow(temporary), {"regression.yml": ["actions/cache@v4.2.3"]})


class ActionsLockTests(unittest.TestCase):
    def test_lockfile_covers_every_remote_action_reference(self):
        self.assertTrue(LOCKFILE.is_file(), "actions.lock がありません")
        locked = lockfile_workflows(LOCKFILE.read_text(encoding="utf-8"))
        for name, refs in references_by_workflow().items():
            relative = f".github/workflows/{name}"
            with self.subTest(workflow=relative):
                self.assertIn(
                    relative,
                    locked,
                    "lockfile に workflow が登録されていません。`gh actions-lock` で再生成してください",
                )
                for ref in refs:
                    self.assertIn(
                        ref,
                        locked[relative],
                        "lockfile に未登録の action 参照があります。`gh actions-lock` で再生成してください",
                    )

    def test_remote_action_references_are_not_mutable_version_refs(self):
        offenders = []
        for path in workflow_files():
            for ref in step_uses(load_workflow(path)):
                _, _, version = ref.partition("@")
                if MUTABLE_VERSION_RE.match(version):
                    offenders.append(f"{path.relative_to(ROOT).as_posix()}: {ref}")
        self.assertEqual(
            offenders,
            [],
            "可変のバージョン ref が残っています。`gh actions-lock` で full semver へ narrow してください:\n"
            + "\n".join(offenders),
        )

    def test_reusable_workflow_calls_are_pinned_to_a_full_sha(self):
        # reusable workflow は lockfile の対象外なので、呼び出し元の SHA 固定だけが防衛線になる
        offenders = []
        for path in workflow_files():
            for ref in reusable_workflow_uses(load_workflow(path)):
                _, _, version = ref.rpartition("@")
                if not FULL_SHA_RE.match(version):
                    offenders.append(f"{path.relative_to(ROOT).as_posix()}: {ref}")
        self.assertEqual(
            offenders,
            [],
            "reusable workflow の呼び出しを full commit SHA に固定してください:\n" + "\n".join(offenders),
        )

    def test_dependabot_updates_github_actions(self):
        text = DEPENDABOT.read_text(encoding="utf-8")
        self.assertRegex(text, r'(?m)^\s*(?:-\s*)?package-ecosystem:\s*["\']?github-actions["\']?\s*$')
        self.assertRegex(text, r'(?m)^\s*directory:\s*["\']?/["\']?\s*$')

    def test_a_workflow_verifies_the_lockfile(self):
        verified = []
        for path in workflow_files():
            text = path.read_text(encoding="utf-8")
            if "gh actions-lock --verify" not in text:
                continue
            if re.search(r"(?m)^\s*pull_request:\s*$", text):
                verified.append(path.relative_to(ROOT).as_posix())
        self.assertTrue(
            verified,
            "pull_request で `gh actions-lock --verify` を実行する workflow がありません",
        )


if __name__ == "__main__":
    unittest.main()
