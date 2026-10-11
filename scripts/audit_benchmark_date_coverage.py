"""Export the full catalog's release-date coverage and unresolved source keys.

Run after normalize-catalog. This audit never infers a release from a crawl,
model announcement, similarly named record, or an adoption-only mention.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


def audit_date_coverage(index: dict[str, Any]) -> dict[str, Any]:
    records = index["benchmarks"]
    keys = [row["key"] for row in records]
    if len(set(keys)) != len(keys):
        raise ValueError("duplicate source-record keys in benchmark index")
    totals: dict[str, Counter] = defaultdict(Counter)
    undated = []
    for row in records:
        source = totals[row["source"]]
        source["records"] += 1
        if row.get("released"):
            source["released"] += 1
            continue
        source["missing_release"] += 1
        reference = row.get("first_score_source_reference") or {}
        score = row.get("first_score_record") or {}
        if reference.get("date_precision") == "score_publication":
            fallback = "score_publication"
        elif score.get("date_precision") == "model_announcement":
            fallback = "model_release_proxy"
        else:
            fallback = "undated"
        source[fallback] += 1
        undated.append(
            {
                "key": row["key"],
                "name": row["name"],
                "source": row["source"],
                "source_url": row["source_url"],
                "fallback": fallback,
                "first_score_reported_at": row.get("first_score_reported_at"),
                "status": "release_evidence_required",
            }
        )
    return {
        "records": len(records),
        "released": len(records) - len(undated),
        "missing_release": len(undated),
        "sources": {name: dict(counts) for name, counts in sorted(totals.items())},
        "unresolved": sorted(undated, key=lambda row: row["key"]),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("index", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    audit = audit_date_coverage(json.loads(args.index.read_text(encoding="utf-8")))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(audit, indent=2, ensure_ascii=False) + "\n")
    print(
        f"{audit['released']} released; {audit['missing_release']} missing; "
        f"{audit['records']} total"
    )


if __name__ == "__main__":
    main()
