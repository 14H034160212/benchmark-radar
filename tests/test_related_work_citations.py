from __future__ import annotations

import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from test_related_work import _paths, _run_related_work_cli

from benchmark_radar.citation import BIBTEX_KEY, bibtex_citation
from benchmark_radar.models import RadarItem, RadarRun, SourceHealth
from benchmark_radar.query import QueryService
from benchmark_radar.related_work import (
    ManuscriptContext,
    append_missing_bibtex,
    citation_placements,
)
from benchmark_radar.snapshots import write_snapshot


@pytest.mark.parametrize(
    ("packages", "command"),
    [
        (r"\usepackage{natbib}", "citep"),
        (r"\usepackage[numbers]{url, natbib}", "citep"),
        ("\\RequirePackage\n[numbers]\n{natbib}", "citep"),
        (r"% \usepackage{natbib}", "cite"),
        (r"\usepackage{url}", "cite"),
    ],
)
def test_placements_locate_actual_paragraphs_and_heading(packages: str, command: str) -> None:
    text = (
        packages + "\n\\begin{document}\n% \\section{Related Work}\n"
        "\\section{Related Work}\n\\label{sec:related}\n\nExisting related paragraph.\n"
        "\\section{Experimental Setup}\n\nExisting setup paragraph.\n\\end{document}\n"
    )
    placements = citation_placements(ManuscriptContext("main.tex", text))
    lines = text.splitlines()
    assert [item["option"] for item in placements] == [1, 2, 3]
    assert lines[placements[0]["line"] - 1] == "Existing related paragraph."
    assert lines[placements[1]["line"] - 1] == "Existing setup paragraph."
    assert lines[placements[2]["line"] - 1] == r"\section{Related Work}"
    assert all(item["file"] == "main.tex" and item["available"] for item in placements)
    assert all(f"\\{command}{{{BIBTEX_KEY}}}" in item["sentence"] for item in placements)
    assert placements[2]["sentence"].startswith(r"\footnote{")


def test_multiline_heading_anchor_ends_after_title_braces() -> None:
    text = "\\section{\nRelated Work\n}\nA paragraph.\n"
    placements = citation_placements(ManuscriptContext("main.tex", text))
    assert placements[0]["line"] == 4
    assert placements[2]["line"] == 3
    assert placements[1]["line"] is None


def test_missing_sections_and_no_manuscript_have_honest_locations() -> None:
    placements = citation_placements(
        ManuscriptContext("main.tex", "\\section{Introduction}\nHi.\n")
    )
    assert all(item["line"] is None and not item["available"] for item in placements)
    assert all(item["file"] == "main.tex" and item["reason"] for item in placements)
    defaults = citation_placements(None)
    assert all(item["file"] is None and item["line"] is None for item in defaults)


@pytest.mark.parametrize("delimiter", ["brace", "parenthesis"])
def test_bibtex_append_preserves_bytes_and_skips_only_active_keys(delimiter: str) -> None:
    opening, closing = ("{", "}") if delimiter == "brace" else ("(", ")")
    original = (
        "% Original bibliography\r\n"
        '@string{publisher = "Example"}\r\n'
        '@preamble{"\\newcommand{\\example}{Example}"}\r\n'
        '@comment{Ignore unmatched " quote}\r\n'
        f'@misc{opening}existing, title="Quoted @misc{{{BIBTEX_KEY}, title={{Fake}}}}", '
        f'note={{Nested {{values, commas}} and escaped \\%}}, year="2025"{closing}\r\n'
    ).encode()
    generated = "@misc{existing, title={Do not replace}}\n\n" + bibtex_citation() + "\n"
    merged = append_missing_bibtex(original, generated)
    assert merged.startswith(original)
    assert b"Do not replace" not in merged
    assert merged.endswith((bibtex_citation() + "\n").encode())
    assert append_missing_bibtex(merged, generated) == merged


@pytest.mark.parametrize(
    "original",
    [
        b"@misc{existing, title={Title}, url={https://example.com/a%20b}}\n",
        b'@misc(existing, title="Title 20% with comma, okay", year={2025})\n',
    ],
)
def test_literal_percent_values_survive_append(original: bytes) -> None:
    generated = "@misc{existing, title={Do not replace}}\n\n" + bibtex_citation()
    merged = append_missing_bibtex(original, generated)
    assert merged.startswith(original)
    assert b"Do not replace" not in merged
    assert append_missing_bibtex(merged, generated) == merged


