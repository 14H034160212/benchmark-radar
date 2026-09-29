# Source-neutral snapshot normalization

## Goal

Remove source-specific decisions from catalog normalization. Snapshot configuration and source adapters should translate source data into one catalog input contract before the normalizer runs.

The change must preserve the current generated product:

- 3,198 catalog records and shards;
- all 1,914 Claire Radar records;
- all 12,929 score observations;
- source-owned scores and reviewed identity relationships;
- unchanged Claire `extra_json` objects and `record_sha256` values;
- legacy empty series where they are used for source-coverage auditing.

## Problem

The current normalizer contains two Claire-specific branches:

1. It omits empty score series by comparing the source name with `claire_radar`.
2. It reads Claire's private `releaseDates`, `firstPublicAt`, and `paperV1At` fields.

These branches make a general catalog stage responsible for source policy and source schema. A new scoreless source or a source with equivalent date metadata would require another normalizer edit.

## Design

### Snapshot policy

Every registered snapshot declares a score-series policy:

```yaml
score_series_policy: preserve_empty
```

or:

```yaml
score_series_policy: observed_only
```

`preserve_empty` emits a series even when it has no observations. Existing sources use this policy to preserve coverage-audit behavior.

`observed_only` emits a series only when at least one observation exists. The Claire snapshot uses this policy because it contains no score data.

The snapshot loader validates the value and rejects missing or unknown policies. The catalog normalizer receives the validated policy and applies it without inspecting the source name.

### Source adapters

A snapshot can name a catalog adapter:

```yaml
catalog_adapter: claire_radar_v1
```

The adapter runs after the source CSV row is parsed and before `_source_record` receives it. Its output follows the common row contract used by catalog normalization.

The Claire adapter translates its preserved source object into these common fields:

- `released`;
- `released_basis`;
- `released_source_url`;
- `publication_dates`.

`publication_dates` is a list of normalized date facts. Each fact has a date, basis, source URL, and optional note. The common normalizer validates and copies these facts; it does not parse source-private date keys.

The adapter retains the complete Claire source object as source metadata. It does not mutate `extra_json`, rewrite the CSV, or change `record_sha256`.

Snapshots without an adapter use the identity adapter, which returns the parsed row unchanged. Unknown adapter names fail during snapshot loading.

### Date evidence

The Claire adapter reads the six records that contain `releaseDates` in their preserved source objects. It maps:

- `firstPublicAt` to the common `released` fact with basis `first_public`;
- `paperV1At` to a `publication_dates` fact with basis `paper_first_version`.

Reviewed first-public evidence remains keyed by exact source record ID in snapshot configuration. The adapter uses it when present. It never matches evidence by benchmark name.

When a source object contains a date but no reviewed first-public URL, the adapter retains the date and uses the original record evidence defined by the common provenance contract. It does not imply that the imported date received an independent review.

Paper evidence comes from the record's paper URL when available. A missing evidence URL does not cause the date fact to be invented or discarded; the common representation records only evidence that exists.

### Source metadata

The normalizer stores source metadata under the actual source key:

```python
{"source_metadata": {source: source_metadata}}
```

It does not name Claire directly. Adapters decide which source metadata to return, while the common normalizer only preserves it.

## Module boundaries

### `leaderboard_snapshots.py`

- Parse and validate `score_series_policy`.
- Parse and validate `catalog_adapter`.
- Preserve adapter options as configuration data.
- Reject unsupported policies or adapters before normalization.

### `catalog_snapshot_adapters.py`

- Own the adapter registry.
- Provide the identity adapter.
- Translate Claire's private schema into the common row contract.
- Validate adapter-specific options that cannot be validated generically.

### `catalog.py`

- Consume only the common row contract.
- Apply the declared score-series policy.
- Validate normalized date facts.
- Preserve returned source metadata under the source key.
- Contain no Claire date-schema branches or Claire score-series branches.

`catalog.py` may retain the existing snapshot-to-source registration until that separate concern has a source-neutral replacement. This refactor does not broaden into redesigning source identifiers.

## Validation and failure behavior

Normalization fails visibly for:

- a missing or unsupported score-series policy;
- an unsupported adapter name;
- malformed adapter options;
- an invalid normalized date or date basis;
- malformed `publication_dates` output.

The adapter must not silently infer relationships, evidence, or dates from a benchmark name.

## Tests

Tests are written before implementation and must fail for the missing general behavior.

1. A synthetic source using `observed_only` emits no empty series.
2. A synthetic source using `preserve_empty` retains an empty series.
3. Missing and unknown policies fail during snapshot loading.
4. An unknown adapter fails during snapshot loading.
5. The common normalizer accepts normalized first-public and paper-version facts without source knowledge.
6. The Claire adapter converts all six source objects with `releaseDates`.
7. Reviewed evidence is selected by exact source ID.
8. Claire `extra_json` and `record_sha256` remain byte-for-byte unchanged.
9. A structural test prevents the removed private schema keys and source-specific score condition from returning to `catalog.py`.
10. Generated-product tests retain 3,198 records, 1,914 Claire records, 3,198 shards, and 12,929 observations.
11. Search, detail pages, provenance, reviewed siblings, and source-partitioned scores retain their current behavior.

## Delivery sequence

1. Add failing policy, adapter, normalized-date, and architecture-boundary tests.
2. Add policy and adapter configuration validation.
3. Add the adapter registry and Claire adapter.
4. Simplify catalog normalization to consume the common contract.
5. Run focused tests and inspect generated records.
6. Run the documented six-stage CI in a clean checkout.
7. Push the new commits and re-review the new PR head. Do not merge the PR.

## Non-goals

- Merging source records across reviewed identity links.
- Moving scores between sources.
- Changing benchmark counts or taxonomy.
- Replacing the existing snapshot-to-source ID registration.
- Introducing a general SSRF policy for static outbound links.
- Rewriting all Claire CSV rows to materialize six normalized date records.
