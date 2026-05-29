"""Tests for equation alignment."""

from __future__ import annotations

import pytest

from bench_score.align import align_equations, equation_similarity
from bench_score.types import Equation, Variable


def _make_eq(eid: str, name: str, latex: str = "", variables: list[Variable] | None = None) -> Equation:
    return Equation(
        equation_local_id=eid,
        equation_name=name,
        equation_description=f"Description of {name}",
        equation_latex=latex or None,
        variables=variables or [],
    )


class TestEquationSimilarity:
    def test_identical(self):
        eq = _make_eq("eq1", "growth rate", r"\mu = \gamma(T) \times \mu_{max}")
        sim = equation_similarity(eq, eq)
        assert sim >= 0.9

    def test_different(self):
        a = _make_eq("eq1", "growth rate", r"\mu = a + b")
        b = _make_eq("eq2", "water activity", r"a_w = 0.995 - 0.00721 \cdot S")
        sim = equation_similarity(a, b)
        assert sim < 0.5


class TestAlignEquations:
    def test_perfect_alignment(self):
        eqs = [
            _make_eq("eq1", "growth rate", r"\mu = a"),
            _make_eq("eq2", "decay rate", r"\delta = b"),
        ]
        pairs = align_equations(eqs, eqs)
        matched = [(gt.equation_local_id, pred.equation_local_id)
                    for gt, pred in pairs if gt and pred]
        assert ("eq1", "eq1") in matched
        assert ("eq2", "eq2") in matched

    def test_shuffled_alignment(self):
        gt = [
            _make_eq("eq1", "growth rate", r"\mu = a"),
            _make_eq("eq2", "decay rate", r"\delta = b"),
        ]
        pred = [
            _make_eq("eq2", "decay rate", r"\delta = b"),
            _make_eq("eq1", "growth rate", r"\mu = a"),
        ]
        pairs = align_equations(gt, pred)
        matched = {(gt.equation_local_id, pred.equation_local_id)
                   for gt, pred in pairs if gt and pred}
        assert ("eq1", "eq1") in matched
        assert ("eq2", "eq2") in matched

    def test_missing_equation(self):
        gt = [
            _make_eq("eq1", "growth rate", r"\mu = a"),
            _make_eq("eq2", "decay rate", r"\delta = b"),
        ]
        pred = [
            _make_eq("eq1", "growth rate", r"\mu = a"),
        ]
        pairs = align_equations(gt, pred)
        matched = [(gt, pred) for gt, pred in pairs if gt and pred]
        missed = [(gt, pred) for gt, pred in pairs if gt and not pred]
        assert len(matched) == 1
        assert len(missed) == 1
        assert missed[0][0].equation_local_id == "eq2"

    def test_extra_equation(self):
        gt = [
            _make_eq("eq1", "growth rate", r"\mu = a"),
        ]
        pred = [
            _make_eq("eq1", "growth rate", r"\mu = a"),
            _make_eq("eq2", "decay rate", r"\delta = b"),
        ]
        pairs = align_equations(gt, pred)
        spurious = [(gt, pred) for gt, pred in pairs if not gt and pred]
        assert len(spurious) == 1

    def test_empty_both(self):
        pairs = align_equations([], [])
        assert pairs == []

    def test_empty_pred(self):
        gt = [_make_eq("eq1", "growth rate")]
        pairs = align_equations(gt, [])
        assert len(pairs) == 1
        assert pairs[0][0] is not None
        assert pairs[0][1] is None

    def test_empty_gt(self):
        pred = [_make_eq("eq1", "growth rate")]
        pairs = align_equations([], pred)
        assert len(pairs) == 1
        assert pairs[0][0] is None
        assert pairs[0][1] is not None
