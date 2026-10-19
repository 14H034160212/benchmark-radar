# Maintainer review

Answer these questions, in order, before you merge a contributor PR. Stop at the
first "no" and request changes. These checks add to the rules in
[`CONTRIBUTING.md`](CONTRIBUTING.md#1-what-we-merge). They do not replace them.

## Review depth

Size the review to the change. For a PR under about 20 changed lines that is not
docs-only, first read the before and after screenshots and the issue table in
the description. If you cannot say in one sentence what a reader sees
differently, request changes. Do not run the six CI steps for it yet.

## 1. Did the human contributor answer the four questions?

- The contributor answers the four questions in
  [`CONTRIBUTING.md`](CONTRIBUTING.md#before-you-start-a-pr) themselves.
  Answers written by their agent do not count, even on the contributor's
  instruction.
- For agent-assisted work, check for the `330226 <model-id>` comment.
- Maintainer-authored PRs are exempt. A maintainer may waive the questions for
  a fix the maintainer asked for, such as one that closes a maintainer-filed
  issue. State the waiver and its reason in the merge comment, so it does not
  become a precedent.

## 2. Is this the least resource-intensive way to get the outcome?

Each cost below recurs for every visitor, every CI run, or every day. Name the
cost in numbers. Then check whether an existing file, function, or workflow step
already does the job.

- **Visitor bytes.** Measure each new or changed page and data file, raw and
  gzipped. Prefer a page that reads a file the site already loads, such as
  `/data/benchmark-index.json`. A returning visitor then downloads nothing new
  while that file is unchanged. Pages has a 100 GB/month soft limit; see
  [`docs/agent-gotchas.md`](docs/agent-gotchas.md#github-and-hosting).
- **Stored data.** A new field in a daily snapshot is stored every day, forever.
  See [Technical burden without a real failure](CONTRIBUTING.md#2-what-we-dont-merge).
- **Code to maintain.** A second copy of existing logic, such as a browser copy
  of `QueryService` ranking, must be updated by hand. Reuse the existing code,
  or keep the simpler behavior.
- **CI and workflow steps.** A new CI step runs on every PR push. A new daily-job
  step runs every day. Put site build work in the Pages deploy, which already
  builds the catalog.

A heavier page or a longer menu slows both readers named in
[`AGENTS.md`](AGENTS.md): the newcomer and the benchmark expert.

## 3. If it is a bug fix, does it link a failure that already happened?

The failure must appear in a committed snapshot, a CI run, the live site, or a
user report. A review-bot comment or a possible case is not a failure.

## 4. Does it keep the full corpus?

Every benchmark-facing surface covers all records across all sources. Missing
measurements never remove a record. Benchmark Frontier and its linked score
ranking exclude records without a numeric reported score, and count them. See
[`principle.md`](principle.md).

## 5. Is the daily snapshot safe?

You can rerun a failed deploy. You cannot recover a missed snapshot. Reject a
change that adds a step that can fail before the daily job writes the snapshot.

## 6. Does the description disclose every behavior change?

Check the diff for changes to scores, rankings, counts, or output formats that
the description does not mention. Ask the contributor to state them, or state
them in the merge comment.

## 7. Does the current head pass on current `main`?

A "verified head" in the description goes stale with each new commit. Merge the
current head onto the latest `main` in a clean worktree with its own venv. Run
the full CI sequence from [`AGENTS.md`](AGENTS.md). When the user asks you to
merge, run `gh pr merge --merge --admin --match-head-commit <sha>`. A push after
your check then cannot slip in. Never squash.

## 8. Does it do what the linked issue asks, and is the result easier to read?

Open the issue and the PR description side by side. List each thing the issue
asks for. Mark each as done or not done in the diff, then check the before and
after screenshots at one viewport.

- Request changes when the PR does a small part of the issue but says `Closes`.
  It should say `Related to`, and the rest stays open.
- Request changes when the after is harder to read than the before. Removing a
  line that tells the reader what a chart answers, or renaming a plain heading
  to a vague one, fails this check even when CI is green.
- A PR with no link to an existing issue is closed by automation. Do not review
  it. Maintainers and the core team are exempt.

A green CI run says the change does not break the build. It does not say the
change is worth merging.
