"""
Flowith Hub — Stage Analysis Engine
Performs structural analysis on a detected learning stage and produces a
structured analysis dict ready for the reporter.

Usage (standalone CLI):
    python scripts/analyzer/analyze_stage.py \\
        --materials materials.json \\
        --stage stage.json \\
        [--output analysis.json]
"""

import argparse
import json
from collections import Counter
from datetime import datetime
from typing import Dict, List, Optional


# ---------------------------------------------------------------------------
# AI insight layer
# ---------------------------------------------------------------------------

def build_ai_prompt(stage_summary: Dict) -> str:
    """
    Construct the frozen prompt template used to request a semantic stage
    analysis from an external LLM.

    The prompt is intentionally constrained to prevent the model from making
    long-term character judgements about the learner.  It requests exactly
    three output sections:

    1. Stage core characteristics
    2. Possible change signals
    3. Analytical boundaries and uncertainties

    Args:
        stage_summary: Dict containing the following keys:
            - ``time_range``            (dict with ``start`` / ``end`` strings)
            - ``material_count``        (int)
            - ``total_content_length``  (int)
            - ``themes``                (list of str)
            - ``structure_notes``       (str)
            - ``average_heading_count`` (float)
            - ``skill_traces``          (dict mapping format → count)
            - ``knowledge_gaps``        (list of relative paths)

    Returns:
        A multi-line prompt string ready to be sent to any LLM API.
    """
    return f"""
You are analysing a user's knowledge input and expression materials for a specific time stage.
These materials have been structurally processed. Below are objective statistics for this stage.

Time range:        {stage_summary['time_range']['start']} → {stage_summary['time_range']['end']}
Material count:    {stage_summary['material_count']}
Total characters:  {stage_summary['total_content_length']}

Theme keywords:
{', '.join(stage_summary['themes'])}

Structural notes:
{stage_summary['structure_notes']}

Average heading count: {stage_summary['average_heading_count']}

Format distribution:
{stage_summary['skill_traces']}

Potential low-density materials:
{stage_summary['knowledge_gaps']}

Please complete a stage semantic analysis under these constraints:
1. Only describe characteristics of *this stage* — do not generalise to long-term conclusions
2. You may note changes, trends, or anomalies, but maintain a revisable tone
3. Do not make judgements about the user's ability, character, or long-term identity
4. Do not use phrases like "consistently" or "always has been"
5. Do not assume you know the user's full background

Your output MUST contain exactly three sections:
[Stage Core Characteristics]
[Possible Change Signals]
[Analytical Boundaries and Uncertainties]

Output the analysis text directly.
""".strip()


def _ai_stage_insight_placeholder(stage_summary: Dict) -> str:
    """
    Return the placeholder AI insight text shown when no live LLM is connected.

    This makes it visually obvious in the final Markdown report that the AI
    insight section has not been filled by a real model — it is not silently
    empty.  Replace or wrap this function to inject live LLM responses.

    Args:
        stage_summary: Structural summary dict (accepted but not used in the
                       placeholder; included for API parity with an LLM caller).

    Returns:
        A multi-line placeholder string with three required sections.
    """
    _ = stage_summary  # unused in placeholder — kept for signature parity
    return (
        "[Stage Core Characteristics]\n"
        "(Placeholder: no LLM has generated semantic analysis for this stage.)\n\n"
        "[Possible Change Signals]\n"
        "(Placeholder: no model intervention; no change signals evaluated.)\n\n"
        "[Analytical Boundaries and Uncertainties]\n"
        "(Placeholder: no LLM-generated content used here.)"
    )


# ---------------------------------------------------------------------------
# Main analysis logic
# ---------------------------------------------------------------------------

