"""Tests for score aggregation."""

from __future__ import annotations

import pytest

from bench_score.score import score_equation, score_paper, score_system
from bench_score.types import Equation, Paper, ScoringConfig, Variable, Parameter


def _make_eq(eid: str, name: str, latex: str = "") -> Equation:
    return Equation(
        equation_local_id=eid,
        equation_name=name,
        equation_description=f"Description of {name}",
        equation_latex=latex or None,
        variables=[Variable(symbol="x", name="input")],
        parameters=[Parameter(symbol="a", value=1.0)],
        assumptions=["Linear model"],
    )


def _make_paper(doi: str, title: str, equations: list[Equation]) -> Paper:
    return Paper(doi=doi, title=title, mechanistic_equations=equations)


class TestScoreEquation:
    def test_perfect_score(self):
        eq = _make_eq("eq1", "growth rate", r"\mu = a \times b")
        es = score_equation(eq, eq)
        assert abs(es.overall - 1.0) < 1e-6

    def test_different_equations(self):
        gt = _make_eq("eq1", "growth rate", r"\mu = a")
        pred = _make_eq("eq2", "decay constant", r"\delta = c + d")
        es = score_equation(gt, pred)
        assert es.overall < 1.0


class TestScorePaper:
    def test_perfect_paper(self, paper001):
        ps = score_paper(paper001, paper001)
        assert abs(ps.overall - 1.0) < 1e-6
        assert abs(ps.equation_detection_f1 - 1.0) < 1e-6
        assert abs(ps.mean_equation_score - 1.0) < 1e-6

    def test_empty_prediction(self, paper001):
        empty = Paper(doi=paper001.doi, title=paper001.title, mechanistic_equations=[])
        ps = score_paper(paper001, empty)
        assert ps.equation_detection_f1 == 0.0
        assert ps.overall == 0.0

    def test_extra_predictions(self):
        gt = _make_paper("doi1", "Paper 1", [_make_eq("eq1", "eq one", "a=b")])
        pred = _make_paper("doi1", "Paper 1", [
            _make_eq("eq1", "eq one", "a=b"),
            _make_eq("eq2", "eq two", "c=d"),
        ])
        ps = score_paper(gt, pred)
        assert ps.equation_detection_precision == 0.5
        assert ps.equation_detection_recall == 1.0

    def test_custom_config(self, paper001):
        config = ScoringConfig(
            latex_weight=0.5,
            variables_weight=0.1,
            parameters_weight=0.1,
            name_weight=0.1,
            description_weight=0.1,
            source_spans_weight=0.05,
            assumptions_weight=0.05,
        )
        ps = score_paper(paper001, paper001, config)
        assert abs(ps.overall - 1.0) < 1e-6


class TestScoreSystem:
    def test_perfect_system(self, all_papers):
        pairs = [(p, p) for p in all_papers]
        ss = score_system(pairs)
        assert abs(ss.overall - 1.0) < 1e-6
        assert ss.n_papers == len(all_papers)

    def test_empty(self):
        ss = score_system([])
        assert ss.n_papers == 0
        assert ss.overall == 0.0

    def test_cross_paper_low_score(self, paper001, paper002):
        ps = score_paper(paper001, paper002)
        assert ps.overall < 0.8


class TestSelfScoreAllPapers:
    def test_each_paper_scores_1(self, all_papers):
        """The fundamental validation: every paper scores 1.0 against itself."""
        for paper in all_papers:
            ps = score_paper(paper, paper)
            assert abs(ps.overall - 1.0) < 1e-6, (
                f"Paper '{paper.title[:50]}' self-score={ps.overall:.4f}, "
                f"F1={ps.equation_detection_f1:.4f}, "
                f"quality={ps.mean_equation_score:.4f}"
            )
