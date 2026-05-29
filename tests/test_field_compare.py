"""Tests for field-type-aware comparison functions."""

from __future__ import annotations

import pytest

from bench_score.field_compare import (
    compare_assumptions,
    compare_numeric,
    compare_parameters,
    compare_source_spans,
    compare_string_exact,
    compare_string_fuzzy,
    compare_text_similarity,
    compare_variables,
)
from bench_score.types import Parameter, SourceSpan, Variable


class TestStringExact:
    def test_identical(self):
        assert compare_string_exact("eq1", "eq1") == 1.0

    def test_case_insensitive(self):
        assert compare_string_exact("Eq1", "eq1") == 1.0

    def test_different(self):
        assert compare_string_exact("eq1", "eq2") == 0.0

    def test_both_none(self):
        assert compare_string_exact(None, None) == 1.0

    def test_one_none(self):
        assert compare_string_exact("eq1", None) == 0.0


class TestStringFuzzy:
    def test_identical(self):
        assert compare_string_fuzzy("maximum growth rate", "maximum growth rate") == 1.0

    def test_similar(self):
        score = compare_string_fuzzy("maximum growth rate", "max growth rate")
        assert score > 0.5

    def test_different(self):
        score = compare_string_fuzzy("temperature", "water activity")
        assert score < 0.5

    def test_both_none(self):
        assert compare_string_fuzzy(None, None) == 1.0


class TestNumeric:
    def test_exact(self):
        assert compare_numeric(0.76, 0.76) == 1.0

    def test_within_tolerance(self):
        assert compare_numeric(0.760, 0.7601) == 1.0

    def test_outside_tolerance(self):
        score = compare_numeric(1.0, 2.0)
        assert score < 1.0

    def test_both_none(self):
        assert compare_numeric(None, None) == 1.0

    def test_one_none(self):
        assert compare_numeric(5.0, None) == 0.0

    def test_zero_values(self):
        assert compare_numeric(0.0, 0.0) == 1.0

    def test_large_numbers(self):
        assert compare_numeric(40000000.0, 40000000.0) == 1.0

    def test_string_numeric(self):
        assert compare_numeric("0.76", 0.76) == 1.0


class TestTextSimilarity:
    def test_identical(self):
        text = "Primary growth model for Clostridium tyrobutyricum"
        assert compare_text_similarity(text, text) == 1.0

    def test_similar(self):
        a = "Primary growth model for Clostridium tyrobutyricum in Gouda cheese"
        b = "Growth model for C. tyrobutyricum in cheese"
        score = compare_text_similarity(a, b)
        assert score > 0.3

    def test_different(self):
        a = "Primary growth model for bacteria"
        b = "Economic optimization of feed costs"
        score = compare_text_similarity(a, b)
        assert score < 0.3

    def test_both_none(self):
        assert compare_text_similarity(None, None) == 1.0


class TestCompareVariables:
    def test_identical(self):
        vars = [
            Variable(symbol="t", name="aging time", unit="h"),
            Variable(symbol="T", name="temperature", unit="C"),
        ]
        fs = compare_variables(vars, vars)
        assert fs.score == 1.0

    def test_partial_match(self):
        gt = [
            Variable(symbol="t", name="aging time", unit="h"),
            Variable(symbol="T", name="temperature", unit="C"),
        ]
        pred = [
            Variable(symbol="t", name="time", unit="h"),
        ]
        fs = compare_variables(gt, pred)
        assert 0.0 < fs.score < 1.0

    def test_no_match(self):
        gt = [Variable(symbol="t", name="time")]
        pred = [Variable(symbol="x", name="distance")]
        fs = compare_variables(gt, pred)
        assert fs.score == 0.0

    def test_both_empty(self):
        fs = compare_variables([], [])
        assert fs.score == 1.0


class TestCompareParameters:
    def test_identical(self):
        params = [
            Parameter(symbol=r"N_{max}", name="max population", value=40000000.0, unit="MPN/kg"),
            Parameter(symbol=r"\mu_{max}", name="max growth rate", value=0.76, unit="h^{-1}"),
        ]
        fs = compare_parameters(params, params)
        assert fs.score == 1.0

    def test_value_difference(self):
        gt = [Parameter(symbol="a", name="param a", value=1.0)]
        pred = [Parameter(symbol="a", name="param a", value=2.0)]
        fs = compare_parameters(gt, pred)
        assert 0.0 < fs.score < 1.0

    def test_both_empty(self):
        fs = compare_parameters([], [])
        assert fs.score == 1.0


class TestCompareAssumptions:
    def test_identical(self):
        assumptions = ["Logistic growth", "Fixed maximum density"]
        fs = compare_assumptions(assumptions, assumptions)
        assert fs.score == 1.0

    def test_similar(self):
        gt = ["Assumes logistic growth with a fixed maximum population density"]
        pred = ["Logistic growth model with fixed maximum population"]
        fs = compare_assumptions(gt, pred)
        assert fs.score > 0.3

    def test_both_empty(self):
        fs = compare_assumptions([], [])
        assert fs.score == 1.0


class TestCompareSourceSpans:
    def test_identical(self):
        spans = [
            SourceSpan(
                section="MATERIALS AND METHODS",
                label_in_paper="[1]",
                text_context="Growth of C. tyrobutyricum is described by...",
                table_ids=["tbl2"],
            ),
        ]
        fs = compare_source_spans(spans, spans)
        assert fs.score == 1.0

    def test_both_empty(self):
        fs = compare_source_spans([], [])
        assert fs.score == 1.0

    def test_different_sections(self):
        gt = [SourceSpan(section="Methods", label_in_paper="[1]")]
        pred = [SourceSpan(section="Results", label_in_paper="[1]")]
        fs = compare_source_spans(gt, pred)
        assert 0.0 < fs.score < 1.0
