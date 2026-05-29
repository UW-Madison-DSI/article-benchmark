"""Compose equation templates into synthetic paper ground truth files.

Selects equation subsets from the template library, assigns paper metadata,
and writes ground truth JSON in DB format ready for scoring.
"""

from __future__ import annotations

import json
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any

TEMPLATES_DIR = Path(__file__).parent.parent / "templates"
OUTPUT_DIR = Path(__file__).parent.parent / "benchmark" / "synthetic" / "pilot"

DIFFICULTY_TIERS = {
    "easy": {"min_equations": 1, "max_equations": 2},
    "medium": {"min_equations": 3, "max_equations": 5},
    "hard": {"min_equations": 5, "max_equations": 8},
    "adversarial": {"min_equations": 3, "max_equations": 6},
}

JOURNALS = [
    "Journal of Dairy Science",
    "International Journal of Food Microbiology",
    "Food Microbiology",
    "Applied and Environmental Microbiology",
    "International Dairy Journal",
    "Journal of Food Protection",
]

TITLE_TEMPLATES = [
    "Predictive modeling of {organism} growth in {product} during {process}",
    "A {model_type} approach to estimate {target} in {product}",
    "Development of a quality assessment model for {organism} in {product}",
    "Modeling the effect of {factor} on {organism} growth in {product}",
    "Quantitative assessment of {target} using {model_type} models",
    "Shelf life prediction of {product} based on {organism} growth kinetics",
    "Temperature-dependent growth of {organism} in {product}: a {model_type} study",
    "Growth kinetics of {organism} during {process} of {product}",
]

ORGANISMS = [
    "spoilage bacteria", "lactic acid bacteria",
    "psychrotrophic bacteria", "spore-forming bacteria",
    "mesophilic flora", "starter cultures",
    "dairy microflora", "quality indicator organisms",
]

PRODUCTS = [
    "Gouda cheese", "Cheddar cheese", "raw milk",
    "pasteurized milk", "yogurt", "fresh cheese",
    "mozzarella", "cream cheese", "butter",
]

PROCESSES = [
    "refrigerated storage", "aging", "ripening",
    "cold chain distribution", "thermal processing",
    "fermentation", "shelf life storage",
]

FACTORS = ["temperature", "pH", "water activity", "salt concentration", "storage time"]
TARGETS = ["spoilage risk", "microbial growth", "shelf life", "pathogen concentration", "product safety"]
MODEL_TYPES = ["predictive microbiology", "Monte Carlo simulation", "cardinal parameter", "gamma concept"]


def load_templates(domain: str) -> list[dict[str, Any]]:
    """Load equation templates for a given domain."""
    path = TEMPLATES_DIR / f"{domain}.json"
    with path.open() as f:
        data = json.load(f)
    return data["templates"]


def generate_title(templates: list[dict]) -> str:
    """Generate a plausible paper title based on selected templates."""
    template = random.choice(TITLE_TEMPLATES)
    return template.format(
        organism=random.choice(ORGANISMS),
        product=random.choice(PRODUCTS),
        process=random.choice(PROCESSES),
        factor=random.choice(FACTORS),
        target=random.choice(TARGETS),
        model_type=random.choice(MODEL_TYPES),
    )


