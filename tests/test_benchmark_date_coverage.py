"""Keep unknown releases distinct from dated score and model-release evidence."""

import importlib.util
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location(
    "audit_benchmark_date_coverage", Path("scripts/audit_benchmark_date_coverage.py")
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_coverage_preserves_every_source_record_and_distinguishes_date_evidence():
    rows = [
        {"key": "a:released", "released": "2024-01-01"},
        {
            "key": "a:score",
            "first_score_reported_at": "2024-01-02",
            "first_score_source_reference": {"date_precision": "score_publication"},
        },
        {
            "key": "b:proxy",
            "first_score_reported_at": "2023-01-01",
            "first_score_record": {"date_precision": "model_announcement"},
        },
        {"key": "b:unknown", "collected_at": "2026-10-11", "score_count": 0},
    ]
    for row in rows:
        row.update(name=row["key"], source=row["key"][0], source_url="https://example.org")
    result = MODULE.audit_date_coverage({"benchmarks": rows})
    assert result["records"] == 4
    assert result["released"] == 1
    assert result["missing_release"] == 3
    assert {row["key"]: row["fallback"] for row in result["unresolved"]} == {
        "a:score": "score_publication",
        "b:proxy": "model_release_proxy",
        "b:unknown": "undated",
    }
    assert sum(source["records"] for source in result["sources"].values()) == 4
    assert sum(source.get("missing_release", 0) for source in result["sources"].values()) == 3


def test_date_coverage_rejects_a_silent_duplicate_population():
    with pytest.raises(ValueError, match="duplicate source-record keys"):
        MODULE.audit_date_coverage({"benchmarks": [{"key": "a"}, {"key": "a"}]})


@pytest.mark.parametrize("precision", ["score_publication", "document_publication", "day"])
def test_actual_score_dates_are_not_reported_as_fully_undated(precision):
    row = {
        "key": "model-reports:reported-score",
        "name": "Reported score",
        "source": "model_reports",
        "source_url": "https://example.org/paper",
        "first_score_reported_at": "2024-01-02",
        "first_score_source_reference": {"date_precision": precision},
        "first_score_record": {"date_precision": "model_announcement"},
    }
    result = MODULE.audit_date_coverage({"benchmarks": [row]})
    assert result["missing_release"] == 1
    assert result["unresolved"][0]["fallback"] == "score_publication"
    assert result["sources"]["model_reports"]["score_publication"] == 1
    assert "undated" not in result["sources"]["model_reports"]
