"""One reported score per model and benchmark record, for the Models matrix.

benchmark-radar.com's Model Evals compared models in a "model x benchmark"
matrix with a shared-benchmark average. This module builds the data that view
reads, from the same catalog shards every other surface reads (one evidence
path, as ``models_registry.build_registry``), and holds the rules the page
applies, so the Python seed and ``assets/app.js`` cannot drift:

1. A comparison uses only the benchmarks every compared model has a score on.
   A model that reported only easy benchmarks does not get a higher average.
2. A score enters an average on its series' direction and scale. Raw values mix
   Elo (1577), fractions (0.6) and percentages (74.7); a series' declared
   ``display_multiplier`` puts it on its display scale, and only a series whose
   display scale is 0-100 is averaged, flipped when lower is better. Elo,
   dollar and point scales are shown in their cells and left out of averages.
3. Every average states how many shared benchmarks it uses.

Every source is read the same way: none is preferred or discounted.
"""

from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any

from .models_registry import build_registry

SCHEMA_VERSION = 1
DEFAULT_SCORES_OUTPUT = Path("site/data/model-scores.json")
DIRECTIONS = ("higher_is_better", "lower_is_better")


def score_scale(series: dict[str, Any]) -> tuple[float, bool]:
    """A series' display multiplier, and whether its display scale is 0-100.

    The multiplier is the series' own ``display_multiplier`` (fractions are
    declared with 100). The display scale is 0-100 when the series says so: a
    multiplier of 100, a percent unit, or a declared maximum that the multiplier
    puts at 100. A reported value outside 0-100 contradicts that and wins.
    """
    summary = series.get("score_summary") or {}
    multiplier = summary.get("display_multiplier") or 1
    unit = summary.get("unit") or series.get("unit")
    declared = series.get("declared_max")
    percent = (
        multiplier == 100
        or unit == "percent"
        or (declared is not None and declared * multiplier == 100)
    )
    raw_min, raw_max = summary.get("raw_min"), summary.get("raw_max")
    if raw_min is not None and raw_min * multiplier < 0:
        percent = False
    if raw_max is not None and raw_max * multiplier > 100:
        percent = False
    return multiplier, percent


def _better(direction: str | None, candidate: float, current: float) -> bool:
    if direction == "lower_is_better":
        return candidate < current
    return candidate > current


def _unit_label(series: dict[str, Any], percent: bool) -> str | None:
    if percent:
        return "%"
    unit = (series.get("score_summary") or {}).get("unit") or series.get("unit")
    return {"elo": "Elo", "usd": "USD"}.get(unit, unit)


def build_model_scores(shard_dir: Path) -> dict[str, Any]:
    """Each registry model's best reported score on each benchmark record.

    Models are the registry's (organization, model) identities, so the matrix
    and models.json agree. Several rows for one model on one record (different
    protocols or settings) keep the best by the series' direction; the count of
    rows is kept so the page can say that more settings were reported, and the
    side panel reads every row from the record's shard.
    """
    shard_dir = Path(shard_dir)
    registry = build_registry({}, shard_dir)
    keys = {
        (record.organization.lower(), record.model.lower()): key for key, record in registry.items()
    }
    benchmarks: list[dict[str, Any]] = []
    cells: dict[str, dict[int, list[Any]]] = {}
    dates: dict[str, str] = {}
    for path in sorted(shard_dir.glob("*.json")):
        shard = json.loads(path.read_text(encoding="utf-8"))
        record_key = (shard.get("record") or {}).get("key")
        for _source, payload in sorted((shard.get("scores_by_source") or {}).items()):
            rows = [
                row
                for row in payload.get("rows") or []
                if isinstance(row.get("value"), (int, float))
            ]
            if not rows or not record_key:
                continue
            series = payload.get("series") or {}
            multiplier, percent = score_scale(series)
            direction = series.get("direction")
            index = len(benchmarks)
            benchmarks.append(
                {
                    "key": record_key,
                    "direction": direction if direction in DIRECTIONS else None,
                    "multiplier": multiplier,
                    "percent": percent,
                    "unit": _unit_label(series, percent),
                }
            )
            for row in rows:
                identity = (
                    (row.get("organization") or "").lower(),
                    (row.get("model_name") or "").lower(),
                )
                model = keys.get(identity)
                if model is None:
                    continue
                value = round(row["value"] * multiplier, 4)
                cell = cells.setdefault(model, {}).get(index)
                if cell is None:
                    cells[model][index] = [value, 1]
                else:
                    cell[1] += 1
                    if _better(direction, value, cell[0]):
                        cell[0] = value
                reported = row.get("reported_date") or row.get("reported_at") or ""
                dates[model] = max(dates.get(model, ""), reported)
    models = [
        {
            "key": key,
            "model": registry[key].model,
            "organization": registry[key].organization,
            "date": dates.get(key) or None,
            # [benchmark index, display value] plus the row count when several
            # settings were reported.
            "scores": [
                [index, value] if count == 1 else [index, value, count]
                for index, (value, count) in sorted(cells[key].items())
            ],
        }
        for key in sorted(cells)
    ]
    return {"schema_version": SCHEMA_VERSION, "benchmarks": benchmarks, "models": models}


