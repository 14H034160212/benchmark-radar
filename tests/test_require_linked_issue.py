"""A pull request that links no existing issue is closed, unless its author is exempt."""

import os
import stat
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(".github/scripts/require-linked-issue.sh").resolve()
EXEMPT = "ktwu01 junjiezhou1122 14H034160212 Claire1217"


def run_gate(tmp_path, *, body, author="someone", kinds=None, exempt=EXEMPT):
    # A fake `gh` answers the issues API from `kinds` and records every close.
    kinds = kinds or {}
    log = tmp_path / "calls.log"
    fake = tmp_path / "gh"
    cases = "".join(f'  *"issues/{n}"*) echo {kind};;\n' for n, kind in kinds.items())
    fake.write_text(
        "#!/usr/bin/env bash\n"
        'echo "$*" >> "$CALLS"\n'
        'if [[ "$1" == api ]]; then\n'
        '  case "$*" in\n'
        f"{cases}"
        "  *) exit 1;;\n"
        "  esac\n"
        "fi\n"
    )
    fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
    env = {
        **os.environ,
        "PATH": f"{tmp_path}:{os.environ['PATH']}",
        "CALLS": str(log),
        "REPO": "ktwu01/benchmark-radar",
        "AUTHOR": author,
        "NUMBER": "900",
        "BODY": body,
        "EXEMPT": exempt,
    }
    result = subprocess.run([str(SCRIPT)], env=env, capture_output=True, text=True)
    calls = log.read_text().splitlines() if log.exists() else []
    return result, [line for line in calls if line.startswith("pr close")]


@pytest.mark.parametrize(
    "body",
    [
        "Closes #411",
        "fixes #411 and more",
        "Related to #411",
        "Relates to: #411",
        "Part of ktwu01/benchmark-radar#411",
        "See https://github.com/ktwu01/benchmark-radar/issues/411",
        "Why\n\nCloses #411\n\n## Before and after",
    ],
)
def test_a_link_to_an_existing_issue_is_accepted(tmp_path, body):
    result, closes = run_gate(tmp_path, body=body, kinds={411: "issue"})
    assert result.returncode == 0
    assert closes == []


@pytest.mark.parametrize(
    "body",
    [
        "",
        "Condense leaderboard headings",
        "see #411",  # a bare mention is not a link
        "Closes #999",  # the issue does not exist
    ],
)
def test_a_pr_without_an_existing_issue_is_closed(tmp_path, body):
    result, closes = run_gate(tmp_path, body=body, kinds={411: "issue"} if "411" in body else {})
    assert result.returncode == 0
    assert len(closes) == 1


def test_a_link_to_a_pull_request_is_not_an_issue(tmp_path):
    result, closes = run_gate(tmp_path, body="Closes #411", kinds={411: "pr"})
    assert result.returncode == 0
    assert len(closes) == 1


def test_a_link_to_another_repository_does_not_count(tmp_path):
    result, closes = run_gate(tmp_path, body="Closes someone/else#411", kinds={411: "issue"})
    assert result.returncode == 0
    assert len(closes) == 1


@pytest.mark.parametrize("author", ["ktwu01", "KTWU01", "14H034160212", "claire1217"])
def test_exempt_authors_are_never_closed(tmp_path, author):
    result, closes = run_gate(tmp_path, body="", author=author)
    assert result.returncode == 0
    assert closes == []


def test_a_login_with_shell_syntax_is_refused(tmp_path):
    result, closes = run_gate(tmp_path, body="", author='x"; echo pwned')
    assert result.returncode == 1
    assert closes == []
