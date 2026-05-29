"""Shared fixtures for benchmark tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from bench_score.types import Equation, Paper, load_paper

EXAMPLES_DIR = Path(__file__).parent.parent / "examples" / "benchmark"
DB_FORMAT_DIR = EXAMPLES_DIR / "DB_format_json_files"
CURATED_DIR = EXAMPLES_DIR / "curated_json_files"


@pytest.fixture
def db_format_dir() -> Path:
    return DB_FORMAT_DIR


@pytest.fixture
def all_papers() -> list[Paper]:
    """Load all 6 benchmark papers in DB format."""
    papers = []
    for f in sorted(DB_FORMAT_DIR.glob("Paper*_answer.json")):
        papers.append(load_paper(f))
    return papers


@pytest.fixture
def all_equations(all_papers: list[Paper]) -> list[Equation]:
    """Flatten all equations from all papers."""
    eqs = []
    for p in all_papers:
        eqs.extend(p.mechanistic_equations)
    return eqs


@pytest.fixture
def paper001() -> Paper:
    return load_paper(DB_FORMAT_DIR / "Paper001_answer.json")


@pytest.fixture
def paper002() -> Paper:
    return load_paper(DB_FORMAT_DIR / "Paper002_answer.json")
