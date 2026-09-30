"""Display slugs are not evidence that two scored models are identical."""

import csv
import json
from pathlib import Path

import pytest

from benchmark_radar.models_registry import build_registry


def registry_for(tmp_path, identities):
    rows = [
        {
            "obs_id": f"observation-{index}",
            "model_name": model,
            "organization": organization,
        }
        for index, (organization, model) in enumerate(identities)
    ]
    (tmp_path / "benchmark.json").write_text(
        json.dumps({"scores_by_source": {"llm_stats": {"rows": rows}}})
    )
    return build_registry({}, tmp_path)


@pytest.mark.parametrize(
    "identities",
    [
        [("Cohere", "Command A"), ("Cohere", "Command A+")],
        [("A", "B C"), ("A B", "C")],
        [("研究所", "模型甲"), ("研究所", "模型乙")],
        [("Org", "A/B"), ("Org", "A B")],
    ],
)
def test_slug_collisions_keep_model_evidence_separate(tmp_path, identities):
    # Command A+ currently shares a slug with Command A. The registry dropped
    # the '+' and attributed the newer model's evidence to the older model.
    registry = registry_for(tmp_path, identities)
    assert {(r.organization, r.model) for r in registry.values()} == set(identities)
    assert len(registry) == len(identities)
    for record in registry.values():
        assert len(record.sources) == 1
        assert record.sources[0].payload["model_name"] == record.model
        assert record.sources[0].payload["organization"] == record.organization
    assert all(key.isascii() for key in registry)


def test_collision_keys_and_labels_are_independent_of_input_order(tmp_path):
    identities = [("Cohere", "Command A"), ("Cohere", "Command A+")]
    first = registry_for(tmp_path, identities)
    second = registry_for(tmp_path, list(reversed(identities)))

    def project(registry):
        return [(k, r.organization, r.model) for k, r in registry.items()]

    assert project(first) == project(second)


def test_case_only_spellings_keep_a_deterministic_label(tmp_path):
    identities = [("Cohere", "Command A"), ("COHERE", "COMMAND A")]
    first = registry_for(tmp_path, identities)
    second = registry_for(tmp_path, list(reversed(identities)))
    assert len(first) == len(second) == 1
    assert [(k, r.organization, r.model) for k, r in first.items()] == [
        (k, r.organization, r.model) for k, r in second.items()
    ]


def test_immutable_scores_distinguish_command_a_and_command_a_plus(tmp_path):
    identities = set()
    for path in Path("data/leaderboard_snapshots").glob("*scores*.csv"):
        with path.open() as stream:
            for row in csv.DictReader(stream):
                if row["model_name"] in {"Command A", "Command A+"}:
                    identities.add((row["organization_name"], row["model_name"]))
    assert identities == {("Cohere", "Command A"), ("Cohere", "Command A+")}
    assert len(registry_for(tmp_path, sorted(identities))) == 2