@pytest.mark.parametrize("prefix", ["% ", "@comment{Ignore "])
def test_bibtex_entries_in_top_level_text_are_not_duplicated(prefix: str) -> None:
    original = (prefix + bibtex_citation() + "\n").encode()
    assert append_missing_bibtex(original, bibtex_citation()) == original


def test_related_work_descendant_paragraph_is_available() -> None:
    text = (
        "\\section{Related Work}\n"
        "\\subsection{Agent evaluation}\n"
        "\\label{sec:agents}\n"
        "Actual related paragraph.\n"
        "\\section{Methods}\n"
        "Setup paragraph.\n"
    )
    placements = citation_placements(ManuscriptContext("main.tex", text))
    assert placements[0]["line"] == 4
    assert placements[1]["line"] == 6
    assert placements[2]["line"] == 1


def test_verbatim_commands_do_not_supply_sections_or_packages() -> None:
    text = (
        "\\begin{verbatim}\n"
        "\\usepackage{natbib}\n"
        "\\section{Related Work}\n"
        "Example paragraph.\n"
        "\\end{verbatim}\n"
        "\\section{Related Work}\n"
        "Actual paragraph.\n"
    )
    placements = citation_placements(ManuscriptContext("main.tex", text))
    assert placements[0]["line"] == 7
    assert placements[2]["line"] == 6
    assert all(f"\\cite{{{BIBTEX_KEY}}}" in item["sentence"] for item in placements)


@pytest.mark.parametrize(
    "heading", ["\\subsection{Agent evaluation}", "\\subsection{\nAgent evaluation\n}"]
)
def test_multiline_descendant_heading_is_not_a_paragraph(heading: str) -> None:
    text = "\\section{Related Work}\n" + heading + "\nActual paragraph.\n"
    placements = citation_placements(ManuscriptContext("main.tex", text))
    assert text.splitlines()[placements[0]["line"] - 1] == "Actual paragraph."


def test_commented_verbatim_delimiters_do_not_hide_active_sections() -> None:
    text = "% \\begin{verbatim}\n\\section{Related Work}\nActual paragraph.\n% \\end{verbatim}\n"
    placements = citation_placements(ManuscriptContext("main.tex", text))
    assert placements[0]["line"] == 3
    assert placements[2]["line"] == 2


def test_existing_radar_key_is_preserved_without_rewriting() -> None:
    existing = f"@misc({BIBTEX_KEY}, title={{User's existing reference}})\r\n".encode()
    assert append_missing_bibtex(existing, bibtex_citation()) == existing


def test_cli_append_is_idempotent_and_preserves_permissions(tmp_path: Path, capsys) -> None:
    paths = _paths(tmp_path)
    bib = tmp_path / "refs.bib"
    original = b"% Existing work\r\n@misc(existing, title={Original})\r\n"
    bib.write_bytes(original)
    bib.chmod(0o640)
    for run in range(2):
        assert _run_related_work_cli(paths, "--bib", str(bib), "--json") == 0
        captured = capsys.readouterr()
        json.loads(captured.out)
        current = bib.read_bytes()
        assert current.startswith(original)
        assert current.count(f"@misc{{{BIBTEX_KEY},".encode()) == 1
        assert bib.stat().st_mode & 0o777 == 0o640
        if run == 0:
            first = current
            first_mtime = bib.stat().st_mtime_ns
            assert "Added" in captured.err
        else:
            assert current == first
            assert bib.stat().st_mtime_ns == first_mtime
            assert "already" in captured.err


@pytest.mark.parametrize("failure", ["utf8", "malformed"])
def test_invalid_existing_bibtex_preserves_all_destinations(
    tmp_path: Path, capsys, failure: str
) -> None:
    paths = _paths(tmp_path)
    tex, bib = tmp_path / "related.tex", tmp_path / "refs.bib"
    tex.write_bytes(b"Original tex")
    original = b"\xff" if failure == "utf8" else b"@misc{unfinished, title={Broken}"
    bib.write_bytes(original)
    assert _run_related_work_cli(paths, "--tex", str(tex), "--bib", str(bib), "--json") == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert json.loads(captured.err)["error"]["code"] == "artifact_write_failed"
    assert tex.read_bytes() == b"Original tex"
    assert bib.read_bytes() == original


@pytest.mark.parametrize("alias", ["same", "symlink", "hardlink"])
def test_cli_rejects_manuscript_export_aliases(tmp_path: Path, capsys, alias: str) -> None:
    paths = _paths(tmp_path)
    main = tmp_path / "main.tex"
    original = b"\\section{Related Work}\nExisting paragraph.\n"
    main.write_bytes(original)
    output = main
    if alias != "same":
        output = tmp_path / "alias.tex"
        if alias == "symlink":
            output.symlink_to(main)
        else:
            os.link(main, output)
    assert _run_related_work_cli(paths, "--main", str(main), "--tex", str(output), "--json") == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert json.loads(captured.err)["error"]["code"] == "invalid_paths"
    assert main.read_bytes() == original


