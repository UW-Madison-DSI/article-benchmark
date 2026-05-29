"""Core data types for the scoring framework."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class Variable:
    symbol: str
    name: str = ""
    unit: str | None = None
    description: str | None = None


@dataclass
class Parameter:
    symbol: str
    name: str | None = None
    value: float | str | None = None
    unit: str | None = None
    source: str | None = None
    bounds: dict[str, float | None] | None = None


@dataclass
class SourceSpan:
    section: str | None = None
    label_in_paper: str | None = None
    page: int | None = None
    text_context: str | None = None
    figure_ids: list[str] = field(default_factory=list)
    table_ids: list[str] = field(default_factory=list)
    supplement_ids: list[str] = field(default_factory=list)


@dataclass
class Equation:
    equation_local_id: str
    equation_name: str
    equation_description: str
    equation_latex: str | None = None
    equation_sympy: str | None = None
    variables: list[Variable] = field(default_factory=list)
    parameters: list[Parameter] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)
    source_spans: list[SourceSpan] = field(default_factory=list)
    confidence: float | None = None


@dataclass
class Paper:
    doi: str | None
    title: str
    mechanistic_equations: list[Equation] = field(default_factory=list)
    ml_models: list[dict[str, Any]] = field(default_factory=list)
    abstract_text: str | None = None
    publication_year: int | None = None
    source_url: str | None = None


@dataclass
class FieldScore:
    field_name: str
    score: float
    method: str
    detail: str = ""

    def __repr__(self) -> str:
        return f"FieldScore({self.field_name}={self.score:.3f}, {self.method})"


@dataclass
class ScoringConfig:
    latex_weight: float = 0.35
    variables_weight: float = 0.15
    parameters_weight: float = 0.15
    name_weight: float = 0.10
    description_weight: float = 0.10
    source_spans_weight: float = 0.10
    assumptions_weight: float = 0.05
    detection_f1_weight: float = 0.4
    quality_weight: float = 0.6
    alignment_threshold: float = 0.3

    @property
    def field_weights(self) -> dict[str, float]:
        return {
            "equation_latex": self.latex_weight,
            "variables": self.variables_weight,
            "parameters": self.parameters_weight,
            "equation_name": self.name_weight,
            "equation_description": self.description_weight,
            "source_spans": self.source_spans_weight,
            "assumptions": self.assumptions_weight,
        }


@dataclass
class EquationScore:
    gt_id: str
    pred_id: str | None
    field_scores: dict[str, FieldScore]
    overall: float

    @property
    def matched(self) -> bool:
        return self.pred_id is not None


@dataclass
class PaperScore:
    doi: str | None
    title: str
    equation_detection_precision: float
    equation_detection_recall: float
    equation_detection_f1: float
    equation_scores: list[EquationScore]
    mean_equation_score: float
    overall: float
    n_gt_equations: int
    n_pred_equations: int
    n_matched: int


@dataclass
class SystemScore:
    papers: list[PaperScore]
    mean_detection_f1: float
    mean_equation_score: float
    overall: float
    n_papers: int
    n_total_equations: int


def _parse_variable(d: dict[str, Any]) -> Variable:
    return Variable(
        symbol=d.get("symbol") or d.get("name", ""),
        name=d.get("name", ""),
        unit=d.get("unit"),
        description=d.get("description"),
    )


def _parse_parameter(d: dict[str, Any]) -> Parameter:
    value = d.get("value")
    if isinstance(value, str):
        try:
            value = float(value)
        except (ValueError, TypeError):
            pass
    return Parameter(
        symbol=d.get("symbol", ""),
        name=d.get("name"),
        value=value,
        unit=d.get("unit"),
        source=d.get("source"),
        bounds=d.get("bounds"),
    )


def _parse_source_span(d: dict[str, Any]) -> SourceSpan:
    return SourceSpan(
        section=d.get("section"),
        label_in_paper=d.get("label_in_paper"),
        page=d.get("page"),
        text_context=d.get("text_context"),
        figure_ids=d.get("figure_ids", []),
        table_ids=d.get("table_ids", []),
        supplement_ids=d.get("supplement_ids", []),
    )


def _parse_equation(d: dict[str, Any]) -> Equation:
    return Equation(
        equation_local_id=d.get("equation_local_id", ""),
        equation_name=d.get("equation_name", ""),
        equation_description=d.get("equation_description", ""),
        equation_latex=d.get("equation_latex"),
        equation_sympy=d.get("equation_sympy"),
        variables=[_parse_variable(v) for v in d.get("variables", [])],
        parameters=[_parse_parameter(p) for p in d.get("parameters", [])],
        assumptions=d.get("assumptions", []),
        source_spans=[_parse_source_span(s) for s in d.get("source_spans", [])],
        confidence=d.get("confidence"),
    )


def load_paper(path: Path | str) -> Paper:
    """Load a paper from a DB-format JSON file."""
    path = Path(path)
    with path.open() as f:
        data = json.load(f)

    paper_data = data.get("paper", {})
    return Paper(
        doi=paper_data.get("doi"),
        title=paper_data.get("title", ""),
        abstract_text=paper_data.get("abstract_text"),
        publication_year=paper_data.get("publication_year"),
        source_url=paper_data.get("source_url"),
        mechanistic_equations=[
            _parse_equation(eq)
            for eq in data.get("mechanistic_equations", [])
        ],
        ml_models=data.get("ml_models", []),
    )
