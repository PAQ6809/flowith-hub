"""
Flowith Hub — Reporting Engine
Generates a professional Markdown report from analysis JSON output.
Supports optional export hints for DOCX and PPTX formats via the
Skills/docx and Skills/pptx skill integrations.

Usage:
    python scripts/reporter.py --analysis <path_to_analysis.json> [--output <report.md>]
    python scripts/reporter.py --analysis <path_to_analysis.json> --output <report.md> --export-hint docx
    python scripts/reporter.py --analysis <path_to_analysis.json> --output <report.md> --export-hint pptx
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path


# ---------------------------------------------------------------------------
# Shared formatting helpers
# ---------------------------------------------------------------------------

def _bar(value: float, max_value: float, width: int = 20) -> str:
    """
    Render a simple ASCII progress bar using block characters.

    Args:
        value:     The current value to represent on the bar.
        max_value: The maximum possible value (full bar).
        width:     Total number of characters in the bar.

    Returns:
        A string of ``width`` characters using ``█`` (filled) and ``░`` (empty).
        Returns an all-empty bar if ``max_value`` is zero.
    """
    if max_value == 0:
        filled = 0
    else:
        filled = int(round(value / max_value * width))
    return "█" * filled + "░" * (width - filled)


def _fmt_number(n) -> str:
    """
    Format a value as a comma-separated integer string.

    Falls back to ``str(n)`` when ``n`` cannot be converted to ``int``
    (e.g. ``None``, non-numeric strings).

    Args:
        n: The value to format.

    Returns:
        Formatted number string, e.g. ``"1,234,567"``.
    """
    try:
        return f"{int(n):,}"
    except (TypeError, ValueError):
        return str(n)


# ---------------------------------------------------------------------------
# Section renderers
# ---------------------------------------------------------------------------

def _section_header(analysis: dict) -> str:
    """
    Render the report header block containing stage ID, time range, and
    generation timestamp.

    Args:
        analysis: Full analysis dict from ``analyze_stage``.

    Returns:
        Markdown string for the header section.
    """
    stage_id     = analysis.get("stage_id", "unknown")
    generated_at = analysis.get("generated_at", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    ctx          = analysis.get("stage_context_analysis", {})
    tr           = ctx.get("time_range", {})
    start        = tr.get("start", "—")
    end          = tr.get("end", "—")

    lines = [
        "# Flowith Hub — Stage Analysis Report",
        "",
        f"> **Stage ID:** `{stage_id}`  ",
        f"> **Period:** {start} → {end}  ",
        f"> **Generated:** {generated_at}",
        "",
        "---",
        "",
    ]
    return "\n".join(lines)


def _section_overview(analysis: dict) -> str:
    """
    Render the overview table with key stage metrics.

    Displays material count, total content length, and the stage detection
    rationale in a compact Markdown table.

    Args:
        analysis: Full analysis dict.

    Returns:
        Markdown string for the overview section.
    """
    ctx            = analysis.get("stage_context_analysis", {})
    material_count = ctx.get("material_count", 0)
    total_chars    = ctx.get("total_content_length", 0)
    rationale      = ctx.get("stage_rationale", "")

    lines = [
        "## Overview",
        "",
        "| Metric | Value |",
        "|--------|-------|",
        f"| Materials in stage | {_fmt_number(material_count)} |",
        f"| Total content length | {_fmt_number(total_chars)} chars |",
        f"| Stage detection reason | {rationale} |",
        "",
    ]
    return "\n".join(lines)


def _section_themes(analysis: dict) -> str:
    """
    Render the core themes section as a numbered list.

    Shows up to 5 dominant heading keywords extracted from the stage
    materials.  A fallback message is shown when no themes are detected.

    Args:
        analysis: Full analysis dict.

    Returns:
        Markdown string for the themes section.
    """
    theme_data = analysis.get("theme_structure_analysis", {})
    themes     = theme_data.get("core_themes", [])
    note       = theme_data.get("structure_notes", "")

    lines = ["## Core Themes", ""]

    if themes:
        for i, theme in enumerate(themes, 1):
            lines.append(f"{i}. **{theme}**")
    else:
        lines.append("_No dominant themes detected._")

    if note:
        lines += ["", f"> {note}"]

    lines.append("")
    return "\n".join(lines)


def _section_cognitive(analysis: dict) -> str:
    """
    Render the cognitive structure section with an ASCII depth gauge.

    Uses the average heading count per material as a proxy for structural
    thinking depth.  The gauge spans 0–10 headings.

    Args:
        analysis: Full analysis dict.

    Returns:
        Markdown string for the cognitive structure section.
    """
    cog   = analysis.get("cognitive_pattern_analysis", {})
    avg_h = cog.get("average_heading_count", 0)
    note  = cog.get("pattern_note", "")

    bar = _bar(min(avg_h, 10), 10)

    lines = [
        "## Cognitive Structure",
        "",
        f"Average heading count per material: **{avg_h:.1f}**",
        "",
        "```",
        f"Structure depth  [{bar}]  {avg_h:.1f} / 10",
        "```",
        "",
    ]
    if note:
        lines += [f"> {note}", ""]

    return "\n".join(lines)


def _section_skills(analysis: dict) -> str:
    """
    Render the format and skill traces section as a distribution table.

    Shows each file format's count, percentage share, and a small ASCII bar
    chart.  Formats are sorted by frequency (descending).

    Args:
        analysis: Full analysis dict.

    Returns:
        Markdown string for the skill traces section.
    """
    skill   = analysis.get("skill_evolution_analysis", {})
    formats = skill.get("dominant_formats", {})
    note    = skill.get("skill_trace_note", "")

    lines = ["## Format & Skill Traces", ""]

    if formats:
        total = sum(formats.values()) or 1
        lines += [
            "| Format | Count | Share | Distribution |",
            "|--------|-------|-------|--------------|",
        ]
        for fmt, count in sorted(formats.items(), key=lambda x: -x[1]):
            pct = count / total * 100
            bar = _bar(count, float(total), width=15)
            lines.append(f"| `{fmt}` | {count} | {pct:.1f}% | `{bar}` |")
    else:
        lines.append("_No format data available._")

    if note:
        lines += ["", f"> {note}"]

    lines.append("")
    return "\n".join(lines)


def _section_gaps(analysis: dict) -> str:
    """
    Render the knowledge gap analysis section.

    Lists low-density materials (those with fewer than 300 characters of
    content) that may require expansion.  Capped at 20 items with a
    "… and N more" suffix if the list is longer.

    Args:
        analysis: Full analysis dict.

    Returns:
        Markdown string for the knowledge gap section.
    """
    gap         = analysis.get("knowledge_gap_analysis", {})
    low_density = gap.get("low_density_materials", [])
    note        = gap.get("gap_note", "")

    lines = ["## Knowledge Gap Analysis", ""]

    if low_density:
        lines += [
            f"**{len(low_density)} low-density material(s) identified** (< 300 chars):",
            "",
        ]
        for path in low_density[:20]:
            lines.append(f"- `{path}`")
        if len(low_density) > 20:
            lines.append(f"- _… and {len(low_density) - 20} more_")
    else:
        lines.append("No significant knowledge gaps detected.")

    if note:
        lines += ["", f"> {note}"]

    lines.append("")
    return "\n".join(lines)


def _section_ai(analysis: dict) -> str:
    """
    Render the AI stage insight section.

    Outputs the ``ai_stage_insight`` field verbatim.  When the field is
    empty (or absent), a fallback message is shown.

    Args:
        analysis: Full analysis dict.

    Returns:
        Markdown string for the AI insight section.
    """
    insight = analysis.get("ai_stage_insight", "")

    lines = [
        "## AI Stage Insight",
        "",
    ]

    if insight:
        for line in insight.splitlines():
            lines.append(line)
    else:
        lines.append("_No AI insight available for this stage._")

    lines.append("")
    return "\n".join(lines)


def _section_trending(analysis: dict) -> str:
    """
    Render the optional trending context section.

    Only included when the analysis dict contains a ``trending_context``
    block (injected by the scraper pipeline).  Shows a table of the top-10
    trending repositories with rank, name, language, star count, and a
    truncated description.

    Args:
        analysis: Full analysis dict.

    Returns:
        Markdown string for the trending section, or an empty string if
        no trending data is present.
    """
    trending = analysis.get("trending_context")
    if not trending:
        return ""

    scraped_at = trending.get("scraped_at", "unknown")
    repos      = trending.get("repositories", [])

    lines = [
        "## Trending Context (GitHub)",
        "",
        f"_Scraped at: {scraped_at}_",
        "",
    ]

    if repos:
        lines += [
            "| Rank | Repository | Language | Stars | Description |",
            "|------|-----------|----------|-------|-------------|",
        ]
        for repo in repos[:10]:
            rank  = repo.get("rank", "—")
            name  = repo.get("full_name") or repo.get("name", "unknown")
            lang  = repo.get("language") or "—"
            stars = _fmt_number(repo.get("stars_today") or repo.get("stars", 0))
            raw_desc = repo.get("description") or ""
            desc  = raw_desc[:60] + ("…" if len(raw_desc) > 60 else "")
            lines.append(f"| {rank} | **{name}** | {lang} | {stars} | {desc} |")
    else:
        lines.append("_No trending repositories in this snapshot._")

    lines.append("")
    return "\n".join(lines)


def _section_export_hint(export_format: str) -> str:
    """
    Render an optional export-ready callout block with instructions for
    converting this Markdown report to DOCX or PPTX using the matching Skill.

    This section bridges the reporter with the Skills/docx and Skills/pptx
    integrations, providing actionable next steps for high-quality document
    export without embedding the full skill workflow in the reporter itself.

    Args:
        export_format: One of ``"docx"``, ``"pptx"``, or ``""`` (no hint).

    Returns:
        Markdown string for the export hint section, or an empty string if
        ``export_format`` is empty or unrecognised.
    """
    if export_format == "docx":
        return "\n".join([
            "## Export to Word Document",
            "",
            "> **Skill: `docx`** — Convert this report to a polished `.docx` file.",
            ">",
            "> **Recommended approach:**",
            "> 1. Install the docx npm package: `npm install -g docx`",
            "> 2. Use `docx-js` to create a new document with `Heading1`/`Heading2` styles.",
            "> 3. Map each section in this report to a heading + paragraph block.",
            "> 4. Validate with: `python Skills/docx/scripts/office/validate.py report.docx`",
            ">",
            "> **Page setup (US Letter):** width=12240 DXA, height=15840 DXA, margins=1440 DXA",
            "> **Tables:** always set both `columnWidths` and cell `width` in DXA units.",
            "> **Lists:** use `LevelFormat.BULLET` — never insert raw unicode bullet chars.",
            "",
        ])
    elif export_format == "pptx":
        return "\n".join([
            "## Export to Presentation",
            "",
            "> **Skill: `pptx`** — Convert this report into a slide deck.",
            ">",
            "> **Recommended approach:**",
            "> 1. Install pptxgenjs: `npm install -g pptxgenjs`",
            "> 2. Map each `##` section to one slide (title + bullet layout).",
            "> 3. Use a bold color palette from the PPTX skill (e.g. Midnight Executive).",
            "> 4. Add a visual element to every slide — avoid text-only slides.",
            "> 5. Visual QA: convert to PDF → images with LibreOffice + pdftoppm.",
            ">",
            "> **Typography:** slide title 36-44pt bold · body text 14-16pt",
            "> **Margins:** 0.5\" minimum from all edges",
            "",
        ])
    return ""


def _section_footer() -> str:
    """
    Render the report footer line with a generation timestamp.

    Returns:
        Markdown string for the footer section.
    """
    lines = [
        "---",
        "",
        f"_Report generated by **Flowith Hub** · {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}_",
        "",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main renderer
# ---------------------------------------------------------------------------

def generate_report(analysis: dict, export_format: str = "") -> str:
    """
    Assemble the full Markdown report from individual section renderers.

    Sections are rendered in a fixed order:

        Header → Overview → Themes → Cognitive → Skills →
        Gaps → Trending → Export Hint → AI Insight → Footer

    Empty strings returned by optional sections (trending, export hint) are
    automatically filtered out so no blank section separators appear.

    Args:
        analysis:      Full analysis dict from ``analyze_stage``.
        export_format: Optional export hint format — ``"docx"``, ``"pptx"``,
                       or ``""`` (default, no hint).

    Returns:
        Complete Markdown report as a single string.
    """
    sections = [
        _section_header(analysis),
        _section_overview(analysis),
        _section_themes(analysis),
        _section_cognitive(analysis),
        _section_skills(analysis),
        _section_gaps(analysis),
        _section_trending(analysis),
        _section_export_hint(export_format),
        _section_ai(analysis),
        _section_footer(),
    ]
    return "\n".join(s for s in sections if s)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """
    CLI entry point for the reporting engine.

    Loads an analysis JSON file, calls :func:`generate_report`, and either
    writes the Markdown to ``--output`` or prints it to stdout.

    Supports an optional ``--export-hint`` flag that appends a Skills-aware
    section to the report with actionable DOCX or PPTX export guidance.
    """
    parser = argparse.ArgumentParser(
        description="Flowith Hub — Generate Markdown report from analysis JSON"
    )
    parser.add_argument(
        "--analysis",
        required=True,
        help="Path to analysis JSON file (output of analyze_stage)",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Path to write the Markdown report (default: print to stdout)",
    )
    parser.add_argument(
        "--export-hint",
        default="",
        choices=["", "docx", "pptx"],
        help="Append a Skills-aware export section to the report (docx or pptx)",
    )
    args = parser.parse_args()

    analysis_path = Path(args.analysis)
    if not analysis_path.exists():
        print(
            f"[reporter] ERROR: analysis file not found: {args.analysis}",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        with open(analysis_path, "r", encoding="utf-8") as f:
            analysis = json.load(f)
    except json.JSONDecodeError as exc:
        print(f"[reporter] ERROR: invalid JSON in {args.analysis}: {exc}", file=sys.stderr)
        sys.exit(1)

    export_format = args.export_hint or ""
    report_md = generate_report(analysis, export_format=export_format)

    if args.output:
        out_path = Path(args.output)
        try:
            out_path.parent.mkdir(parents=True, exist_ok=True)
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(report_md)
            print(f"[reporter] Report written to: {args.output}")
            if export_format:
                print(f"[reporter] Export hint included: {export_format.upper()}")
        except OSError as exc:
            print(f"[reporter] ERROR: could not write report: {exc}", file=sys.stderr)
            sys.exit(1)
    else:
        print(report_md)


if __name__ == "__main__":
    main()
