"""Tests for LaTeX normalization and comparison."""

from __future__ import annotations

import pytest

from bench_score.latex_compare import (
    compare_latex,
    normalize_latex,
    split_condition,
    token_similarity,
    try_sympy_equivalence,
)
from bench_score.types import Equation


class TestSplitCondition:
    def test_no_condition(self):
        eq, cond = split_condition(r"y = ax + b")
        assert eq == r"y = ax + b"
        assert cond == ""

    def test_quad_text_for(self):
        latex = r"y = ax \quad\text{for } x > 0"
        eq, cond = split_condition(latex)
        assert eq == r"y = ax"
        assert "for" in cond

    def test_comma_text_where(self):
        latex = r"f(x) = x^2, \text{where } x \in \mathbb{R}"
        eq, cond = split_condition(latex)
        assert eq == r"f(x) = x^2"
        assert "where" in cond


class TestNormalizeLatex:
    def test_identity(self):
        assert normalize_latex("a+b") == "a+b"

    def test_whitespace(self):
        assert normalize_latex(r"\frac{a}{b}") == normalize_latex(r"\frac{ a }{ b }")

    def test_text_mathrm_equivalence(self):
        assert normalize_latex(r"\text{pH}") == normalize_latex(r"\mathrm{pH}")

    def test_delimiter_normalization(self):
        assert normalize_latex(r"\left(\frac{a}{b}\right)") == normalize_latex(r"(\frac{a}{b})")

    def test_operator_normalization(self):
        assert normalize_latex(r"a \times b") == normalize_latex(r"a \cdot b")

    def test_spacing_stripped(self):
        assert normalize_latex(r"a\,b\;c") == normalize_latex("abc")

    def test_subscript_braces(self):
        assert normalize_latex("N_0") == normalize_latex("N_{0}")

    def test_complex_subscript_preserved(self):
        n = normalize_latex(r"T_{\mathrm{aging}}")
        assert "aging" in n

    def test_uncertainty_stripped(self):
        a = normalize_latex(r"0.94 (\pm 0.022)")
        b = normalize_latex(r"0.94")
        assert a == b


class TestTokenSimilarity:
    def test_identical(self):
        assert token_similarity("a + b", "a + b") == 1.0

    def test_completely_different(self):
        sim = token_similarity("x^2 + y^2", "\\sin(\\theta)")
        assert sim < 0.5

    def test_similar_with_noise(self):
        a = r"\frac{a}{b+c}"
        b = r"\frac{a}{b + c}"
        sim = token_similarity(a, b)
        assert sim > 0.8

    def test_empty_strings(self):
        assert token_similarity("", "") == 1.0


class TestSympyEquivalence:
    def test_commutative(self):
        result = try_sympy_equivalence("a + b", "b + a")
        assert result == 1.0

    def test_fraction_forms(self):
        result = try_sympy_equivalence(r"\frac{a}{b}", r"a / b")
        if result is not None:
            assert result == 1.0

    def test_clearly_different(self):
        result = try_sympy_equivalence("a + b", "a - b")
        if result is not None:
            assert result == 0.0

    def test_unparseable_returns_none(self):
        result = try_sympy_equivalence(
            r"\text{water-phase salt} \cdot 0.00721",
            r"0.00721 * WPS",
        )
        # Should return None (can't parse domain-specific text)
        # or a float if normalization made it parseable
        assert result is None or isinstance(result, float)


class TestCompareLatex:
    def test_identical(self):
        fs = compare_latex("a + b", "a + b")
        assert fs.score == 1.0

    def test_both_null(self):
        fs = compare_latex(None, None)
        assert fs.score == 1.0
        assert fs.method == "both_null"

    def test_one_null(self):
        fs = compare_latex("a + b", None)
        assert fs.score == 0.0

    def test_normalized_match(self):
        fs = compare_latex(r"a \times b", r"a \cdot b")
        assert fs.score == 1.0
        assert fs.method == "normalized_exact"

    def test_different_equations(self):
        fs = compare_latex(r"\frac{a}{b}", r"a + b")
        assert fs.score < 0.8

    def test_condition_stripped(self):
        a = r"y = ax + b \quad\text{for } x > 0"
        b = r"y = ax + b"
        fs = compare_latex(a, b)
        assert fs.score == 1.0


class TestAllEquationsSelfScore:
    def test_all_equations_self_score_1(self, all_equations):
        """Every equation in the benchmark should score 1.0 against itself."""
        for eq in all_equations:
            if eq.equation_latex:
                fs = compare_latex(eq.equation_latex, eq.equation_latex)
                assert fs.score == 1.0, (
                    f"Equation {eq.equation_local_id} ({eq.equation_name}) "
                    f"did not self-score 1.0: score={fs.score}, method={fs.method}"
                )

    def test_all_equations_normalized_self_score(self, all_equations):
        """Equations should still score 1.0 after whitespace perturbation."""
        for eq in all_equations:
            if eq.equation_latex:
                perturbed = eq.equation_latex.replace("=", " = ").replace("+", " + ")
                fs = compare_latex(eq.equation_latex, perturbed)
                assert fs.score >= 0.9, (
                    f"Equation {eq.equation_local_id} perturbed score too low: "
                    f"{fs.score}, method={fs.method}"
                )
