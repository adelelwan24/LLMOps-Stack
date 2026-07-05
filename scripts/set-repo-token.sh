#!/usr/bin/env bash
# Set GitHub credentials for THIS repo only (does not affect global git config).
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
USERNAME="${1:-adelelwan24}"
TOKEN="${2:-}"

if [[ -z "$TOKEN" ]]; then
  echo "Usage: $0 [github_username] <personal_access_token>"
  echo "Example: $0 adelelwan24 github_pat_xxxx"
  exit 1
fi

cd "$REPO_ROOT"

printf 'https://%s:%s@github.com/adelelwan24/LLMOps-Stack.git\n' "$USERNAME" "$TOKEN" > .git/credentials
chmod 600 .git/credentials

git config --local --unset-all credential.helper 2>/dev/null || true
git config --local credential.useHttpPath true
git config --local credential.https://github.com/adelelwan24/LLMOps-Stack.git.helper 'store --file=.git/credentials'
git remote set-url origin "https://${USERNAME}:${TOKEN}@github.com/adelelwan24/LLMOps-Stack.git"

echo "Repo-only credentials configured for adelelwan24/LLMOps-Stack."
echo "Global git credentials are not modified."
