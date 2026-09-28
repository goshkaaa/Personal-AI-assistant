#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PATTERN='([0-9]{8,12}:[A-Za-z0-9_-]{30,}|sk-[A-Za-z0-9_-]{20,}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{30,}|xox[baprs]-[A-Za-z0-9-]{20,}|-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----)'

cd "$ROOT_DIR"

tracked_matches="$(git grep -I -l -E "$PATTERN" -- . ':!hermes/hermes-agent' || true)"
untracked_files=()
while IFS= read -r -d '' path; do
  untracked_files+=("$path")
done < <(git ls-files --others --exclude-standard -z)
untracked_matches=""
if (( ${#untracked_files[@]} > 0 )); then
  untracked_matches="$(grep -I -l -E "$PATTERN" -- "${untracked_files[@]}" || true)"
fi
matches="${tracked_matches}${tracked_matches:+$'\n'}${untracked_matches}"
if [[ -n "$matches" ]]; then
  printf 'Potential secret signatures in repository files:\n%s\n' "$matches" >&2
  exit 1
fi

history_matches=""
while IFS= read -r commit; do
  commit_matches="$(
    git grep -I -l -E "$PATTERN" "$commit" -- . ':!hermes/hermes-agent' 2>/dev/null || true
  )"
  if [[ -n "$commit_matches" ]]; then
    history_matches+="${commit_matches}"$'\n'
  fi
done < <(git rev-list --all)

if [[ -n "$history_matches" ]]; then
  printf 'Potential secret signatures in Git history (filenames only):\n%s' \
    "$history_matches" >&2
  exit 1
fi

non_private_metadata_emails="$(
  git log --all --format='%ae%n%ce' \
    | sort -u \
    | grep -Ev '^[A-Za-z0-9._%+-]+@users\.noreply\.github\.com$' \
    || true
)"
if [[ -n "$non_private_metadata_emails" ]]; then
  printf '%s\n' \
    'Git history contains author or committer emails outside the no-reply domain.' >&2
  exit 1
fi

sensitive_files="$(
  git ls-files --cached --others --exclude-standard \
    | grep -E '(^|/)(\.env$|[^/]*(credentials|token|session|private[-_]?key)[^/]*$)|\.(pem|p12|pfx|key|sqlite|sqlite3|db)$' \
    | grep -Ev '(^|/)\.env\.example$' \
    || true
)"
if [[ -n "$sensitive_files" ]]; then
  printf 'Sensitive-looking files are present in the repository worktree:\n%s\n' \
    "$sensitive_files" >&2
  exit 1
fi

HERMES_DIR="$ROOT_DIR/hermes/hermes-agent"
if [[ -e "$HERMES_DIR/.git" ]]; then
  submodule_changes="$(git -C "$HERMES_DIR" status --porcelain --untracked-files=all)"
  if [[ -n "$submodule_changes" ]]; then
    printf '%s\n' \
      'Hermes submodule has local tracked or untracked files. Review them before push:' \
      "$submodule_changes" >&2
    exit 1
  fi

  for private_file in .env config.yaml config.yml; do
    if [[ -f "$HERMES_DIR/$private_file" ]]; then
      printf 'Private Hermes file is inside the submodule: %s\n' "$private_file" >&2
      exit 1
    fi
  done
fi

printf '%s\n' \
  'Secret scan passed: repository history is clean and the Hermes submodule has no local files.'