def test_cli_rejects_hardlinked_export_destinations(tmp_path: Path, capsys) -> None:
    paths = _paths(tmp_path)
    tex, bib = tmp_path / "related.tex", tmp_path / "refs.bib"
    tex.write_bytes(b"Existing file")
    os.link(tex, bib)
    assert _run_related_work_cli(paths, "--tex", str(tex), "--bib", str(bib), "--json") == 1
    captured = capsys.readouterr()
    assert json.loads(captured.err)["error"]["code"] == "artifact_write_failed"
    assert tex.read_bytes() == bib.read_bytes() == b"Existing file"


@pytest.mark.parametrize("failure", ["missing", "utf8"])
def test_cli_manuscript_read_errors_are_structured(tmp_path: Path, capsys, failure: str) -> None:
    paths = _paths(tmp_path)
    main, bib = tmp_path / "main.tex", tmp_path / "refs.bib"
    if failure == "utf8":
        main.write_bytes(b"\xff")
    assert _run_related_work_cli(paths, "--main", str(main), "--bib", str(bib), "--json") == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert json.loads(captured.err)["error"]["code"] == "manuscript_read_failed"
    assert not bib.exists()


def test_scholarly_filter_runs_before_radar_search_limit(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    generated = datetime(2026, 8, 31, 8, tzinfo=UTC)
    items = [
        RadarItem(
            source="GitHub",
            source_id=f"example/novel-{index}",
            title="novel scholarly",
            url=f"https://github.com/example/novel-{index}",
            published_at=generated,
            summary="novel scholarly",
            categories=["benchmark"],
        )
        for index in range(205)
    ]
    items.append(
        RadarItem(
            source="arXiv",
            source_id="2608.09999",
            title="A novel scholarly benchmark for agents",
            url="https://arxiv.org/abs/2608.09999",
            published_at=generated,
            summary="A benchmark with novel scholarly evidence.",
            categories=["benchmark"],
        )
    )
    write_snapshot(
        RadarRun(
            generated_at=generated,
            since=generated - timedelta(days=1),
            items=items,
            health=[SourceHealth(source="arxiv", ok=True, item_count=1, method="API")],
        ),
        paths.snapshots,
    )
    service = QueryService(paths)
    assert all(
        item["source"] == "GitHub"
        for item in service.search("novel scholarly", scope="radar", limit=200)["results"]
    )
    payload = service.related_work(["novel scholarly"], per_topic=1)
    assert [entry["arxiv_id"] for entry in payload["entries"]] == ["2608.09999"]


def test_per_topic_limit_covers_both_scopes_and_duplicate_leads_enrich(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    generated = datetime(2026, 8, 31, 8, tzinfo=UTC)
    index = json.loads(paths.index.read_text())
    record = next(row for row in index["benchmarks"] if row["name"] == "Agent Workbench")
    shard_path = paths.shards / f"{record['slug']}.json"
    shard = json.loads(shard_path.read_text())
    shard["record"]["artifacts"].append(
        {"kind": "paper", "url": "https://arxiv.org/abs/2608.01234"}
    )
    shard_path.write_text(json.dumps(shard))
    write_snapshot(
        RadarRun(
            generated_at=generated,
            since=generated - timedelta(days=1),
            items=[
                RadarItem(
                    source="Semantic Scholar",
                    source_id="semantic123",
                    title="Agent Workbench",
                    url="https://semanticscholar.org/paper/semantic123",
                    artifact_urls=["https://arxiv.org/abs/2608.01234"],
                    authors=["Ada Lovelace"],
                    published_at=generated,
                    summary="An agent workbench benchmark.",
                    categories=["benchmark"],
                )
            ],
            health=[SourceHealth(source="semantic_scholar", ok=True, item_count=1, method="API")],
        ),
        paths.snapshots,
    )
    payload = QueryService(paths).related_work(["agent workbench"], per_topic=1)
    assert len(payload["topics"][0]["cite_keys"]) == 1
    assert payload["count"] == 1
    assert payload["entries"][0]["arxiv_id"] == "2608.01234"
    assert payload["entries"][0]["authors"]
    assert "radar:semantic scholar:semantic123" in payload["entries"][0]["merged_keys"]