def select_equations(
    templates: list[dict],
    difficulty: str,
    rng: random.Random,
) -> list[dict]:
    """Select a coherent subset of equations based on difficulty tier."""
    tier = DIFFICULTY_TIERS[difficulty]
    n = rng.randint(tier["min_equations"], tier["max_equations"])
    n = min(n, len(templates))

    if difficulty == "easy":
        simple_types = {"primary_growth_model", "empirical_relationship", "inactivation_model"}
        candidates = [t for t in templates if t.get("equation_type") in simple_types]
        if len(candidates) < n:
            candidates = templates
        return rng.sample(candidates, n)

    if difficulty in ("medium", "hard"):
        gamma_templates = [t for t in templates if "gamma" in t.get("equation_type", "")]
        composite = [t for t in templates if t.get("equation_type") == "secondary_model_composite"]
        primary = [t for t in templates if t.get("equation_type") == "primary_growth_model"]
        other = [t for t in templates if t not in gamma_templates + composite + primary]

        selected = []
        if composite and rng.random() > 0.3:
            selected.extend(rng.sample(composite, min(1, len(composite))))
            n_gamma = min(rng.randint(1, 3), len(gamma_templates))
            selected.extend(rng.sample(gamma_templates, n_gamma))
        if primary and len(selected) < n:
            selected.extend(rng.sample(primary, min(1, len(primary))))
        remaining = [t for t in templates if t not in selected]
        while len(selected) < n and remaining:
            pick = rng.choice(remaining)
            selected.append(pick)
            remaining.remove(pick)
        return selected[:n]

    # adversarial: mix unrelated equation types
    return rng.sample(templates, n)


def template_to_db_equation(template: dict, eq_index: int) -> dict:
    """Convert a template to DB-format equation structure."""
    return {
        "equation_local_id": f"eq{eq_index}",
        "equation_name": template["equation_name"],
        "equation_description": template["equation_description"],
        "equation_latex": template["equation_latex"],
        "equation_sympy": None,
        "variables": template.get("variables", []),
        "parameters": [
            {k: v for k, v in p.items() if k in ("symbol", "name", "value", "unit", "source", "bounds")}
            for p in template.get("parameters", [])
        ],
        "assumptions": template.get("assumptions", []),
        "source_spans": [
            {
                "section": "MATERIALS AND METHODS",
                "label_in_paper": f"[{eq_index}]",
                "page": None,
                "text_context": template["equation_description"],
                "figure_ids": [],
                "table_ids": [],
                "supplement_ids": [],
            }
        ],
    }


def generate_paper(
    paper_id: int,
    templates: list[dict],
    difficulty: str,
    rng: random.Random,
) -> dict:
    """Generate a complete ground truth paper in DB format."""
    selected = select_equations(templates, difficulty, rng)
    title = generate_title(selected)

    equations = [
        template_to_db_equation(tmpl, i + 1)
        for i, tmpl in enumerate(selected)
    ]

    paper = {
        "doi": f"10.0000/synthetic-pilot-{paper_id:03d}",
        "openalex_id": None,
        "title": title,
        "abstract_text": None,
        "publication_year": rng.randint(2018, 2025),
        "publication_date": None,
        "type": None,
        "language": "en",
        "source_url": None,
        "primary_landing_page_url": None,
        "primary_pdf_url": None,
        "is_oa": None,
        "cited_by_count": None,
    }

    return {
        "paper": paper,
        "mechanistic_equations": equations,
        "ml_models": [],
        "_metadata": {
            "difficulty": difficulty,
            "domain": "microbial_growth",
            "template_ids": [t["template_id"] for t in selected],
            "generator_version": "0.1.0",
        },
    }


def main() -> None:
    templates = load_templates("microbial_growth")
    rng = random.Random(42)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    difficulty_distribution = (
        [("easy", i) for i in range(3)] +
        [("medium", i) for i in range(5)] +
        [("hard", i) for i in range(4)] +
        [("adversarial", i) for i in range(2)]
    )

    for paper_idx, (difficulty, _) in enumerate(difficulty_distribution, start=1):
        paper = generate_paper(paper_idx, templates, difficulty, rng)
        out_path = OUTPUT_DIR / f"Synthetic{paper_idx:03d}_ground_truth.json"
        with out_path.open("w") as f:
            json.dump(paper, f, indent=2, ensure_ascii=False)
        n_eq = len(paper["mechanistic_equations"])
        print(f"  {out_path.name}  difficulty={difficulty:12s}  equations={n_eq}  "
              f"templates={paper['_metadata']['template_ids']}")

    print(f"\nGenerated {len(difficulty_distribution)} ground truth files in {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
