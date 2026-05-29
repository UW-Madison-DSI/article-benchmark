"""Field-type-aware comparison functions."""

from __future__ import annotations

import difflib
import math
import re

from bench_score.latex_compare import normalize_latex
from bench_score.types import (
    Equation,
    FieldScore,
    Parameter,
    ScoringConfig,
    SourceSpan,
    Variable,
)

STOPWORDS = frozenset({
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "shall",
    "should", "may", "might", "can", "could", "must", "of", "in", "to",
    "for", "with", "on", "at", "by", "from", "as", "into", "through",
    "during", "before", "after", "and", "but", "or", "nor", "not", "so",
    "yet", "both", "either", "neither", "each", "every", "all", "any",
    "few", "more", "most", "other", "some", "such", "no", "only", "own",
    "same", "than", "too", "very", "just", "also", "that", "this",
    "these", "those", "it", "its",
})


def _tokenize_text(text: str) -> list[str]:
    """Lowercase tokenize, removing punctuation and stopwords."""
    tokens = re.findall(r'[a-z0-9]+', text.lower())
    return [t for t in tokens if t not in STOPWORDS]


def compare_string_exact(gt: str | None, pred: str | None) -> float:
    """Normalized case-insensitive exact match."""
    if gt is None and pred is None:
        return 1.0
    if gt is None or pred is None:
        return 0.0
    return 1.0 if gt.strip().lower() == pred.strip().lower() else 0.0


def compare_string_fuzzy(gt: str | None, pred: str | None) -> float:
    """Token-based fuzzy string similarity.

    Combines Jaccard similarity on tokens with difflib ratio.
    """
    if gt is None and pred is None:
        return 1.0
    if gt is None or pred is None:
        return 0.0
    if not gt.strip() and not pred.strip():
        return 1.0

    gt_tokens = set(_tokenize_text(gt))
    pred_tokens = set(_tokenize_text(pred))

    if not gt_tokens and not pred_tokens:
        return 1.0
    if not gt_tokens or not pred_tokens:
        return 0.0

    intersection = gt_tokens & pred_tokens
    union = gt_tokens | pred_tokens
    jaccard = len(intersection) / len(union) if union else 0.0

    seq_ratio = difflib.SequenceMatcher(None, gt.lower(), pred.lower()).ratio()

    return 0.5 * jaccard + 0.5 * seq_ratio


def compare_numeric(
    gt: float | str | None,
    pred: float | str | None,
    rel_tol: float = 0.01,
    abs_tol: float = 1e-9,
) -> float:
    """Numeric comparison with tolerance."""
    if gt is None and pred is None:
        return 1.0
    if gt is None or pred is None:
        return 0.0

    def _to_float(v: float | str | None) -> float | None:
        if isinstance(v, (int, float)):
            return float(v)
        if isinstance(v, str):
            try:
                return float(v)
            except ValueError:
                return None
        return None

    gt_f = _to_float(gt)
    pred_f = _to_float(pred)

    if gt_f is None and pred_f is None:
        return compare_string_fuzzy(str(gt), str(pred))
    if gt_f is None or pred_f is None:
        return 0.0

    if math.isclose(gt_f, pred_f, rel_tol=rel_tol, abs_tol=abs_tol):
        return 1.0

    denom = max(abs(gt_f), abs_tol)
    relative_error = abs(gt_f - pred_f) / denom
    return max(0.0, 1.0 - relative_error)


def compare_text_similarity(gt: str | None, pred: str | None) -> float:
    """Token-overlap F1 for longer text (descriptions, assumptions)."""
    if gt is None and pred is None:
        return 1.0
    if gt is None or pred is None:
        return 0.0
    if not gt.strip() and not pred.strip():
        return 1.0

    gt_tokens = _tokenize_text(gt)
    pred_tokens = _tokenize_text(pred)

    if not gt_tokens and not pred_tokens:
        return 1.0
    if not gt_tokens or not pred_tokens:
        return 0.0

    gt_bag = {}
    for t in gt_tokens:
        gt_bag[t] = gt_bag.get(t, 0) + 1
    pred_bag = {}
    for t in pred_tokens:
        pred_bag[t] = pred_bag.get(t, 0) + 1

    overlap = sum(min(gt_bag.get(t, 0), pred_bag.get(t, 0)) for t in set(gt_bag) | set(pred_bag))
    precision = overlap / sum(pred_bag.values()) if pred_bag else 0.0
    recall = overlap / sum(gt_bag.values()) if gt_bag else 0.0

    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def _normalize_symbol(sym: str) -> str:
    """Normalize a variable/parameter symbol for matching."""
    return normalize_latex(sym)


