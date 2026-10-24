"""実際の一時Gitリポジトリと模擬ghで、最新化とマージ済みブランチ削除の安全策を確認する。

GitHubへの実接続と、適用後のログインシェルからの利用は別途実機で確認する。
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
SCRIPT = ROOT / "home/dot_local/bin/executable_gpc"
PROFILE = ROOT / "home/dot_zprofile"
GIT = shutil.which("git")
CHEZMOI = shutil.which("chezmoi")
ZSH = shutil.which("zsh")


@unittest.skipUnless(GIT, "git is required for gpc tests")
class GpcTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="gpc test ")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.home = self.root / "home"
        self.bin = self.root / "bin"
        self.home.mkdir()
        self.bin.mkdir()
        self.remote = self.root / "origin.git"
        self.seed = self.root / "seed"
        self.repo = self.root / "work"
        self.gh_log = self.root / "gh-calls.jsonl"
        self.origin_url = "https://github.com/gpc-fixture/repository.git"
        self.branch = "feature/cleanup"
        self.env = {
            key: value for key, value in os.environ.items()
            if not key.startswith(("GIT_", "GH_", "GITHUB_"))
        }
        self.env.update(
            HOME=str(self.home),
            XDG_CONFIG_HOME=str(self.home / ".config"),
            LC_ALL="C",
            PATH=f"{self.bin}{os.pathsep}{os.environ['PATH']}",
            GIT_CONFIG_NOSYSTEM="1",
            GIT_CONFIG_GLOBAL=os.devnull,
            GIT_TERMINAL_PROMPT="0",
            GIT_AUTHOR_NAME="Fixture",
            GIT_AUTHOR_EMAIL="gpc-test",
            GIT_COMMITTER_NAME="Fixture",
            GIT_COMMITTER_EMAIL="gpc-test",
            GPC_GH_LOG=str(self.gh_log),
            GPC_AUTH_STATUS="0",
            GPC_PR_STATUS="0",
            GPC_PR_FIELDS="",
        )
        gh = self.bin / "gh"
        gh.write_text(
            f"#!{sys.executable}\n"
            "import json, os, sys\n"
            "with open(os.environ['GPC_GH_LOG'], 'a') as log:\n"
            "    log.write(json.dumps(sys.argv[1:]) + '\\n')\n"
            "if sys.argv[1:3] == ['auth', 'status']:\n"
            "    sys.exit(int(os.environ['GPC_AUTH_STATUS']))\n"
            "if sys.argv[1:3] == ['pr', 'view']:\n"
            "    print(os.environ['GPC_PR_FIELDS'])\n"
            "    sys.exit(int(os.environ['GPC_PR_STATUS']))\n"
            "sys.exit(99)\n"
        )
        gh.chmod(0o755)
        self.git("init", "--bare", "--initial-branch=main", str(self.remote), cwd=self.root)
        self.git("init", "--initial-branch=main", str(self.seed), cwd=self.root)
        self.initial = self.commit(self.seed, "initial")
        self.git("remote", "add", "origin", str(self.remote), cwd=self.seed)
        self.git("push", "-u", "origin", "main", cwd=self.seed)
        self.git("clone", str(self.remote), str(self.repo), cwd=self.root)
        self.set_origin(self.origin_url)

    def git(self, *args, cwd=None):
        return subprocess.check_output(
            [GIT, *args], cwd=cwd or self.repo, env=self.env,
            text=True, stderr=subprocess.PIPE,
        ).strip()

    def commit(self, repo, name):
        (repo / name).write_text(name + "\n")
        self.git("add", "--", name, cwd=repo)
        self.git("commit", "-qm", name, cwd=repo)
        return self.git("rev-parse", "HEAD", cwd=repo)

    def set_origin(self, url):
        self.git("remote", "set-url", "origin", url)
        # 通信先だけを一時bareリポジトリへ置き換え、Gitのpull自体は実行する。
        self.git("config", "--add", f"url.{self.remote.as_uri()}.insteadOf", url)

    def create_feature(self):
        self.git("switch", "-c", self.branch)
        self.feature_oid = self.commit(self.repo, "feature")
        self.git("push", "-u", "origin", self.branch)

    def merge_feature(self, squash=True):
        self.create_feature()
        self.git("fetch", "origin", self.branch, cwd=self.seed)
        if squash:
            self.git("merge", "--squash", "FETCH_HEAD", cwd=self.seed)
            self.git("commit", "-qm", "squash feature", cwd=self.seed)
        else:
            self.git("merge", "--no-ff", "-m", "merge feature", "FETCH_HEAD", cwd=self.seed)
        self.merge_oid = self.git("rev-parse", "HEAD", cwd=self.seed)
        self.git("push", "origin", "main", cwd=self.seed)
        self.git("push", "origin", "--delete", self.branch, cwd=self.seed)
        self.pr = {
            "state": "MERGED", "merged_at": "2026-01-01T00:00:00Z",
            "base": "main", "head": self.branch,
            "head_oid": self.feature_oid, "merge_oid": self.merge_oid,
        }
        self.set_pr()

    def set_pr(self, **fields):
        self.pr.update(fields)
        self.env["GPC_PR_FIELDS"] = "\t".join(self.pr.values())

    def run_gpc(self, *args, cwd=None):
        return subprocess.run(
            ["/bin/bash", str(SCRIPT), *args], cwd=cwd or self.repo,
            env=self.env, text=True, capture_output=True, check=False,
        )

    def gh_calls(self):
        if not self.gh_log.exists():
            return []
        return [json.loads(line) for line in self.gh_log.read_text().splitlines()]

    def local_refs(self):
        return self.git("for-each-ref", "--format=%(refname) %(objectname)", "refs/heads")

    def assert_refusal_preserves_refs(self, message):
        before = self.local_refs()
        branch = self.git("branch", "--show-current")
        result = self.run_gpc()
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn(message, result.stderr)
        self.assertEqual(self.local_refs(), before)
        self.assertEqual(self.git("branch", "--show-current"), branch)

    def test_base_branches_pull_without_github_or_branch_deletion(self):
        self.env["GPC_AUTH_STATUS"] = "1"
        self.git("branch", "keep-work", self.initial)
        for branch in ("main", "master", "develop"):
            with self.subTest(branch=branch):
                self.git("switch", "-C", branch, self.initial, cwd=self.seed)
                remote_oid = self.commit(self.seed, f"remote-{branch}")
                self.git("push", "origin", branch, cwd=self.seed)
                self.git("switch", "-C", branch, self.initial)
                result = self.run_gpc()
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(self.git("branch", "--show-current"), branch)
                self.assertEqual(self.git("rev-parse", "HEAD"), remote_oid)
                self.assertEqual(self.git("rev-parse", "keep-work"), self.initial)
                self.assertEqual(self.gh_calls(), [])

    def test_diverged_current_base_stops_without_github_or_reset(self):
        remote_oid = self.commit(self.seed, "remote-base")
        self.git("push", "origin", "main", cwd=self.seed)
        local_oid = self.commit(self.repo, "local-base")
        self.assertNotEqual(remote_oid, local_oid)
        self.assert_refusal_preserves_refs("Not possible to fast-forward")
        self.assertEqual(self.git("rev-parse", "HEAD"), local_oid)
        self.assertEqual(self.gh_calls(), [])

    def test_squash_merge_cleanup_and_repeat_on_base(self):
        self.merge_feature()
        self.git("branch", "keep-work", self.feature_oid)
        self.env["GH_REPO"] = "unrelated/repository"
        result = self.run_gpc()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.git("branch", "--show-current"), "main")
        self.assertEqual(self.git("rev-parse", "HEAD"), self.merge_oid)
        self.assertNotIn(f"refs/heads/{self.branch} ", self.local_refs())
        self.assertEqual(self.git("rev-parse", "keep-work"), self.feature_oid)
        calls = self.gh_calls()
        self.assertEqual(calls[0], ["auth", "status", "--hostname", "github.com"])
        self.assertEqual(calls[1][:5], [
            "pr", "view", self.branch, "--repo", "https://github.com/gpc-fixture/repository",
        ])
        self.assertIn("mergeCommit", calls[1][6])
        again = self.run_gpc()
        self.assertEqual(again.returncode, 0, again.stderr)
        self.assertEqual(self.gh_calls(), calls)

    def test_regular_merge_cleanup(self):
        self.merge_feature(squash=False)
        result = self.run_gpc()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.git("rev-parse", "HEAD"), self.merge_oid)
        self.assertNotIn(f"refs/heads/{self.branch} ", self.local_refs())

    def test_creates_missing_local_base_from_origin(self):
        self.merge_feature()
        self.git("branch", "-D", "main")
        result = self.run_gpc()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.git("branch", "--show-current"), "main")
        self.assertEqual(self.git("rev-parse", "HEAD"), self.merge_oid)

    def test_ssh_origin_is_pinned_for_pr_lookup(self):
        self.merge_feature()
        for url in (
            "git@github.com:gpc-fixture/repository.git",
            "ssh://git@github.com/gpc-fixture/repository.git",
        ):
            with self.subTest(url=url):
                self.set_origin(url)
                self.env["GPC_PR_STATUS"] = "1"
                self.assert_refusal_preserves_refs("no GitHub PR found")
                self.assertEqual(self.gh_calls()[-1][4], "https://github.com/gpc-fixture/repository")

    def test_dirty_files_are_rejected_even_if_untracked_files_are_hidden(self):
        self.git("config", "status.showUntrackedFiles", "no")
        for kind in ("untracked", "unstaged", "staged"):
            with self.subTest(kind=kind):
                path = self.repo / ("new-file" if kind == "untracked" else "initial")
                original = path.read_text() if path.exists() else None
                path.write_text("local change\n")
                if kind == "staged":
                    self.git("add", "--", path.name)
                self.assert_refusal_preserves_refs("worktree is dirty")
                self.assertEqual(path.read_text(), "local change\n")
                self.assertEqual(self.gh_calls(), [])
                if kind == "staged":
                    self.git("reset", "HEAD", "--", path.name)
                if original is None:
                    path.unlink()
                else:
                    path.write_text(original)

    def test_detached_head_is_rejected(self):
        self.git("switch", "--detach")
        self.assert_refusal_preserves_refs("detached HEAD")
        self.assertEqual(self.gh_calls(), [])

    def test_linked_worktree_is_rejected(self):
        linked = self.root / "linked"
        self.git("worktree", "add", "-b", "linked-work", str(linked), "main")
        before = self.local_refs()
        result = self.run_gpc(cwd=linked)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("primary worktree", result.stderr)
        self.assertEqual(self.local_refs(), before)
        self.assertEqual(self.gh_calls(), [])

    def test_base_in_another_worktree_does_not_delete_work_branch(self):
        self.merge_feature()
        self.git("worktree", "add", str(self.root / "base-worktree"), "main")
        self.assert_refusal_preserves_refs("already used by worktree")

    def test_unmerged_and_mismatched_prs_do_not_change_branches(self):
        self.merge_feature()
        original = self.pr.copy()
        for fields, message in (
            ({"state": "OPEN", "merged_at": ""}, "PR is not merged"),
            ({"state": "CLOSED", "merged_at": ""}, "PR is not merged"),
            ({"head": "feature/other"}, "PR head does not match"),
            ({"base": "release"}, "unsupported PR base branch"),
            ({"merge_oid": ""}, "PR commit OIDs are not available"),
        ):
            with self.subTest(fields=fields):
                self.pr = original.copy()
                self.set_pr(**fields)
                self.assert_refusal_preserves_refs(message)

    def test_extra_local_commits_are_preserved(self):
        self.merge_feature()
        local_oid = self.commit(self.repo, "unpublished")
        self.assert_refusal_preserves_refs("local head has diverged")
        self.assertEqual(self.git("rev-parse", "HEAD"), local_oid)

    def test_github_lookup_and_auth_failures_do_not_change_branches(self):
        self.merge_feature()
        for setting, message in (
            ({"GPC_AUTH_STATUS": "1"}, "gh is not authenticated"),
            ({"GPC_PR_STATUS": "1"}, "no GitHub PR found"),
        ):
            with self.subTest(setting=setting):
                self.env.update(GPC_AUTH_STATUS="0", GPC_PR_STATUS="0")
                self.env.update(setting)
                self.assert_refusal_preserves_refs(message)

    def test_missing_github_cli_does_not_change_branches(self):
        self.merge_feature()
        (self.bin / "gh").unlink()
        (self.bin / "git").symlink_to(GIT)
        self.env["PATH"] = str(self.bin)
        self.assert_refusal_preserves_refs("gh is not installed")
        self.assertEqual(self.gh_calls(), [])

    def test_non_github_origin_is_rejected_before_lookup(self):
        self.merge_feature()
        self.git("remote", "set-url", "origin", "https://example.invalid/repository.git")
        self.assert_refusal_preserves_refs("origin must point to a github.com repository")
        self.assertEqual(self.gh_calls(), [])

    def test_diverged_base_stops_without_deleting_work_branch(self):
        self.merge_feature()
        self.git("switch", "main")
        local_oid = self.commit(self.repo, "local-base")
        self.git("switch", self.branch)
        before = self.local_refs()
        result = self.run_gpc()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.git("branch", "--show-current"), "main")
        self.assertEqual(self.git("rev-parse", "HEAD"), local_oid)
        self.assertEqual(self.local_refs(), before)

    def test_pull_failure_keeps_work_branch(self):
        self.merge_feature()
        self.remote.rename(self.root / "unavailable.git")
        before = self.local_refs()
        result = self.run_gpc()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.git("branch", "--show-current"), "main")
        self.assertEqual(self.local_refs(), before)

    def test_branch_changed_during_pull_is_not_deleted(self):
        self.merge_feature()
        hook = self.repo / ".git/hooks/post-merge"
        hook.write_text(
            "#!/bin/sh\n"
            f"git update-ref refs/heads/{self.branch} HEAD\n"
        )
        hook.chmod(0o755)
        result = self.run_gpc()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("local branch changed during cleanup", result.stderr)
        self.assertEqual(self.git("rev-parse", self.branch), self.merge_oid)

    def test_missing_merge_commit_in_base_keeps_work_branch(self):
        self.merge_feature()
        self.set_pr(merge_oid=self.feature_oid)
        result = self.run_gpc()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("PR merge commit is not in the updated base", result.stderr)
        self.assertEqual(self.git("branch", "--show-current"), "main")
        self.assertEqual(self.git("rev-parse", self.branch), self.feature_oid)

    def test_help_invalid_arguments_and_non_repository(self):
        help_result = self.run_gpc("--help", cwd=self.root)
        self.assertEqual(help_result.returncode, 0)
        self.assertIn("Usage: gpc", help_result.stdout)
        invalid = self.run_gpc("unexpected")
        self.assertEqual(invalid.returncode, 2)
        self.assertIn("Usage: gpc", invalid.stderr)
        outside = self.run_gpc(cwd=self.root)
        self.assertNotEqual(outside.returncode, 0)
        self.assertIn("not in a Git worktree", outside.stderr)
        self.assertEqual(self.gh_calls(), [])


@unittest.skipUnless(CHEZMOI and ZSH, "chezmoi and zsh are required for installation tests")
class GpcInstallationTests(unittest.TestCase):
    def test_chezmoi_installs_executable_and_profile_exposes_command(self):
        """本物のchezmoiで一時HOMEに適用し、実行権限とPATHの優先順位を確認する。"""
        with tempfile.TemporaryDirectory(prefix="gpc install ") as temporary:
            root = Path(temporary)
            source = root / "source"
            destination = root / "home"
            bin_source = source / "dot_local/bin"
            bin_source.mkdir(parents=True)
            destination.mkdir()
            (bin_source / SCRIPT.name).write_bytes(SCRIPT.read_bytes())
            (source / "dot_zprofile").write_bytes(PROFILE.read_bytes())
            config = root / "chezmoi.toml"
            config.write_text("")
            env = {**os.environ, "HOME": str(destination)}
            result = subprocess.run(
                [
                    CHEZMOI, "--source", str(source), "--destination", str(destination),
                    "--config", str(config), "--cache", str(root / "cache"),
                    "--persistent-state", str(root / "state.boltdb"),
                    "apply", "--force", "--no-tty",
                ],
                env=env, capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            installed = destination / ".local/bin/gpc"
            self.assertEqual(installed.read_bytes(), SCRIPT.read_bytes())
            self.assertTrue(os.access(installed, os.X_OK))
            shell = subprocess.run(
                [
                    ZSH, "-fc", 'source "$1"; print -r -- "$PATH"; command -v gpc',
                    "zsh", str(destination / ".zprofile"),
                ],
                env=env, capture_output=True, text=True,
            )
            self.assertEqual(shell.returncode, 0, shell.stderr)
            path, command = shell.stdout.splitlines()
            self.assertEqual(path.split(os.pathsep)[:3], [
                "/opt/local/bin", "/opt/local/sbin", str(destination / ".local/bin"),
            ])
            self.assertEqual(command, str(installed))


if __name__ == "__main__":
    unittest.main()
