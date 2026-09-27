import hashlib
import importlib.util
import json
from pathlib import Path

from benchmark_radar.catalog import artifact_identifier, normalize_snapshot
from benchmark_radar.leaderboard_snapshots import load_snapshots

ROOT = Path(__file__).resolve().parents[1]


def test_claire_artifact_urls_use_catalog_identity_anchors():
    assert artifact_identifier("https://arxiv.org/abs/2406.01574v2") == "arxiv:2406.01574"
    assert artifact_identifier("https://arxiv.org/pdf/2406.01574.pdf") == "arxiv:2406.01574"
    assert artifact_identifier("https://github.com/TIGER-AI-Lab/MMLU-Pro") == (
        "gh:tiger-ai-lab/mmlu-pro"
    )
    assert artifact_identifier("https://huggingface.co/datasets/xai-org/RealworldQA") == (
        "hf:xai-org/realworldqa"
    )
    assert artifact_identifier("https://github.com/org/repo/tree/main/data") is None


def _export_module():
    path = ROOT / "scripts" / "export_claire_radar_snapshot.py"
    spec = importlib.util.spec_from_file_location("export_claire_radar_snapshot", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_export_preserves_every_record_with_exact_source_ids_and_review_states():
    module = _export_module()
    document = {
        "records": [
            {
                "id": "accepted",
                "name": "Accepted Bench",
                "displayEligible": True,
                "releasedAt": "2026-09-24",
                "aliases": ["Accepted Evaluation"],
                "whyItMatters": "A fixture-only extra field.",
                "source": {
                    "id": "github:owner/accepted",
                    "type": "github",
                    "url": "https://github.com/owner/accepted",
                },
                "curation": {
                    "state": "ai-reviewed",
                    "reviewedAt": "2026-09-24T12:00:00Z",
                    "model": "claude-haiku",
                },
            },
            {
                "id": "deferred",
                "name": "Deferred Bench",
                "displayEligible": False,
                "source": {
                    "id": "github:owner/deferred",
                    "type": "github",
                    "url": "https://github.com/owner/deferred",
                },
                "curation": {"state": "ai-name-audit-deferred"},
            },
            {
                "id": "unreviewed",
                "name": "Unreviewed Bench",
                "source": {
                    "id": "2609.99999",
                    "type": "arxiv",
                    "url": "https://arxiv.org/abs/2609.99999",
                },
            },
        ]
    }

    rows = module.export_rows(document)

    assert [row["benchmark_id"] for row in rows] == [
        "2609.99999",
        "github:owner/accepted",
        "github:owner/deferred",
    ]
    by_id = {row["benchmark_id"]: row for row in rows}
    assert by_id["github:owner/accepted"]["review_model"] == "claude-haiku"
    assert by_id["github:owner/accepted"]["aliases"] == '["Accepted Evaluation"]'
    assert (
        json.loads(by_id["github:owner/accepted"]["extra_json"])["whyItMatters"]
        == "A fixture-only extra field."
    )
    assert by_id["github:owner/accepted"]["display_eligible"] == "true"
    assert by_id["github:owner/deferred"]["review_state"] == "ai-name-audit-deferred"
    assert by_id["github:owner/deferred"]["display_eligible"] == "false"
    assert by_id["2609.99999"]["review_state"] == "unreviewed"
    assert by_id["2609.99999"]["display_eligible"] == "unknown"
    assert all(len(row["record_sha256"]) == 64 for row in rows)


def test_registered_snapshot_preserves_review_provenance_and_links():
    snapshots = load_snapshots()
    snapshot = next(row for row in snapshots["snapshots"] if row["id"] == "claire_radar_2026-09-25")

    normalized = normalize_snapshot(snapshot)

    assert normalized["validation"]["source_record_count"] == 1914
    assert normalized["validation"]["score_observation_count"] == 0
    record = next(
        row
        for row in normalized["source_records"]
        if row["source_benchmark_id"] == "github:liningbest/apitest"
    )
    assert record["key"] == "claire-radar:github:liningbest/apitest"
    assert record["released"] == "2026-09-13"
    assert record["released_reference"]["source_url"] == "https://github.com/liningbest/apitest"
    assert record["provenance"]["review_state"] == "ai-reviewed"
    assert record["provenance"]["origin_source"] == "github"
    assert record["provenance"]["display_eligible"] == "true"
    assert {item["kind"] for item in record["artifacts"]} == {"repo"}
    assert record["artifacts"][0]["id"] == "gh:liningbest/apitest"
    assert record["source_metadata"]["claire_radar"]["id"] == "bm_apitest_7d8e6901"
    assert record["source_metadata"]["claire_radar"]["whyItMatters"]

    unreviewed = next(
        row for row in normalized["source_records"] if row["source_benchmark_id"] == "2608.16081"
    )
    assert unreviewed["name"] == "SafeGesture"
    assert unreviewed["provenance"]["review_state"] == "unreviewed"
    assert unreviewed["provenance"]["display_eligible"] == "unknown"


def test_registered_snapshot_retains_every_original_object_losslessly():
    snapshot = next(
        row for row in load_snapshots()["snapshots"] if row["id"] == "claire_radar_2026-09-25"
    )

    originals = []
    for row in snapshot["benchmark_rows"]:
        original = json.loads(row["extra_json"])
        payload = json.dumps(
            original, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode()
        assert hashlib.sha256(payload).hexdigest() == row["record_sha256"]
        assert original["id"] == row["origin_record_id"]
        originals.append(original["id"])

    assert len(originals) == 1914
    assert len(set(originals)) == 1914
