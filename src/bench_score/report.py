"""Human-readable report generation."""

from __future__ import annotations

import json
from dataclasses import asdict

from bench_score.types import PaperScore, SystemScore


def format_paper_report(ps: PaperScore) -> str:
    """Generate a text report for a single paper."""
    lines = []
    lines.append(f"Paper: {ps.title}")
    lines.append(f"  DOI: {ps.doi or 'N/A'}")
    lines.append(f"  Equations: {ps.n_gt_equations} ground truth, "
                 f"{ps.n_pred_equations} predicted, {ps.n_matched} matched")
    lines.append(f"  Detection: P={ps.equation_detection_precision:.3f}  "
                 f"R={ps.equation_detection_recall:.3f}  "
                 f"F1={ps.equation_detection_f1:.3f}")
    lines.append(f"  Mean equation quality: {ps.mean_equation_score:.3f}")
    lines.append(f"  Overall score: {ps.overall:.3f}")

    if ps.equation_scores:
        lines.append("")
        lines.append("  Equation details:")
        for es in ps.equation_scores:
            if es.matched:
                lines.append(f"    [{es.gt_id}] -> [{es.pred_id}]  "
                             f"overall={es.overall:.3f}")
                for fname, fs in sorted(es.field_scores.items()):
                    lines.append(f"      {fname:25s} {fs.score:.3f}  ({fs.method})")
            elif es.pred_id is None:
                lines.append(f"    [{es.gt_id}] -> MISSED")
            else:
                lines.append(f"    SPURIOUS -> [{es.pred_id}]")

    return "\n".join(lines)


def format_system_report(ss: SystemScore) -> str:
    """Generate a text report for the full system."""
    lines = []
    lines.append("=" * 70)
    lines.append("BENCHMARK SCORING REPORT")
    lines.append("=" * 70)
    lines.append("")
    lines.append(f"Papers scored: {ss.n_papers}")
    lines.append(f"Total ground truth equations: {ss.n_total_equations}")
    lines.append(f"Mean detection F1: {ss.mean_detection_f1:.3f}")
    lines.append(f"Mean equation quality: {ss.mean_equation_score:.3f}")
    lines.append(f"Overall system score: {ss.overall:.3f}")
    lines.append("")
    lines.append("-" * 70)

    for ps in ss.papers:
        lines.append("")
        lines.append(format_paper_report(ps))
        lines.append("")
        lines.append("-" * 70)

    return "\n".join(lines)


def format_system_json(ss: SystemScore) -> str:
    """Generate a JSON report for the full system."""
    data = {
        "n_papers": ss.n_papers,
        "n_total_equations": ss.n_total_equations,
        "mean_detection_f1": round(ss.mean_detection_f1, 4),
        "mean_equation_score": round(ss.mean_equation_score, 4),
        "overall": round(ss.overall, 4),
        "papers": [],
    }

    for ps in ss.papers:
        paper_data = {
            "doi": ps.doi,
            "title": ps.title,
            "n_gt_equations": ps.n_gt_equations,
            "n_pred_equations": ps.n_pred_equations,
            "n_matched": ps.n_matched,
            "detection_precision": round(ps.equation_detection_precision, 4),
            "detection_recall": round(ps.equation_detection_recall, 4),
            "detection_f1": round(ps.equation_detection_f1, 4),
            "mean_equation_score": round(ps.mean_equation_score, 4),
            "overall": round(ps.overall, 4),
            "equations": [],
        }

        for es in ps.equation_scores:
            eq_data = {
                "gt_id": es.gt_id,
                "pred_id": es.pred_id,
                "matched": es.matched,
                "overall": round(es.overall, 4),
                "fields": {
                    fname: {
                        "score": round(fs.score, 4),
                        "method": fs.method,
                    }
                    for fname, fs in es.field_scores.items()
                } if es.field_scores else {},
            }
            paper_data["equations"].append(eq_data)

        data["papers"].append(paper_data)

    return json.dumps(data, indent=2)
