# Article Benchmark

Synthetic benchmark dataset for evaluating the [AG Model Database](https://github.com/UW-Madison-DSI/ag-model-database) extraction pipeline. The pipeline uses LangGraph agents to extract mechanistic equations from dairy science papers into structured JSON. This project generates synthetic papers with known ground truth so we can measure extraction accuracy at scale.

## Why synthetic?

Manual curation of ground-truth papers takes ~40 hours each. We currently have 6 curated papers (44 equations), which is not enough to detect 5-10% accuracy differences between pipeline versions. Synthetic generation flips the problem: define the expected output first (ground truth JSON), then generate paper text that contains exactly that information. Ground truth is correct by construction.

**Trade-off:** Synthetic papers are "LLM-shaped" (cleaner notation, more predictable structure than real papers), so extraction scores will be inflated vs. real-paper performance. The benchmark is useful for relative comparisons between pipeline versions, not absolute accuracy estimates. A real-paper calibration set (Phase 1) validates that synthetic rankings transfer.

## Current status

| Phase | Status | Description |
|-------|--------|-------------|
| Phase 0: Scoring | Complete | LaTeX comparison, field-level scoring, 81 tests passing |
| Phase 1: Real papers | Ongoing | 6 existing curated papers, target 10-12 |
| Phase 2: Pilot | In progress | 14 synthetic papers, 55 equations, 4 difficulty tiers |
| Phase 3: Scale-up | Not started | 75 papers across 6-8 domains |

## Project structure

```
article_benchmark/
  src/bench_score/        # Scoring framework
    latex_compare.py      #   LaTeX normalization + SymPy symbolic equivalence
    field_compare.py      #   Field-type-aware comparison (numeric, text, arrays)
    align.py              #   Equation alignment between extracted and ground truth
    score.py              #   Paper-level and system-level metric aggregation
    report.py             #   Human-readable scoring reports
    cli.py                #   CLI entry point (bench-score command)
    types.py              #   Shared type definitions
  generation/             # Synthetic paper generation scripts
    generate_ground_truth.py   # Compose ground truth JSON from templates
    generate_paper_text.py     # Generate realistic paper text from ground truth
  templates/
    microbial_growth.json # 18 equation templates for the microbial growth domain
  benchmark/synthetic/
    pilot/                # 14 pilot papers (text + ground truth + prompts)
  examples/benchmark/     # 6 manually curated real papers (PDFs + ground truth)
  tests/                  # pytest suite (81 tests)
  slides.html             # Project plan slide deck (UW-Madison branded)
  performance.html        # Pilot generation quality slide deck
  PLAN.md                 # Detailed phased project plan
```

## Setup

Requires Python 3.11+ and [uv](https://docs.astral.sh/uv/).

```bash
uv sync
```

## Usage

Run the scoring framework against a paper:

```bash
uv run bench-score <extracted.json> <ground_truth.json>
```

Run the test suite:

```bash
uv run pytest
```

## Scoring approach

The scoring framework handles five field types:

- **LaTeX**: Normalization + SymPy symbolic equivalence, with token edit distance fallback for unparseable expressions
- **Identifiers**: Normalized string match
- **Numeric values**: Relative tolerance (1%)
- **Free text**: Embedding cosine similarity
- **Arrays**: Set-based F1 with element-level matching

All 6 existing curated papers self-score 1.0 (scorer correctly identifies identical extractions).

## Pilot papers

The 14 pilot papers span four difficulty tiers designed to test different extraction challenges:

| Tier | Papers | Avg equations | Characteristics |
|------|--------|---------------|-----------------|
| Easy | 3 | 1.0 | Clear subsections, single displayed equation, parameters defined inline |
| Medium | 5 | 3.4 | Multiple equations with cross-references, parameter tables |
| Hard | 4 | 6.8 | Dense equation systems, 11-12 subsections |
| Adversarial | 2 | 4.0 | No subsection headers, equations woven into prose, variable aliasing |

93% of ground-truth parameter values appear verbatim in the generated text. 15 of 18 equation templates are exercised across the pilot.

## Next steps

1. Run the extraction pipeline on all 14 pilot papers
2. Score extracted output against ground truth
3. Validate difficulty separation (easy > medium > hard > adversarial)
4. If scores show meaningful separation, proceed to 75-paper generation across 6-8 domains