def write_model_scores(shard_dir: Path, output: Path = DEFAULT_SCORES_OUTPUT) -> dict[str, Any]:
    payload = build_model_scores(shard_dir)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8"
    )
    return {"models": len(payload["models"]), "benchmarks": len(payload["benchmarks"])}


def average_value(value: float, benchmark: dict[str, Any]) -> float | None:
    """A display value on the 0-100 higher-is-better scale averages use, or None."""
    if not benchmark.get("percent") or benchmark.get("direction") not in DIRECTIONS:
        return None
    return 100 - value if benchmark["direction"] == "lower_is_better" else value


def round_tenth(value: float) -> float:
    """Math.round(10 * value) / 10, as the page rounds, not banker's rounding."""
    return math.floor(10 * value + 0.5) / 10


def shared_average(
    columns: list[dict[str, float]], benchmarks: dict[str, dict[str, Any]]
) -> tuple[list[float | None], list[str]]:
    """Mean over the averageable benchmarks every column has a score on.

    ``columns`` maps record keys to display values, one mapping per model.
    Returns each column's mean (None when nothing is shared) and the shared
    record keys, whose count the page shows. Mirrors modelSharedAverage in
    app.js, summing in the same key order so both round the same float.
    """
    if not columns:
        return [], []
    shared = sorted(
        key
        for key in columns[0]
        if all(key in column for column in columns)
        and average_value(columns[0][key], benchmarks.get(key) or {}) is not None
    )
    if not shared:
        return [None] * len(columns), []
    means: list[float | None] = []
    for column in columns:
        total = 0.0
        for key in shared:
            total += average_value(column[key], benchmarks[key])
        means.append(round_tenth(total / len(shared)))
    return means, shared


# .com Model Evals' capability groups, in its order, read from a record's
# categories and Library direction. A benchmark measuring several abilities sits
# in the first group it matches. Mirrors modelCapabilityGroup in app.js.
CAPABILITY_GROUPS = (
    ("Mathematics", r"math"),
    ("Coding", r"cod|software"),
    ("Agents & Tools", r"agent|tool|computer"),
    ("Science", r"science|biology|chemistry|physics"),
    ("Multimodal", r"vision|multi|image|video|audio|speech"),
    ("Reasoning & Knowledge", r"reason|knowledge|language"),
)
CAPABILITY_ORDER = (
    "Reasoning & Knowledge",
    "Mathematics",
    "Coding",
    "Agents & Tools",
    "Science",
    "Multimodal",
    "Other",
)


def capability_group(record: dict[str, Any]) -> str:
    direction = record.get("library_direction") or {}
    text = " ".join(
        [*(record.get("categories") or []), *(direction.get("categories") or [])]
    ).lower()
    for group, pattern in CAPABILITY_GROUPS:
        if re.search(pattern, text):
            return group
    return "Other"


_CONFIGURATION = re.compile(r"^(.*?)[\s-]*\(([^()]*)\)$")


def model_family(name: str) -> tuple[str, str]:
    """A model name split into its family and configuration.

    "Claude Opus 5 (Adaptive Reasoning, High Effort)" is the family "Claude Opus
    5" in the configuration "Adaptive Reasoning, High Effort", so configurations
    of one model sit together in the matrix. A name without a trailing
    parenthesis is its own family. Mirrors modelFamily in app.js.
    """
    match = _CONFIGURATION.match(name.strip())
    if match and match.group(1):
        return match.group(1), match.group(2)
    return name.strip(), ""


def order_models(models: list[dict[str, Any]], sort: str = "coverage") -> list[dict[str, Any]]:
    """Columns in the page's order, a family's configurations together.

    ``models`` carry ``organization``, ``model``, ``date`` and ``cells``.
    "coverage" puts the most benchmarks first, then the newest; "newest" orders
    by the latest reported score. Families sort by their best member, then by
    name; within one, the base model comes before its configurations, then the
    same order, then the name. Mirrors modelOrder in app.js (plain code-point
    comparison on both sides).
    """

    def family_key(model: dict[str, Any]) -> str:
        return f"{model['organization']}\u0000{model_family(model['model'])[0]}"

    def descending(value: str) -> tuple[int, ...]:
        return tuple(-ord(char) for char in value) + (1,)

    def metric(model: dict[str, Any]) -> tuple[Any, ...]:
        newest = descending(model.get("date") or "")
        return (newest,) if sort == "newest" else (-len(model.get("cells") or ()), newest)

    best: dict[str, tuple[Any, ...]] = {}
    for model in models:
        key = family_key(model)
        best[key] = min(best.get(key, metric(model)), metric(model))
    return sorted(
        models,
        key=lambda model: (
            best[family_key(model)],
            family_key(model),
            bool(model_family(model["model"])[1]),
            metric(model),
            model["model"],
        ),
    )
