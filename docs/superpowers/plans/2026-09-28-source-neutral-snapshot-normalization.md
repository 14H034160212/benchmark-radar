# Source-Neutral Snapshot Normalization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove Claire-specific date and score-series behavior from catalog normalization by translating source rows through validated adapters and applying registry-declared series policies.

**Architecture:** `leaderboard_snapshots.py` validates declarative snapshot policy and adapter configuration. A new `catalog_snapshot_adapters.py` module translates parsed source rows into a common catalog-row contract. `catalog.py` consumes only that contract and never branches on Claire or reads Claire-private date keys.

**Tech Stack:** Python 3, PyYAML, pytest, Ruff, committed CSV/YAML snapshot data.

**Spec:** `docs/superpowers/specs/2026-09-28-source-neutral-snapshot-normalization-design.md`

## Global Constraints

- Preserve 3,198 catalog records and shards.
- Preserve all 1,914 Claire Radar records and all 12,929 score observations.
- Do not modify Claire `extra_json` objects or `record_sha256` values.
- Scores remain attached to their original source records and partitioned by source.
- Legacy snapshots retain empty score series; Claire emits series only for observations.
- Reviewed date evidence is selected by exact source ID, never benchmark name.
- `catalog.py` must not interpret Claire-private date keys or branch on Claire for score behavior.
- Do not merge identity-linked source records or change taxonomy.

---

### Task 1: Lock the source-neutral contracts with failing tests

**Files:**
- Modify: `tests/test_catalog.py`
- Modify: `tests/test_claire_radar_snapshot.py`

**Interfaces:**
- Consumes: existing `load_snapshots()` and `normalize_snapshot()` entry points.
- Produces: regression requirements for `score_series_policy`, `catalog_adapter`, normalized dates, generic source metadata, and the architecture boundary.

- [ ] Add registry fixture support for `score_series_policy` and tests showing missing/unknown policies fail.
- [ ] Add tests showing unknown adapters fail.
- [ ] Add synthetic snapshot tests showing `observed_only` omits empty series and `preserve_empty` retains them without checking a source name.
- [ ] Add Claire tests requiring adapter configuration and all six `releaseDates` objects to be translated.
- [ ] Add a structural test proving `catalog.py` does not contain `releaseDates`, `firstPublicAt`, `paperV1At`, or a Claire-specific score condition.
- [ ] Run the focused tests and record the expected failures before production edits.

Run:

```bash
uv run --frozen --extra dev pytest -q \
  tests/test_catalog.py \
  tests/test_claire_radar_snapshot.py
```

Expected: failures for missing policy validation, missing adapter validation/translation, and source-specific normalizer code.

- [ ] Commit the failing tests.

```bash
git add tests/test_catalog.py tests/test_claire_radar_snapshot.py
git commit -m "test: require source-neutral snapshot normalization"
```

### Task 2: Validate snapshot policy and adapter configuration

**Files:**
- Create: `src/benchmark_radar/catalog_snapshot_adapters.py`
- Modify: `src/benchmark_radar/leaderboard_snapshots.py`
- Modify: `data/leaderboard_snapshots.yml`

**Interfaces:**
- Produces: `SCORE_SERIES_POLICIES`, `CATALOG_ADAPTERS`, and validated snapshot fields `score_series_policy`, `catalog_adapter`, and `adapter_options`.
- `score_series_policy` is exactly `preserve_empty` or `observed_only`.
- `catalog_adapter` defaults to `identity` and must be registered.

- [ ] Implement the adapter registry names and snapshot configuration validators.
- [ ] Require every registry entry to declare `score_series_policy`.
- [ ] Set existing snapshots to `preserve_empty` and Claire to `observed_only`.
- [ ] Move Claire first-public evidence under `adapter_options.first_public_evidence` and declare `catalog_adapter: claire_radar_v1`.
- [ ] Run loader-focused tests until policy and adapter validation pass.

Run:

```bash
uv run --frozen --extra dev pytest -q \
  tests/test_catalog.py -k 'loader or policy or adapter' \
  tests/test_claire_radar_snapshot.py -k 'registered_snapshot'
```

Expected: PASS for registry validation; date translation tests remain red until Task 3.

### Task 3: Translate rows through the adapter boundary

**Files:**
- Modify: `src/benchmark_radar/catalog_snapshot_adapters.py`
- Modify: `src/benchmark_radar/catalog.py`
- Modify: `tests/test_catalog.py`
- Modify: `tests/test_claire_radar_snapshot.py`

**Interfaces:**
- Produces: `adapt_catalog_row(row, *, adapter, adapter_options, snapshot_id) -> dict[str, Any]`.
- Common adapted fields are `source_metadata`, `released`, `released_basis`, `released_source_url`, and `publication_dates`.
- Raises `CatalogSnapshotAdapterError` for malformed source objects or adapter options.

- [ ] Implement the identity adapter, including generic `extra_json` preservation as `source_metadata`.
- [ ] Implement `claire_radar_v1`, translating exact-ID first-public evidence and paper-version dates.
- [ ] Make `normalize_snapshot()` adapt each benchmark row before record/series generation.
- [ ] Simplify `_source_record()` to consume and validate only common fields.
- [ ] Store source metadata under `{source: metadata}`.
- [ ] Apply `score_series_policy` instead of checking the source name.
- [ ] Run all focused catalog and Claire tests until green.

Run:

```bash
uv run --frozen --extra dev pytest -q \
  tests/test_catalog.py \
  tests/test_claire_radar_snapshot.py \
  tests/test_artificial_analysis_snapshot.py
```

Expected: PASS.

- [ ] Commit the implementation.

```bash
git add data/leaderboard_snapshots.yml \
  src/benchmark_radar/catalog_snapshot_adapters.py \
  src/benchmark_radar/leaderboard_snapshots.py \
  src/benchmark_radar/catalog.py \
  tests/test_catalog.py tests/test_claire_radar_snapshot.py
git commit -m "refactor: normalize snapshots through source adapters"
```

### Task 4: Verify generated products and full corpus invariants

**Files:**
- Modify only if a behavior regression is found in code already in scope.

**Interfaces:**
- Consumes: generated catalog, shards, index, search, detail pages, and release artifacts.
- Produces: evidence that the refactor changed architecture without changing the published corpus.

- [ ] Run focused generation commands and assert 3,198 records, 1,914 Claire records, 3,198 shards, and 12,929 observations.
- [ ] Verify reviewed GAUGE/ELBench siblings, Claire empty score groups, provenance, date evidence, and source-owned scores.
- [ ] Run `git diff --check` and confirm the Claire CSV checksum remains `cb15e3e585c4234517f4dfe6f93235980b3acf762f093739caea4338e77f166d`.
- [ ] Run the documented six-stage CI in a clean detached worktree:

```bash
ruff check .
ruff format --check .
benchmark-radar normalize-catalog
benchmark-radar classify
benchmark-radar build-data-release
pytest -q
```

Expected: every command exits zero.

### Task 5: Review and update PR #693

**Files:**
- No source changes unless review identifies a bounded defect.

- [ ] Run `no-comments` and `deslop` checks required by the project workflow.
- [ ] Inspect the final diff and commit history.
- [ ] Push commits to `origin/data/import-claire-radar-corpus`.
- [ ] Wait for GitHub CI on the new head.
- [ ] Re-review the new head and document how registry policy and adapters removed the two source-specific branches.
- [ ] Do not merge the PR.
