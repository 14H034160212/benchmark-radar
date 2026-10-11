# Release-date recovery for issue #588

**147 source records now have cited benchmark dates; all 3,228 catalog records remain.**

| Source | Missing release before | Missing release after | Recovered |
| --- | ---: | ---: | ---: |
| LLM Stats | 645 | 507 | 138 |
| Model reports | 26 | 18 | 8 |
| Artificial Analysis | 8 | 8 | 0 |
| OpenCompass Hub | 4 | 3 | 1 |
| Claire Radar | 0 | 0 | 0 |
| Total | 683 | 536 | 147 |

The issue's original 668-record count predates the current catalog. `baseline.json`
pins the software commit, rebuilt-index hash, and every initially missing source key.
`primary-source-review.json` records the primary URLs, introducing-paper titles,
first-version dates, checked source keys, and retrieved-response hashes. Facts live
in `data/catalog/benchmark_dates.yml`, not in generated index or shard files.

Use the public release announcement when available: HealthBench and its Hard and
Consensus subsets use May 12, 2025, rather than the May 13 arXiv submission.
Other additions explicitly use `paper_first_version`; their evidence is the paper
introducing the particular benchmark or original partition, not an arbitrary
bibliography citation. The second batch dates original partitions such as the VQAv2
test and validation splits, CoVoST 2 English-to-Chinese, the MMMU validation set; versioned, protocol-labelled, and variant
records without their own evidence remain undated. The third batch adds 25 more LLM Stats
records from 23 introducing papers verified by arXiv title identity and v1 submission
history, including the MultiPL-E HumanEval and MBPP translations named in that paper's
abstract. No score, metric, source identity, or runtime name join is added.

## Review corrections

WSC, RTE, and COPA predate SuperGLUE. Its introducing paper is retained only
as cited score-publication evidence for those three OpenCompass records; their
release dates remain unknown. The original review entry is preserved and an
append-only correction records the withdrawn release attribution. The baseline
recovered-key list now reconciles every batch to the current unresolved ledger.

## Still unresolved

**These verified batches are not completion of all date research.** The 536
remaining records are enumerated without truncation in `date-coverage.json`.
They need primary-source release evidence; inclusion in that list does not mean
that every possible external source has already been searched. Versioned, internal,
community, and ambiguously named entries must not inherit dates merely from a
similar benchmark name. In particular, this batch does not date BigCodeBench-Hard,
MathVerse-Mini, MathVista-Mini, or MBPP+ from a parent benchmark's introducing paper.

A numeric score-publication date and a model-release proxy are separate fallbacks,
not benchmark releases. The audit distinguishes them from records with neither.
Do not replace any of these gaps with a crawl date. Unknown measurements and all
source records remain in the catalog, detail shards, and offline release. Known
pre-2024 releases can move out of the Frontier timeline under its existing date
filter; that is not deletion from the corpus.

Regenerate the ledger after the normal catalog build:

```sh
benchmark-radar normalize-catalog
python scripts/audit_benchmark_date_coverage.py site/data/benchmark-index.json \
  --output assets/use-case-588/date-coverage.json
```

The frozen v0.11.0 paper inputs and figures are unchanged. Any later paper data
refresh needs a separately agreed cutoff; this software PR does not change Figure 6.
