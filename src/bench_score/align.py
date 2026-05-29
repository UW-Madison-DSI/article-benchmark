"""Bipartite equation alignment using the Hungarian algorithm."""

from __future__ import annotations

from bench_score.field_compare import compare_string_fuzzy
from bench_score.latex_compare import normalize_latex, token_similarity
from bench_score.types import Equation


def equation_similarity(a: Equation, b: Equation) -> float:
    """Compute similarity between two equations for alignment purposes.

    Weighted combination: LaTeX (0.5), name (0.3), variable symbols (0.2).
    """
    latex_sim = 0.0
    if a.equation_latex and b.equation_latex:
        latex_sim = token_similarity(a.equation_latex, b.equation_latex)
    elif a.equation_latex is None and b.equation_latex is None:
        latex_sim = 1.0

    name_sim = compare_string_fuzzy(a.equation_name, b.equation_name)

    a_syms = {normalize_latex(v.symbol) for v in a.variables}
    b_syms = {normalize_latex(v.symbol) for v in b.variables}
    if a_syms or b_syms:
        if a_syms and b_syms:
            var_sim = len(a_syms & b_syms) / len(a_syms | b_syms)
        else:
            var_sim = 0.0
    else:
        var_sim = 0.5

    return 0.5 * latex_sim + 0.3 * name_sim + 0.2 * var_sim


def _hungarian(cost_matrix: list[list[float]]) -> list[tuple[int, int]]:
    """Pure Python Hungarian algorithm for minimum-cost assignment.

    Operates on an n x m cost matrix. Returns list of (row, col) assignments.
    Handles rectangular matrices by padding to square.
    """
    n = len(cost_matrix)
    if n == 0:
        return []
    m = len(cost_matrix[0])
    if m == 0:
        return []

    size = max(n, m)
    pad_val = 1e9
    c = [[pad_val] * size for _ in range(size)]
    for i in range(n):
        for j in range(m):
            c[i][j] = cost_matrix[i][j]

    u = [0.0] * (size + 1)
    v = [0.0] * (size + 1)
    p = [0] * (size + 1)
    way = [0] * (size + 1)

    for i in range(1, size + 1):
        p[0] = i
        j0 = 0
        minv = [float('inf')] * (size + 1)
        used = [False] * (size + 1)

        while True:
            used[j0] = True
            i0 = p[j0]
            delta = float('inf')
            j1 = -1

            for j in range(1, size + 1):
                if not used[j]:
                    cur = c[i0 - 1][j - 1] - u[i0] - v[j]
                    if cur < minv[j]:
                        minv[j] = cur
                        way[j] = j0
                    if minv[j] < delta:
                        delta = minv[j]
                        j1 = j

            for j in range(size + 1):
                if used[j]:
                    u[p[j]] += delta
                    v[j] -= delta
                else:
                    minv[j] -= delta

            j0 = j1
            if p[j0] == 0:
                break

        while j0:
            p[j0] = p[way[j0]]
            j0 = way[j0]

    result = []
    for j in range(1, size + 1):
        if p[j] != 0 and p[j] - 1 < n and j - 1 < m:
            result.append((p[j] - 1, j - 1))

    return result


def align_equations(
    gt_equations: list[Equation],
    pred_equations: list[Equation],
    threshold: float = 0.3,
) -> list[tuple[Equation | None, Equation | None]]:
    """Align predicted equations to ground truth using bipartite matching.

    Returns list of (gt_eq, pred_eq) pairs:
    - (gt_eq, pred_eq) for matched pairs
    - (gt_eq, None) for unmatched ground truth (missed)
    - (None, pred_eq) for unmatched predictions (spurious)
    """
    if not gt_equations and not pred_equations:
        return []
    if not gt_equations:
        return [(None, eq) for eq in pred_equations]
    if not pred_equations:
        return [(eq, None) for eq in gt_equations]

    n_gt = len(gt_equations)
    n_pred = len(pred_equations)

    sim_matrix = [
        [equation_similarity(gt_equations[i], pred_equations[j]) for j in range(n_pred)]
        for i in range(n_gt)
    ]

    cost_matrix = [
        [1.0 - sim_matrix[i][j] for j in range(n_pred)]
        for i in range(n_gt)
    ]

    assignments = _hungarian(cost_matrix)

    matched_gt: set[int] = set()
    matched_pred: set[int] = set()
    pairs: list[tuple[Equation | None, Equation | None]] = []

    for gt_idx, pred_idx in assignments:
        if gt_idx < n_gt and pred_idx < n_pred:
            if sim_matrix[gt_idx][pred_idx] >= threshold:
                pairs.append((gt_equations[gt_idx], pred_equations[pred_idx]))
                matched_gt.add(gt_idx)
                matched_pred.add(pred_idx)

    for i in range(n_gt):
        if i not in matched_gt:
            pairs.append((gt_equations[i], None))

    for j in range(n_pred):
        if j not in matched_pred:
            pairs.append((None, pred_equations[j]))

    return pairs
