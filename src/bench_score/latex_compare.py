"""Three-tier LaTeX comparison: normalize -> SymPy equivalence -> token similarity."""

from __future__ import annotations

import difflib
import re
import signal
from contextlib import contextmanager
from typing import Generator

from bench_score.types import FieldScore


@contextmanager
def _timeout(seconds: int) -> Generator[None, None, None]:
    """Context manager that raises TimeoutError after `seconds`."""
    def _handler(signum: int, frame: object) -> None:
        raise TimeoutError

    old = signal.signal(signal.SIGALRM, _handler)
    signal.alarm(seconds)
    try:
        yield
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old)


def split_condition(latex: str) -> tuple[str, str]:
    """Split a LaTeX expression into (equation, condition).

    Handles patterns like: ``expr \\quad\\text{for } x > 0``
    Returns (equation_part, condition_part). condition_part is empty string
    if no condition clause found.
    """
    patterns = [
        r'\s*\\quad\s*\\text\s*\{',
        r'\s*\\qquad\s*\\text\s*\{',
        r'\s*,\s*\\text\s*\{\s*(?:for|where|when|if)\b',
        r'\s*\\quad\s*(?:for|where|when|if)\b',
    ]
    for pat in patterns:
        m = re.search(pat, latex)
        if m:
            return latex[:m.start()].rstrip(), latex[m.start():].strip()
    return latex, ""


def normalize_latex(latex: str) -> str:
    """Deterministic normalization of a LaTeX expression.

    Handles formatting differences without changing mathematical meaning.
    """
    s = latex

    # 1. Unify text commands: \text{X} and \mathrm{X} -> plain text
    #    For single-word identifiers, just strip the command.
    #    For multi-word, collapse to lowercase alphanumeric.
    def _replace_text_cmd(m: re.Match) -> str:
        content = m.group(1)
        collapsed = re.sub(r'[^a-zA-Z0-9]', '', content).lower()
        return collapsed

    s = re.sub(r'\\text\s*\{([^}]*)\}', _replace_text_cmd, s)
    s = re.sub(r'\\mathrm\s*\{([^}]*)\}', _replace_text_cmd, s)
    s = re.sub(r'\\mathbf\s*\{([^}]*)\}', _replace_text_cmd, s)
    s = re.sub(r'\\mathit\s*\{([^}]*)\}', _replace_text_cmd, s)
    s = re.sub(r'\\operatorname\s*\{([^}]*)\}', _replace_text_cmd, s)

    # 2. Strip spacing commands
    s = re.sub(r'\\[,;!]', '', s)
    s = re.sub(r'\\quad', '', s)
    s = re.sub(r'\\qquad', '', s)

    # 3. Normalize delimiters
    s = s.replace(r'\left(', '(')
    s = s.replace(r'\right)', ')')
    s = s.replace(r'\left[', '[')
    s = s.replace(r'\right]', ']')
    s = s.replace(r'\left|', '|')
    s = s.replace(r'\right|', '|')
    s = s.replace(r'\left.', '')
    s = s.replace(r'\right.', '')
    s = s.replace(r'\bigl(', '(')
    s = s.replace(r'\bigr)', ')')

    # 4. Normalize operators
    s = s.replace(r'\times', '*')
    s = s.replace(r'\cdot', '*')

    # 5. Strip uncertainty annotations: (\pm X) or \pm
    s = re.sub(r'\(\s*\\pm\s*[^)]*\)', '', s)

    # 6. Strip percent notation artifacts
    s = re.sub(r'\(\s*\\?%\s*\)', '', s)

    # 7. Canonicalize subscript braces: N_0 -> N_{0} (single char without braces)
    s = re.sub(r'_([A-Za-z0-9])(?![A-Za-z0-9{])', r'_{\1}', s)

    # 8. Collapse whitespace
    s = re.sub(r'\s+', '', s)

    return s


_TOKEN_RE = re.compile(
    r'\\[a-zA-Z]+'           # LaTeX commands
    r'|[a-zA-Z][a-zA-Z0-9]*' # identifiers
    r'|\d+\.?\d*'             # numbers
    r'|[+\-*/=(){}^_|,\[\]]' # operators and delimiters
    r'|\S'                    # anything else
)


def tokenize_latex(latex: str) -> list[str]:
    """Tokenize a normalized LaTeX string into meaningful tokens."""
    return _TOKEN_RE.findall(latex)


def token_similarity(latex_a: str, latex_b: str) -> float:
    """Compute token-level similarity between two LaTeX expressions."""
    norm_a = normalize_latex(latex_a)
    norm_b = normalize_latex(latex_b)
    tokens_a = tokenize_latex(norm_a)
    tokens_b = tokenize_latex(norm_b)
    if not tokens_a and not tokens_b:
        return 1.0
    if not tokens_a or not tokens_b:
        return 0.0
    return difflib.SequenceMatcher(None, tokens_a, tokens_b).ratio()


def try_sympy_equivalence(latex_a: str, latex_b: str, timeout_sec: int = 2) -> float | None:
    """Attempt symbolic equivalence check via SymPy.

    Returns 1.0 if equivalent, 0.0 if provably different, None if parsing fails.
    """
    try:
        from sympy.parsing.latex import parse_latex
        from sympy import simplify, SympifyError
    except ImportError:
        return None

    norm_a = normalize_latex(latex_a)
    norm_b = normalize_latex(latex_b)

    # Extract RHS if equation has = sign
    def _get_rhs(expr_str: str) -> str:
        if '=' in expr_str:
            parts = expr_str.split('=', 1)
            return parts[1].strip() if len(parts) == 2 else expr_str
        return expr_str

    rhs_a = _get_rhs(norm_a)
    rhs_b = _get_rhs(norm_b)

    try:
        with _timeout(timeout_sec):
            expr_a = parse_latex(rhs_a)
            expr_b = parse_latex(rhs_b)
            diff = simplify(expr_a - expr_b)
            return 1.0 if diff == 0 else 0.0
    except (SympifyError, Exception):
        return None


def compare_latex(gt: str | None, pred: str | None) -> FieldScore:
    """Compare two LaTeX equations using the three-tier pipeline.

    Tier 1: Normalized string match
    Tier 2: SymPy symbolic equivalence
    Tier 3: Token-level similarity fallback
    """
    if gt is None and pred is None:
        return FieldScore("equation_latex", 1.0, "both_null")
    if gt is None or pred is None:
        return FieldScore("equation_latex", 0.0, "one_null",
                          f"gt={'null' if gt is None else 'present'}, "
                          f"pred={'null' if pred is None else 'present'}")

    gt_eq, _ = split_condition(gt)
    pred_eq, _ = split_condition(pred)

    gt_norm = normalize_latex(gt_eq)
    pred_norm = normalize_latex(pred_eq)

    if gt_norm == pred_norm:
        return FieldScore("equation_latex", 1.0, "normalized_exact")

    sympy_result = try_sympy_equivalence(gt_eq, pred_eq)
    if sympy_result is not None:
        method = "sympy_equivalent" if sympy_result == 1.0 else "sympy_different"
        return FieldScore("equation_latex", sympy_result, method)

    sim = token_similarity(gt_eq, pred_eq)
    return FieldScore("equation_latex", sim, "token_similarity",
                      f"token_sim={sim:.3f}")
