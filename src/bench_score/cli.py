"""CLI entry point for bench-score."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from bench_score.report import format_paper_report, format_system_json, format_system_report
from bench_score.score import score_paper, score_system
from bench_score.types import Paper, ScoringConfig, load_paper


def _find_matching_files(
    gt_dir: Path,
    pred_dir: Path,
) -> list[tuple[Path, Path]]:
    """Find matching ground truth and prediction files by filename."""
    gt_files = {f.name: f for f in sorted(gt_dir.glob("*.json"))}
    pred_files = {f.name: f for f in sorted(pred_dir.glob("*.json"))}

    pairs = []
    for name in sorted(gt_files.keys()):
        if name in pred_files:
            pairs.append((gt_files[name], pred_files[name]))
        else:
            print(f"Warning: no prediction file for {name}", file=sys.stderr)

    for name in sorted(pred_files.keys()):
        if name not in gt_files:
            print(f"Warning: no ground truth file for {name}", file=sys.stderr)

    return pairs


def cmd_score(args: argparse.Namespace) -> None:
    """Score a single paper."""
    config = ScoringConfig()
    gt = load_paper(args.gt)
    pred = load_paper(args.pred)
    ps = score_paper(gt, pred, config)

    if args.format == "json":
        ss = score_system([(gt, pred)], config)
        print(format_system_json(ss))
    else:
        print(format_paper_report(ps))


def cmd_batch(args: argparse.Namespace) -> None:
    """Score all matching papers in two directories."""
    config = ScoringConfig()
    gt_dir = Path(args.gt_dir)
    pred_dir = Path(args.pred_dir)

    pairs = _find_matching_files(gt_dir, pred_dir)
    if not pairs:
        print("No matching files found.", file=sys.stderr)
        sys.exit(1)

    gt_pred = [(load_paper(gt), load_paper(pred)) for gt, pred in pairs]
    ss = score_system(gt_pred, config)

    output = format_system_json(ss) if args.format == "json" else format_system_report(ss)

    if args.output:
        Path(args.output).write_text(output)
        print(f"Report written to {args.output}")
    else:
        print(output)


def cmd_validate(args: argparse.Namespace) -> None:
    """Self-score: compare ground truth against itself. All scores should be 1.0."""
    config = ScoringConfig()
    gt_dir = Path(args.gt_dir)

    gt_files = sorted(gt_dir.glob("*.json"))
    if not gt_files:
        print(f"No JSON files found in {gt_dir}", file=sys.stderr)
        sys.exit(1)

    print(f"Validating scorer against {len(gt_files)} ground truth files...\n")

    gt_pred = []
    for f in gt_files:
        paper = load_paper(f)
        gt_pred.append((paper, paper))

    ss = score_system(gt_pred, config)

    all_perfect = True
    for ps in ss.papers:
        status = "OK" if abs(ps.overall - 1.0) < 1e-6 else "FAIL"
        if status == "FAIL":
            all_perfect = False
        print(f"  [{status}] {ps.title[:60]:60s}  score={ps.overall:.4f}  "
              f"F1={ps.equation_detection_f1:.4f}  "
              f"quality={ps.mean_equation_score:.4f}")

    print(f"\nSystem: overall={ss.overall:.4f}  "
          f"mean_F1={ss.mean_detection_f1:.4f}  "
          f"mean_quality={ss.mean_equation_score:.4f}")

    if all_perfect:
        print("\nAll papers scored 1.0 against themselves. Scorer is consistent.")
    else:
        print("\nSome papers did not score 1.0. Investigate field comparisons.")
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="bench-score",
        description="Score extraction output against ground truth",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    score_p = subparsers.add_parser("score", help="Score a single paper")
    score_p.add_argument("--gt", required=True, help="Ground truth JSON path")
    score_p.add_argument("--pred", required=True, help="Prediction JSON path")
    score_p.add_argument("--format", choices=["text", "json"], default="text")

    batch_p = subparsers.add_parser("batch", help="Score a batch of papers")
    batch_p.add_argument("--gt-dir", required=True, help="Ground truth directory")
    batch_p.add_argument("--pred-dir", required=True, help="Prediction directory")
    batch_p.add_argument("--format", choices=["text", "json"], default="text")
    batch_p.add_argument("--output", help="Output file path")

    val_p = subparsers.add_parser("validate", help="Self-score ground truth (should all be 1.0)")
    val_p.add_argument("--gt-dir", required=True, help="Ground truth directory")

    args = parser.parse_args()

    commands = {
        "score": cmd_score,
        "batch": cmd_batch,
        "validate": cmd_validate,
    }
    commands[args.command](args)


if __name__ == "__main__":
    main()
