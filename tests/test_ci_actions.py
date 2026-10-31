"""CI の action 固定が外れたままマージされるのを防ぐ静的テスト。

workflow の参照・lockfile・Dependabot・verify ステップの対応関係だけを検査し、
ネットワークや実リポジトリの状態には触れない。
"""

import re
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_DIR = ROOT / ".github/workflows"
LOCKFILE = WORKFLOW_DIR / "actions.lock"
DEPENDABOT = ROOT / ".github/dependabot.yml"

# `- uses: owner/repo@ref` / `uses: owner/repo@ref # comment` の参照部分を取り出す
USES_RE = re.compile(r"^\s*(?:-\s*)?uses:\s*([^\s#]+)")
# major のみ (`v4`) や major.minor のみ (`v4.2`) の可変 ref は固定漏れとみなす
MUTABLE_VERSION_RE = re.compile(r"^v?\d+(?:\.\d+)?$")


def workflow_files():
    """workflow 定義ファイルを列挙する。"""
    return sorted(WORKFLOW_DIR.glob("*.y*ml"))


def remote_refs(path):
    """workflow 内の外部 action 参照を返す。ローカル action と container は対象外。"""
    refs = []
    for line in path.read_text(encoding="utf-8").splitlines():
        match = USES_RE.match(line)
        if not match:
            continue
        target = match.group(1).strip("'\"")
        if target.startswith(("./", "$/", "docker://")):
            continue
        refs.append(target)
    return refs


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


class ActionsLockTests(unittest.TestCase):
    def test_lockfile_covers_every_remote_action_reference(self):
        self.assertTrue(LOCKFILE.is_file(), "actions.lock がありません")
        locked = lockfile_workflows(LOCKFILE.read_text(encoding="utf-8"))
        for path in workflow_files():
            relative = path.relative_to(ROOT).as_posix()
            refs = remote_refs(path)
            if not refs:
                continue
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
            for ref in remote_refs(path):
                _, _, version = ref.partition("@")
                if MUTABLE_VERSION_RE.match(version):
                    offenders.append(f"{path.relative_to(ROOT).as_posix()}: {ref}")
        self.assertEqual(
            offenders,
            [],
            "可変のバージョン ref が残っています。`gh actions-lock` で full semver へ narrow してください:\n"
            + "\n".join(offenders),
        )

    def test_dependabot_updates_github_actions(self):
        text = DEPENDABOT.read_text(encoding="utf-8")
        self.assertRegex(text, r'(?m)^\s*(?:-\s*)?package-ecosystem:\s*["\']?github-actions["\']?\s*$')
        self.assertRegex(text, r'(?m)^\s*directory:\s*["\']?/["\']?\s*$')
        self.assertRegex(text, r'(?m)^\s*interval:\s*["\']?weekly["\']?\s*$')

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
