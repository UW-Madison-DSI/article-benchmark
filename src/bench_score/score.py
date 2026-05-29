"""Paper-level and system-level score aggregation."""

from __future__ import annotations

from bench_score.align import align_equations
from bench_score.field_compare import score_equation_fields
from bench_score.types import (
    Equation,
    EquationScore,
    FieldScore,
    Paper,
    PaperScore,
    ScoringConfig,
    SystemScore,
)


def score_equation(
    gt: Equation,
    pred: Equation,
    config: ScoringConfig | None = None,
) -> EquationScore:
    """Score a single matched equation pair across all fields."""
    if config is None:
        config = ScoringConfig()

    field_scores = score_equation_fields(gt, pred, config)

    weights = config.field_weights
    weighted_sum = 0.0
    total_weight = 0.0
    for field_name, weight in weights.items():
        if field_name in field_scores:
            weighted_sum += weight * field_scores[field_name].score
            total_weight += weight

    overall = weighted_sum / total_weight if total_weight > 0 else 0.0

    return EquationScore(
        gt_id=gt.equation_local_id,
        pred_id=pred.equation_local_id,
        field_scores=field_scores,
        overall=overall,
    )


def score_paper(
    gt: Paper,
    pred: Paper,
    config: ScoringConfig | None = None,
) -> PaperScore:
    """Score a paper: align equations, then score each matched pair."""
    if config is None:
        config = ScoringConfig()

    pairs = align_equations(
        gt.mechanistic_equations,
        pred.mechanistic_equations,
        threshold=config.alignment_threshold,
    )

    equation_scores: list[EquationScore] = []
    n_matched = 0

    for gt_eq, pred_eq in pairs:
        if gt_eq is not None and pred_eq is not None:
            eq_score = score_equation(gt_eq, pred_eq, config)
            equation_scores.append(eq_score)
            n_matched += 1
        elif gt_eq is not None:
            equation_scores.append(EquationScore(
                gt_id=gt_eq.equation_local_id,
                pred_id=None,
                field_scores={},
                overall=0.0,
            ))
        elif pred_eq is not None:
            equation_scores.append(EquationScore(
                gt_id="",
                pred_id=pred_eq.equation_local_id,
                field_scores={},
                overall=0.0,
            ))

    n_gt = len(gt.mechanistic_equations)
    n_pred = len(pred.mechanistic_equations)

    precision = n_matched / n_pred if n_pred > 0 else (1.0 if n_gt == 0 else 0.0)
    recall = n_matched / n_gt if n_gt > 0 else (1.0 if n_pred == 0 else 0.0)
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

    matched_scores = [es.overall for es in equation_scores if es.matched]
    mean_eq_score = sum(matched_scores) / len(matched_scores) if matched_scores else 0.0

    overall = (config.detection_f1_weight * f1 +
               config.quality_weight * mean_eq_score)

    return PaperScore(
        doi=gt.doi,
        title=gt.title,
        equation_detection_precision=precision,
        equation_detection_recall=recall,
        equation_detection_f1=f1,
        equation_scores=equation_scores,
        mean_equation_score=mean_eq_score,
        overall=overall,
        n_gt_equations=n_gt,
        n_pred_equations=n_pred,
        n_matched=n_matched,
    )


def score_system(
    gt_pred_pairs: list[tuple[Paper, Paper]],
    config: ScoringConfig | None = None,
) -> SystemScore:
    """Aggregate scores across all papers."""
    if config is None:
        config = ScoringConfig()

    paper_scores = [score_paper(gt, pred, config) for gt, pred in gt_pred_pairs]

    if not paper_scores:
        return SystemScore(
            papers=[],
            mean_detection_f1=0.0,
            mean_equation_score=0.0,
            overall=0.0,
            n_papers=0,
            n_total_equations=0,
        )

    mean_f1 = sum(ps.equation_detection_f1 for ps in paper_scores) / len(paper_scores)
    mean_eq = sum(ps.mean_equation_score for ps in paper_scores) / len(paper_scores)
    mean_overall = sum(ps.overall for ps in paper_scores) / len(paper_scores)
    total_eqs = sum(ps.n_gt_equations for ps in paper_scores)

    return SystemScore(
        papers=paper_scores,
        mean_detection_f1=mean_f1,
        mean_equation_score=mean_eq,
        overall=mean_overall,
        n_papers=len(paper_scores),
        n_total_equations=total_eqs,
    )
