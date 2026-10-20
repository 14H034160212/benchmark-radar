"""The Models matrix merged from benchmark-radar.com's Model Evals (#420)."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from benchmark_radar.app_seeds import _model_value_text, _models_seed
from benchmark_radar.model_scores import (
    average_value,
    build_model_scores,
    capability_group,
    model_family,
    order_models,
    score_scale,
    shared_average,
)

ROOT = Path(__file__).resolve().parents[1]
PERCENT = {"percent": True, "direction": "higher_is_better", "unit": "%"}


def test_models_behaviour_runs_against_the_production_functions():
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    subprocess.run([node, "tests/models_harness.mjs"], check=True, timeout=60, cwd=ROOT)


# --- The shared-benchmark average's three rules -----------------------------------


def test_rule_1_only_benchmarks_every_model_shares_count():
    # B also reported an easy benchmark; it must not lift B above A.
    benchmarks = {"hard": PERCENT, "easy": PERCENT}
    means, shared = shared_average([{"hard": 40.0}, {"hard": 40.0, "easy": 99.0}], benchmarks)
    assert means == [40.0, 40.0]
    assert shared == ["hard"]


def test_rule_2_scores_count_on_their_series_direction_and_scale():
    # A fraction is put on its display scale by the series' multiplier.
    assert score_scale({"score_summary": {"display_multiplier": 100, "raw_max": 0.6}}) == (
        100,
        True,
    )
    assert score_scale({"score_summary": {"display_multiplier": 1, "unit": "percent"}}) == (1, True)
    assert score_scale({"declared_max": 100.0, "score_summary": {"display_multiplier": 1}}) == (
        1,
        True,
    )
    # Elo, dollars and points out of 42 are not on a 0-100 scale.
    elo = {"declared_max": 3000.0, "score_summary": {"display_multiplier": 1, "raw_max": 1577}}
    assert score_scale(elo) == (1, False)
    assert (
        score_scale({"declared_max": 42.0, "score_summary": {"display_multiplier": 1}})[1] is False
    )
    # A reported value outside 0-100 contradicts a percent declaration.
    contradicted = {"score_summary": {"display_multiplier": 1, "unit": "percent", "raw_max": 140}}
    assert score_scale(contradicted)[1] is False
    benchmarks = {
        "hard": PERCENT,
        "elo": {"percent": False, "direction": "higher_is_better", "unit": "Elo"},
        "error": {"percent": True, "direction": "lower_is_better", "unit": "%"},
    }
    means, shared = shared_average(
        [
            {"hard": 60.0, "elo": 1577.0, "error": 10.0},
            {"hard": 80.0, "elo": 1200.0, "error": 30.0},
        ],
        benchmarks,
    )
    assert shared == ["error", "hard"]  # Elo left out
    assert means == [75.0, 75.0]  # lower-is-better flipped: (90 + 60) / 2, (70 + 80) / 2
    assert average_value(10.0, benchmarks["error"]) == 90.0
    assert average_value(1577.0, benchmarks["elo"]) is None
    assert average_value(5.0, {"percent": True, "direction": None}) is None


def test_rule_3_the_count_of_shared_benchmarks_is_returned_and_printed(tmp_path):
    means, shared = shared_average([{"a": 1.0}, {"b": 2.0}], {"a": PERCENT, "b": PERCENT})
    assert (means, shared) == ([None, None], [])
    payload, records = _fixture(tmp_path)
    _, _, matrix, _ = _models_seed(records, payload).values()
    assert "over the 1 benchmarks all 2 models share, 0–100" in matrix


def test_averages_round_half_up_like_the_page():
    assert shared_average([{"a": 0.25}], {"a": PERCENT})[0] == [0.3]


# --- Data -------------------------------------------------------------------------


def _shard(key, rows, *, multiplier=1, unit="percent", direction="higher_is_better", **series):
    return {
        "record": {"key": key},
        "scores_by_source": {
            "llm_stats": {
                "series": {
                    "direction": direction,
                    "score_summary": {"display_multiplier": multiplier, "unit": unit},
                    **series,
                },
                "rows": [
                    {
                        "obs_id": f"{key}:{index}",
                        "model_name": model,
                        "organization": org,
                        "value": value,
                        "reported_date": date,
                    }
                    for index, (model, org, value, date) in enumerate(rows)
                ],
            }
        },
    }


def _fixture(tmp_path):
    shards = tmp_path / "benchmarks"
    shards.mkdir()
    for name, shard in {
        "aime": _shard(
            "llm-stats:aime",
            [
                ("Acme-1", "Acme", 0.5, "2026-01-01"),
                ("Acme-1", "acme", 0.7, "2026-02-01"),
                ("Beta <1>", "Beta", 0.9, "2026-03-01"),
            ],
            multiplier=100,
            unit=None,
        ),
        "arena": _shard(
            "llm-stats:arena",
            [("Acme-1", "Acme", 1500.0, "2026-01-01"), ("Beta <1>", "Beta", 1400.0, "2026-01-01")],
            unit="elo",
            declared_max=3000.0,
        ),
        "arc": _shard("model-reports:arc", [("Beta <1>", "Beta", 12.0, "2026-04-01")]),
    }.items():
        (shards / f"{name}.json").write_text(json.dumps(shard))
    records = [
        {
            "key": "llm-stats:aime",
            "slug": "llm-stats-aime",
            "name": "AIME",
            "source": "llm_stats",
            "categories": ["math"],
            "scored_models": [{"name": "Acme-1"}],
        },
        {
            "key": "llm-stats:arena",
            "slug": "llm-stats-arena",
            "name": "Arena",
            "source": "llm_stats",
            "categories": [],
            "scored_models": [{"name": "Acme-1"}],
        },
        {
            "key": "model-reports:arc",
            "slug": "arc",
            "name": "AIME",
            "source": "model_reports",
            "categories": ["reasoning"],
            "scored_models": [{"name": "Beta <1>"}],
        },
        {"key": "claire-radar:x", "slug": "x", "name": "X", "source": "claire_radar"},
    ]
    return build_model_scores(shards), records


def test_build_keeps_each_models_best_score_per_record_on_its_display_scale(tmp_path):
    payload, _ = _fixture(tmp_path)
    keys = [benchmark["key"] for benchmark in payload["benchmarks"]]
    by_model = {
        model["model"]: {keys[score[0]]: score[1:] for score in model["scores"]}
        for model in payload["models"]
    }
    # Case-only organization spellings are one registry model; its best of two
    # settings is kept with the row count, on the display scale.
    assert by_model["Acme-1"]["llm-stats:aime"] == [70.0, 2]
    assert by_model["Acme-1"]["llm-stats:arena"] == [1500.0]
    arena = payload["benchmarks"][keys.index("llm-stats:arena")]
    assert (arena["percent"], arena["unit"]) == (False, "Elo")
    assert next(m for m in payload["models"] if m["model"] == "Beta <1>")["date"] == "2026-04-01"


def test_lower_is_better_keeps_the_lowest_score(tmp_path):
    shards = tmp_path / "benchmarks"
    shards.mkdir()
    rows = [("M", "Lab", 9.0, "2026-01-01"), ("M", "Lab", 4.0, "2026-01-02")]
    shard = _shard("k:err", rows, direction="lower_is_better")
    (shards / "err.json").write_text(json.dumps(shard))
    payload = build_model_scores(shards)
    assert payload["models"][0]["scores"] == [[0, 4.0, 2]]


# --- Mirrors of app.js ---------------------------------------------------------------


def test_families_groups_and_order_match_the_page():
    assert model_family("Claude Opus 5 (Adaptive Reasoning, High Effort)") == (
        "Claude Opus 5",
        "Adaptive Reasoning, High Effort",
    )
    assert model_family("GPT-5") == ("GPT-5", "")
    assert capability_group({"categories": ["math", "reasoning"]}) == "Mathematics"
    assert capability_group({"library_direction": {"categories": ["agentic-coding"]}}) == "Coding"
    assert capability_group({"categories": ["safety"]}) == "Other"
    family = [
        {"organization": "A", "model": "M (high)", "date": "2026-02-01", "cells": {"x": 1}},
        {"organization": "A", "model": "M", "date": "2026-01-01", "cells": {"x": 1}},
        {"organization": "A", "model": "N", "date": "2026-01-15", "cells": {"x": 1, "y": 1}},
        {"organization": "A", "model": "Old", "date": None, "cells": {"x": 1}},
    ]
    newest = order_models(family, "newest")
    assert [model["model"] for model in newest] == ["M", "M (high)", "N", "Old"]
    assert [model["model"] for model in order_models(family)] == ["N", "M", "M (high)", "Old"]
    assert _model_value_text(74.66, PERCENT) == "74.7%"
    assert _model_value_text(70.0, PERCENT) == "70%"
    assert _model_value_text(1577.0, {"unit": "Elo"}) == "1,577 Elo"
    assert _model_value_text(0.4763, {}) == "0.476"


# --- Seed -------------------------------------------------------------------------------


def test_seed_is_the_first_page_of_the_matrix(tmp_path):
    payload, records = _fixture(tmp_path)
    nav, page, matrix, status = _models_seed(records, payload).values()
    assert '<a class="library-direction" href="/models/?lab=Acme">' in nav
    assert "1–2 of 2 models, most benchmarks first" in page
    # Most benchmarks first, then newest: both have scores on two records, and
    # Beta's latest (Apr) is after Acme's (Feb).
    assert matrix.index("Beta &lt;1&gt;") < matrix.index("Acme-1")
    # Two records named AIME keep their sources visible.
    assert '<span class="models-source">LLM Stats</span>' in matrix
    assert '<span class="models-source">Model reports</span>' in matrix
    # Elo is shown, not averaged; the best of two settings says so.
    assert "1,500 Elo" in matrix and "not averaged" in matrix
    assert "best of 2 settings" in matrix
    assert "<strong>90</strong>" in matrix and "<strong>70</strong>" in matrix
    assert "1 benchmark records have no reported model score." in matrix
    assert "2 models with a reported score on 3 of 4 benchmark records" in status


def test_seed_keeps_document_only_labs_and_publishes_nothing_without_scores(tmp_path):
    payload, records = _fixture(tmp_path)
    documents = {"documents": [{"id": "d", "document_type": "release_post", "organization": "Ai2"}]}
    nav = _models_seed(records, payload, documents)[next(iter(_models_seed(records, payload)))]
    assert "/models/?lab=Ai2" in nav
    assert _models_seed(records, None) == {}
    assert _models_seed([], payload) == {}
