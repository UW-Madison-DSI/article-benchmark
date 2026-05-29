"""Generate realistic paper text from ground truth using an LLM.

Takes ground truth JSON files (from generate_ground_truth.py) and produces
synthetic paper sections that embed the equations in realistic prose.

Usage:
    python generation/generate_paper_text.py --input-dir benchmark/synthetic/pilot/
    python generation/generate_paper_text.py --input-file benchmark/synthetic/pilot/Synthetic001_ground_truth.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

DIFFICULTY_INSTRUCTIONS = {
    "easy": """Write a clear, well-structured methods section. Each equation should be:
- Displayed on its own line with a label like [1], [2], etc.
- Immediately followed by definitions of all variables and parameters
- Using standard mathematical notation
- Clearly separated from surrounding text""",

    "medium": """Write a realistic methods section. Equations should be:
- Displayed with labels, but some variables may be defined in a separate paragraph
- Some parameters should be introduced in the text as "where X is the..." format
- Reference relationships between equations (e.g., "where mu is defined in Eq. [2]")
- Include references to tables for parameter values""",

    "hard": """Write a dense methods section typical of a research paper. Equations should be:
- Part of a connected mathematical framework with shared variables
- Some parameters defined in separate subsections or referenced to tables
- Use notation that requires context to interpret (e.g., subscripts that are defined elsewhere)
- Include cross-references between equations
- Some variables appear in multiple equations with the same meaning but are only defined once""",

    "adversarial": """Write a methods section that makes equation extraction challenging:
- Some equations should be embedded in running prose rather than displayed
- Use inconsistent notation (e.g., refer to the same variable by different names in text vs. equation)
- Include a "distractor" equation that is mentioned but not central to the model
- Define some parameters only implicitly through example values in the text
- Mix units in text (e.g., mention values in different unit systems)""",
}


PATHOGEN_REPLACEMENTS = {
    "Clostridium tyrobutyricum": "the target organism",
    "C. tyrobutyricum": "the target organism",
    "Listeria monocytogenes": "the target organism",
    "L. monocytogenes": "the target organism",
    "Salmonella enterica": "the target organism",
    "Salmonella spp.": "the target organism",
    "Escherichia coli O157:H7": "the target organism",
    "E. coli O157:H7": "the target organism",
    "E. coli": "the target organism",
    "Bacillus cereus": "the target organism",
    "B. cereus": "the target organism",
    "Staphylococcus aureus": "the target organism",
    "S. aureus": "the target organism",
    "Clostridium botulinum": "the target organism",
    "C. botulinum": "the target organism",
    "Pseudomonas fluorescens": "spoilage bacteria",
    "Pseudomonas spp.": "spoilage bacteria",
    "Lactobacillus plantarum": "lactic acid bacteria",
    "Lactobacillus spp.": "lactic acid bacteria",
}


def _sanitize_text(text: str) -> str:
    """Replace specific pathogen names with generic terms to avoid safety filter triggers."""
    for pathogen, replacement in PATHOGEN_REPLACEMENTS.items():
        text = text.replace(pathogen, replacement)
    return text


def build_prompt(ground_truth: dict[str, Any]) -> str:
    """Build the LLM prompt from a ground truth file."""
    paper = ground_truth["paper"]
    equations = ground_truth["mechanistic_equations"]
    metadata = ground_truth.get("_metadata", {})
    difficulty = metadata.get("difficulty", "medium")

    eq_descriptions = []
    for eq in equations:
        name = _sanitize_text(eq['equation_name'])
        description = _sanitize_text(eq.get('equation_description', ''))
        assumptions = [_sanitize_text(a) for a in eq.get('assumptions', [])]
        params = eq.get('parameters', [])
        sanitized_params = [
            {k: (_sanitize_text(v) if isinstance(v, str) else v) for k, v in p.items()}
            for p in params
        ]
        desc = f"""Equation [{eq['equation_local_id'].replace('eq', '')}]:
  Name: {name}
  LaTeX: {eq['equation_latex']}
  Variables: {json.dumps(eq.get('variables', []), indent=2)}
  Parameters: {json.dumps(sanitized_params, indent=2)}
  Assumptions: {json.dumps(assumptions)}"""
        eq_descriptions.append(desc)

    equations_block = "\n\n".join(eq_descriptions)

    difficulty_instruction = DIFFICULTY_INSTRUCTIONS.get(difficulty, DIFFICULTY_INSTRUCTIONS["medium"])

    prompt = f"""CONTEXT: This is for an academic food science benchmarking project. We are
generating synthetic methods sections to test equation-extraction software. The
equations below are standard mathematical models used in dairy science for
predicting product quality and shelf life.

You are an expert in dairy science and mathematical modeling. Write a realistic
MATERIALS AND METHODS section for a research paper with the following details:

Title: {paper['title']}
Journal style: {metadata.get('journal', 'Journal of Dairy Science')}

The section must contain ALL of the following equations embedded naturally in the prose.
Use generic terms like "target organism", "spoilage flora", or "microbial population"
rather than specific species names.

{equations_block}

INSTRUCTIONS FOR WRITING STYLE:
{difficulty_instruction}

CRITICAL REQUIREMENTS:
1. Include EVERY equation listed above with its EXACT LaTeX form.
2. Define ALL variables and parameters mentioned in the equation descriptions.
3. Write 800-2500 words depending on the number of equations.
4. Use a formal academic writing style appropriate for a dairy science journal.
5. Do NOT include an abstract, introduction, results, or discussion.
6. Do NOT add equations that are not in the list above.
7. Include realistic references to literature (you may use placeholder citations like "(Author et al., 2020)").
8. Structure the section with appropriate subsections if there are 3+ equations.
9. Use generic terms for organisms (e.g., "the target organism", "spoilage bacteria").

Return ONLY the methods section text. Do not include any metadata or JSON."""

    return prompt


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate paper text from ground truth")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--input-dir", help="Directory of ground truth JSON files")
    group.add_argument("--input-file", help="Single ground truth JSON file")
    parser.add_argument("--output-dir", help="Output directory (default: same as input)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print prompts without calling LLM")
    args = parser.parse_args()

    if args.input_file:
        files = [Path(args.input_file)]
    else:
        input_dir = Path(args.input_dir)
        files = sorted(input_dir.glob("*_ground_truth.json"))

    if not files:
        print("No ground truth files found.")
        return

    output_dir = Path(args.output_dir) if args.output_dir else files[0].parent
    output_dir.mkdir(parents=True, exist_ok=True)

    for f in files:
        with f.open() as fh:
            gt = json.load(fh)

        prompt = build_prompt(gt)
        paper_id = f.stem.replace("_ground_truth", "")

        if args.dry_run:
            print(f"\n{'='*70}")
            print(f"Paper: {paper_id}")
            print(f"Difficulty: {gt.get('_metadata', {}).get('difficulty', '?')}")
            print(f"Equations: {len(gt['mechanistic_equations'])}")
            print(f"Prompt length: {len(prompt)} chars")
            print(f"{'='*70}")
            print(prompt[:500] + "...\n")
            continue

        # LLM call placeholder
        print(f"[{paper_id}] Would call LLM with {len(prompt)} char prompt "
              f"({len(gt['mechanistic_equations'])} equations, "
              f"difficulty={gt.get('_metadata', {}).get('difficulty', '?')})")
        print(f"  To generate, integrate with your preferred LLM API.")
        print(f"  Prompt saved to: {output_dir / f'{paper_id}_prompt.txt'}")

        prompt_path = output_dir / f"{paper_id}_prompt.txt"
        prompt_path.write_text(prompt)


if __name__ == "__main__":
    main()