def analyze_stage(materials: List[Dict], stage: Dict) -> Dict:
    """
    Perform comprehensive structural analysis on a detected learning stage.

    The function filters ``materials`` to those whose ``ingest_time`` falls
    within the stage window, then computes:

    - **Theme structure** — top-5 heading keywords by frequency.
    - **Cognitive pattern** — average heading count as a structural depth proxy.
    - **Skill evolution** — file-format distribution.
    - **Knowledge gaps** — materials with content length below the threshold.
    - **AI insight** — placeholder (or live LLM output if injected externally).

    Args:
        materials: Full list of material dicts from the materials JSON file.
                   Each dict must include at minimum:
                   ``ingest_time`` (ISO string), ``content_length`` (int),
                   ``heading_count`` (int), ``headings`` (list of str),
                   ``file_type`` (str), ``relative_path`` (str).
        stage:     Stage dict as returned by :func:`detect_stage`, containing
                   ``stage_start_time``, ``stage_end_time``, ``stage_id``,
                   and ``stage_detected_reason``.

    Returns:
        Analysis dict with the following top-level keys::

            {
                "stage_id":                   str,
                "generated_at":               str,   # "%Y-%m-%d %H:%M:%S"
                "analysis_completeness":      str,   # "complete" | "partial"
                "stage_context_analysis":     dict,
                "theme_structure_analysis":   dict,
                "cognitive_pattern_analysis": dict,
                "skill_evolution_analysis":   dict,
                "knowledge_gap_analysis":     dict,
                "ai_stage_insight":           str,
            }
    """
    # Parse stage window boundaries
    try:
        stage_start = datetime.fromisoformat(stage["stage_start_time"])
        stage_end   = datetime.fromisoformat(stage["stage_end_time"])
    except (KeyError, ValueError) as exc:
        raise ValueError(f"Invalid stage time bounds: {exc}") from exc

    # Filter materials to those within the stage window
    stage_files: List[Dict] = []
    for m in materials:
        ingest_time = m.get("ingest_time")
        if not ingest_time:
            continue
        try:
            ts = datetime.fromisoformat(ingest_time)
        except (ValueError, TypeError):
            continue
        if stage_start <= ts <= stage_end:
            stage_files.append(m)

    material_count      = len(stage_files)
    total_content_length = sum(m.get("content_length", 0) for m in stage_files)

    # ------------------------------------------------------------------
    # Theme structure analysis
    # ------------------------------------------------------------------
    all_headings: List[str] = []
    for m in stage_files:
        all_headings.extend(m.get("headings", []))

    theme_counter = Counter(all_headings)
    core_themes   = [k for k, _ in theme_counter.most_common(5)]

    theme_structure_analysis: Dict = {
        "core_themes": core_themes,
        "structure_notes": (
            "Heading and theme frequency is concentrated — materials show "
            "a reasonably focused topical scope."
            if core_themes else
            "Heading data is limited; thematic structure is not yet apparent."
        ),
    }

    # ------------------------------------------------------------------
    # Cognitive pattern analysis
    # ------------------------------------------------------------------
    avg_heading_count: float = (
        sum(m.get("heading_count", 0) for m in stage_files) / material_count
        if material_count else 0.0
    )

    cognitive_pattern_analysis: Dict = {
        "average_heading_count": round(avg_heading_count, 2),
        "pattern_note": (
            "Text structure is clear — materials show deliberate segmentation "
            "and organisational intent."
            if avg_heading_count >= 5 else
            "Text structure is relatively flat — content reads more as continuous "
            "capture than structured notes."
        ),
    }

    # ------------------------------------------------------------------
    # Skill evolution / format distribution
    # ------------------------------------------------------------------
    format_counter = Counter(m.get("file_type", "unknown") for m in stage_files)

    skill_evolution_analysis: Dict = {
        "dominant_formats": dict(format_counter),
        "skill_trace_note": (
            "Knowledge recording in this stage is primarily text-based."
        ),
    }

    # ------------------------------------------------------------------
    # Knowledge gap analysis (low-density materials < 300 chars)
    # ------------------------------------------------------------------
    LOW_DENSITY_THRESHOLD = 300
    low_density: List[str] = [
        m.get("relative_path", "(unknown)")
        for m in stage_files
        if m.get("content_length", 0) < LOW_DENSITY_THRESHOLD
    ]

    knowledge_gap_analysis: Dict = {
        "low_density_materials": low_density,
        "gap_note": (
            "Some materials are brief — they may be placeholders or early-stage "
            "capture notes that need expansion."
            if low_density else
            "Material information density is reasonably balanced across this stage."
        ),
    }

    # ------------------------------------------------------------------
    # Stage context summary
    # ------------------------------------------------------------------
    stage_context_analysis: Dict = {
        "time_range": {
            "start": stage_start.strftime("%Y-%m-%d"),
            "end":   stage_end.strftime("%Y-%m-%d"),
        },
        "material_count":      material_count,
        "total_content_length": total_content_length,
        "stage_rationale": stage.get(
            "stage_detected_reason",
            "Concentrated input detected within the specified time window."
        ),
    }

    # ------------------------------------------------------------------
    # AI semantic insight
    # ------------------------------------------------------------------
    stage_summary_for_ai: Dict = {
        "time_range":            stage_context_analysis["time_range"],
        "material_count":        material_count,
        "total_content_length":  total_content_length,
        "themes":                theme_structure_analysis["core_themes"],
        "structure_notes":       theme_structure_analysis["structure_notes"],
        "average_heading_count": cognitive_pattern_analysis["average_heading_count"],
        "skill_traces":          dict(format_counter),
        "knowledge_gaps":        low_density,
    }

    ai_insight = _ai_stage_insight_placeholder(stage_summary_for_ai)

    # ------------------------------------------------------------------
    # Assemble output
    # ------------------------------------------------------------------
    completeness = "complete" if material_count > 0 else "partial"

    return {
        "stage_id":                   stage["stage_id"],
        "generated_at":               datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "analysis_completeness":      completeness,
        "stage_context_analysis":     stage_context_analysis,
        "theme_structure_analysis":   theme_structure_analysis,
        "cognitive_pattern_analysis": cognitive_pattern_analysis,
        "skill_evolution_analysis":   skill_evolution_analysis,
        "knowledge_gap_analysis":     knowledge_gap_analysis,
        "ai_stage_insight":           ai_insight,
    }


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """
    Standalone CLI entry point for running the analysis stage in isolation.

    Loads a materials JSON and a stage JSON, calls :func:`analyze_stage`,
    and writes the result to ``--output`` or prints a completion message.
    """
    parser = argparse.ArgumentParser(
        description="Flowith Hub — Stage Analysis (standalone)"
    )
    parser.add_argument(
        "--materials",
        required=True,
        help="Path to materials JSON file",
    )
    parser.add_argument(
        "--stage",
        required=True,
        help="Path to stage JSON file (output of detect_stage)",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Optional path to write analysis JSON output",
    )
    args = parser.parse_args()

    with open(args.materials, "r", encoding="utf-8") as f:
        data = json.load(f)
    materials = data["materials"] if isinstance(data, dict) and "materials" in data else data

    with open(args.stage, "r", encoding="utf-8") as f:
        stage = json.load(f)

    try:
        analysis = analyze_stage(materials, stage)
    except ValueError as exc:
        print(f"[analyze_stage] ERROR: {exc}")
        raise SystemExit(1) from exc

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(analysis, f, ensure_ascii=False, indent=2)
        print(f"[analyze_stage] Analysis written to: {args.output}")
    else:
        print(f"[analyze_stage] Analysis generated for stage: {analysis['stage_id']}")


if __name__ == "__main__":
    main()
