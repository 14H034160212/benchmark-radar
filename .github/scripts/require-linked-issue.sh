#!/usr/bin/env bash
# Close a new pull request that does not link an existing issue.
#
# A PR with no issue is a change nobody asked for: it has no stated requirement
# to review against, and a claim on an issue can lapse while its PR still looks
# like finished work. The body is read from the event payload through an
# environment variable and is never interpolated into a command.
set -euo pipefail

: "${REPO:?}" "${AUTHOR:?}" "${NUMBER:?}"
BODY="${BODY:-}"
EXEMPT="${EXEMPT:-}"

author_lc="${AUTHOR,,}"
[[ "$author_lc" =~ ^[a-z0-9-]+(\[bot\])?$ ]] || { echo "unexpected login: $AUTHOR" >&2; exit 1; }

for name in $EXEMPT; do
  if [[ "${name,,}" == "$author_lc" ]]; then
    echo "$AUTHOR is exempt from the linked-issue rule"
    exit 0
  fi
done

# `Closes #N`, `Related to #N`, `owner/repo#N`, or an issue URL.
keywords='(close[sd]?|fix(e[sd])?|resolve[sd]?|relate[sd]? to|refs?|part of)'
refs="$(
  {
    grep -oiE "${keywords}:? +([A-Za-z0-9._-]+/[A-Za-z0-9._-]+)?#[0-9]+" <<<"$BODY" || true
    grep -oiE "github\.com/[A-Za-z0-9._-]+/[A-Za-z0-9._-]+/issues/[0-9]+" <<<"$BODY" || true
  } | sed -E 's|^.*github\.com/([^/]+/[^/]+)/issues/([0-9]+)$|\1#\2|; s|^[A-Za-z ]+:? +||'
)"

for ref in $refs; do
  number="${ref##*#}"
  repo="${ref%#*}"
  [[ -z "$repo" ]] && repo="$REPO"
  [[ "${repo,,}" == "${REPO,,}" ]] || continue
  # The issues API also returns pull requests, so tell them apart.
  kind="$(gh api "repos/$REPO/issues/$number" --jq 'if .pull_request then "pr" else "issue" end' 2>/dev/null || true)"
  if [[ "$kind" == "issue" ]]; then
    echo "linked issue #$number found"
    exit 0
  fi
done

message="Closing: this pull request does not link an existing issue. Every change starts from an issue, so reviewers have a stated requirement to check it against.

Open or pick an issue first. Then reopen this PR with \`Closes #N\` (or \`Related to #N\` if it is one step of a larger issue) in the description, and fill in the pull request template.

已关闭：此 PR 没有关联任何已有 issue。每个改动都应从 issue 出发，评审才有明确的要求可以对照。

请先创建或认领一个 issue，然后在 PR 描述里写 \`Closes #N\`（只完成一部分则写 \`Related to #N\`），按模板补全后再 reopen。"

gh pr close "$NUMBER" --repo "$REPO" --comment "$message"