def compare_variables(
    gt: list[Variable],
    pred: list[Variable],
) -> FieldScore:
    """Set-based F1 comparison of variable lists, matched by symbol."""
    if not gt and not pred:
        return FieldScore("variables", 1.0, "both_empty")
    if not gt or not pred:
        return FieldScore("variables", 0.0, "one_empty",
                          f"gt={len(gt)}, pred={len(pred)}")

    gt_by_sym = {_normalize_symbol(v.symbol): v for v in gt}
    pred_by_sym = {_normalize_symbol(v.symbol): v for v in pred}

    matched_scores = []
    matched_gt = set()
    matched_pred = set()

    for gt_sym, gt_var in gt_by_sym.items():
        if gt_sym in pred_by_sym:
            pred_var = pred_by_sym[gt_sym]
            score = _score_variable_pair(gt_var, pred_var)
            matched_scores.append(score)
            matched_gt.add(gt_sym)
            matched_pred.add(gt_sym)

    n_gt = len(gt_by_sym)
    n_pred = len(pred_by_sym)
    n_matched = len(matched_scores)

    if n_matched == 0:
        return FieldScore("variables", 0.0, "no_matches",
                          f"gt_syms={list(gt_by_sym.keys())}, pred_syms={list(pred_by_sym.keys())}")

    avg_match_quality = sum(matched_scores) / n_matched
    precision = (n_matched / n_pred) * avg_match_quality
    recall = (n_matched / n_gt) * avg_match_quality

    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

    return FieldScore("variables", f1, "set_f1",
                      f"matched={n_matched}/{n_gt} gt, quality={avg_match_quality:.3f}")


def _score_variable_pair(gt: Variable, pred: Variable) -> float:
    """Score a matched variable pair on name and unit."""
    scores = []
    if gt.name and pred.name:
        scores.append(compare_string_fuzzy(gt.name, pred.name))
    if gt.unit is not None or pred.unit is not None:
        scores.append(_compare_unit(gt.unit, pred.unit))
    if not scores:
        return 1.0
    return sum(scores) / len(scores)


def _compare_unit(gt: str | None, pred: str | None) -> float:
    """Compare unit strings with normalization."""
    if gt is None and pred is None:
        return 1.0
    if gt is None or pred is None:
        return 0.0
    gt_n = re.sub(r'\s+', '', gt.lower())
    pred_n = re.sub(r'\s+', '', pred.lower())
    if gt_n == pred_n:
        return 1.0
    gt_n = gt_n.replace("dimensionless", "").replace("unitless", "")
    pred_n = pred_n.replace("dimensionless", "").replace("unitless", "")
    if gt_n == pred_n:
        return 1.0
    return difflib.SequenceMatcher(None, gt_n, pred_n).ratio()


def compare_parameters(
    gt: list[Parameter],
    pred: list[Parameter],
) -> FieldScore:
    """Set-based F1 comparison of parameter lists, matched by symbol."""
    if not gt and not pred:
        return FieldScore("parameters", 1.0, "both_empty")
    if not gt or not pred:
        return FieldScore("parameters", 0.0, "one_empty",
                          f"gt={len(gt)}, pred={len(pred)}")

    gt_by_sym = {_normalize_symbol(p.symbol): p for p in gt}
    pred_by_sym = {_normalize_symbol(p.symbol): p for p in pred}

    matched_scores = []
    matched_gt = set()

    for gt_sym, gt_param in gt_by_sym.items():
        if gt_sym in pred_by_sym:
            pred_param = pred_by_sym[gt_sym]
            score = _score_parameter_pair(gt_param, pred_param)
            matched_scores.append(score)
            matched_gt.add(gt_sym)

    n_gt = len(gt_by_sym)
    n_pred = len(pred_by_sym)
    n_matched = len(matched_scores)

    if n_matched == 0:
        return FieldScore("parameters", 0.0, "no_matches",
                          f"gt_syms={list(gt_by_sym.keys())[:5]}, "
                          f"pred_syms={list(pred_by_sym.keys())[:5]}")

    avg_match_quality = sum(matched_scores) / n_matched
    precision = (n_matched / n_pred) * avg_match_quality
    recall = (n_matched / n_gt) * avg_match_quality
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

    return FieldScore("parameters", f1, "set_f1",
                      f"matched={n_matched}/{n_gt} gt, quality={avg_match_quality:.3f}")


