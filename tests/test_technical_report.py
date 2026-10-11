from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LATEX = ROOT / "docs" / "technical-report" / "latex"
MANUSCRIPT = LATEX / "main.tex"


def test_latex_is_the_only_report_source() -> None:
    assert MANUSCRIPT.is_file()
    assert (LATEX / "references.bib").is_file()
    assert (LATEX / "Makefile").is_file()

    # The ReportLab builders were the previous source. Their return would give
    # the report two sources that can disagree.
    assert not (ROOT / "scripts" / "build_system_evaluation.py").exists()
    assert not (ROOT / "scripts" / "build_technical_report.py").exists()


def test_built_pdf_is_tracked_so_the_report_reads_on_github() -> None:
    assert (LATEX / "main.pdf").is_file()
    ignored = (LATEX / ".gitignore").read_text(encoding="utf-8").split()
    assert "main.pdf" not in ignored


def test_manuscript_records_contributor_names_and_affiliations() -> None:
    # The manuscript ties multi-word names together with LaTeX non-breaking spaces.
    source = MANUSCRIPT.read_text(encoding="utf-8").replace("~", " ")

    for author in ("Koutian Wu", "Junjie Zhou", "Ergan Shang", "Jiayu Wang", "Pengqian Han"):
        assert author in source
    for affiliation in (
        "Tacite AI",
        "Hangzhou Dianzi University",
        "Carnegie Mellon University",
        "Xi'an Jiaotong University",
        "The University of Auckland",
    ):
        assert affiliation in source
    assert "k@tacite.ai" in source


def test_manuscript_embeds_use_case_figures() -> None:
    source = MANUSCRIPT.read_text(encoding="utf-8")
    names = (
        "agent-session.png",
        "artifact-status-paper.png",
        "artifact-status-code.png",
        "cross-validation.png",
    )

    for name in names:
        assert name in source
        assert (LATEX / "figures" / name).is_file()


def test_use_case_tables_are_typeset_rather_than_screenshots() -> None:
    # The survey and prior-art comparison were once screenshots. They are now
    # real tables, so the text is selectable and the links are live.
    source = MANUSCRIPT.read_text(encoding="utf-8")

    for label in ("tab:use-case-survey", "tab:benchmark-comparison"):
        assert f"\\label{{{label}}}" in source
    for retired in ("survey-table.png", "manual-prior-art-table.png"):
        assert retired not in source
        assert not (LATEX / "figures" / retired).exists()


def test_published_pdfs_are_not_copied_into_the_repository() -> None:
    # Cite only https://arxiv.org/abs/2609.11115. The tracked draft is
    # latex/main.pdf; a second PDF copy in the tree goes stale.
    assert not (ROOT / "output" / "pdf").exists()
