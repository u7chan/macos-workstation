#!/usr/bin/env bash
set -euo pipefail

# Source and revision policy for the installed skill package.
REPOSITORY="github.com/u7chan/agent-harness"
BRANCH="main"

echo "==> resolving agent skills: ${REPOSITORY} (${BRANCH})"
REVISION="$(git ls-remote --exit-code "https://${REPOSITORY}.git" "refs/heads/${BRANCH}" | cut -f1)"
if [[ ! "$REVISION" =~ ^[0-9a-f]{40}$ ]]; then
  echo "ERROR: could not resolve a single commit for agent skills" >&2
  exit 1
fi

# Install through pi, never from a development checkout or a skill-directory symlink.
echo "==> installing agent skills at ${REVISION}"
pi install "git:${REPOSITORY}@${REVISION}"

echo "==> next: /reload or restart every running pi session before using the updated skills"