def _score_parameter_pair(gt: Parameter, pred: Parameter) -> float:
    """Score a matched parameter pair across sub-fields."""
    scores = []

    if gt.name is not None or pred.name is not None:
        scores.append(compare_string_fuzzy(gt.name, pred.name))

    if gt.value is not None or pred.value is not None:
        scores.append(compare_numeric(gt.value, pred.value))

    if gt.unit is not None or pred.unit is not None:
        scores.append(_compare_unit(gt.unit, pred.unit))

    if not scores:
        return 1.0
    return sum(scores) / len(scores)


def compare_assumptions(
    gt: list[str],
    pred: list[str],
) -> FieldScore:
    """Best-match pairing of assumption text blocks."""
    if not gt and not pred:
        return FieldScore("assumptions", 1.0, "both_empty")
    if not gt or not pred:
        return FieldScore("assumptions", 0.0, "one_empty",
                          f"gt={len(gt)}, pred={len(pred)}")

    scores = []
    for gt_a in gt:
        best = max(compare_text_similarity(gt_a, pred_a) for pred_a in pred)
        scores.append(best)

    return FieldScore("assumptions", sum(scores) / len(scores), "best_match",
                      f"n_gt={len(gt)}, n_pred={len(pred)}")


def compare_source_spans(
    gt: list[SourceSpan],
    pred: list[SourceSpan],
) -> FieldScore:
    """Compare source span attribution."""
    if not gt and not pred:
        return FieldScore("source_spans", 1.0, "both_empty")
    if not gt or not pred:
        return FieldScore("source_spans", 0.0, "one_empty",
                          f"gt={len(gt)}, pred={len(pred)}")

    scores = []
    for gt_span in gt:
        best = max(_score_span_pair(gt_span, pred_span) for pred_span in pred)
        scores.append(best)

    return FieldScore("source_spans", sum(scores) / len(scores), "best_match",
                      f"n_gt={len(gt)}, n_pred={len(pred)}")


def _score_span_pair(gt: SourceSpan, pred: SourceSpan) -> float:
    """Score a pair of source spans."""
    sub_scores = []

    if gt.section is not None or pred.section is not None:
        sub_scores.append(compare_string_fuzzy(gt.section, pred.section))

    if gt.label_in_paper is not None or pred.label_in_paper is not None:
        sub_scores.append(compare_string_exact(gt.label_in_paper, pred.label_in_paper))

    if gt.text_context is not None or pred.text_context is not None:
        sub_scores.append(compare_text_similarity(gt.text_context, pred.text_context))

    gt_tables = set(gt.table_ids)
    pred_tables = set(pred.table_ids)
    if gt_tables or pred_tables:
        if gt_tables and pred_tables:
            overlap = len(gt_tables & pred_tables)
            union = len(gt_tables | pred_tables)
            sub_scores.append(overlap / union)
        else:
            sub_scores.append(0.0)

    if not sub_scores:
        return 1.0
    return sum(sub_scores) / len(sub_scores)


def score_equation_fields(
    gt: Equation,
    pred: Equation,
    config: ScoringConfig | None = None,
) -> dict[str, FieldScore]:
    """Score all fields of a matched equation pair."""
    from bench_score.latex_compare import compare_latex

    if config is None:
        config = ScoringConfig()

    fields: dict[str, FieldScore] = {}

    fields["equation_latex"] = compare_latex(gt.equation_latex, pred.equation_latex)
    fields["equation_name"] = FieldScore(
        "equation_name",
        compare_string_fuzzy(gt.equation_name, pred.equation_name),
        "fuzzy_match",
    )
    fields["equation_description"] = FieldScore(
        "equation_description",
        compare_text_similarity(gt.equation_description, pred.equation_description),
        "text_similarity",
    )
    fields["variables"] = compare_variables(gt.variables, pred.variables)
    fields["parameters"] = compare_parameters(gt.parameters, pred.parameters)
    fields["assumptions"] = compare_assumptions(gt.assumptions, pred.assumptions)
    fields["source_spans"] = compare_source_spans(gt.source_spans, pred.source_spans)

    return fields
