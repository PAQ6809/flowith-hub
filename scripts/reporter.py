"""
Flowith Hub — Reporting Engine
Generates a professional Markdown report from analysis JSON output.

Usage:
    python scripts/reporter.py --analysis <path_to_analysis.json> [--output <report.md>]
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _bar(value: float, max_value: float, width: int = 20) -> str:
    """Render a simple ASCII progress bar."""
    if max_value == 0:
        filled = 0
    else:
        filled = int(round(value / max_value * width))
    return "█" * filled + "░" * (width - filled)


def _fmt_number(n) -> str:
    try:
        return f"{int(n):,}"
    except (TypeError, ValueError):
        return str(n)


# ---------------------------------------------------------------------------
# Section renderers
# ---------------------------------------------------------------------------

def _section_header(analysis: dict) -> str:
    stage_id = analysis.get("stage_id", "unknown")
    generated_at = analysis.get("generated_at", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    ctx = analysis.get("stage_context_analysis", {})
    tr = ctx.get("time_range", {})
    start = tr.get("start", "—")
    end = tr.get("end", "—")

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
    ctx = analysis.get("stage_context_analysis", {})
    material_count = ctx.get("material_count", 0)
    total_chars = ctx.get("total_content_length", 0)
    rationale = ctx.get("stage_rationale", "")

    lines = [
        "## Overview",
        "",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Materials in stage | {_fmt_number(material_count)} |",
        f"| Total content length | {_fmt_number(total_chars)} chars |",
        f"| Stage detection reason | {rationale} |",
        "",
    ]
    return "\n".join(lines)


def _section_themes(analysis: dict) -> str:
    theme_data = analysis.get("theme_structure_analysis", {})
    themes = theme_data.get("core_themes", [])
    note = theme_data.get("structure_notes", "")

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
    cog = analysis.get("cognitive_pattern_analysis", {})
    avg_h = cog.get("average_heading_count", 0)
    note = cog.get("pattern_note", "")

    # Visual gauge: 0-10 headings considered full
    bar = _bar(min(avg_h, 10), 10)

    lines = [
        "## Cognitive Structure",
        "",
        f"Average heading count per material: **{avg_h:.1f}**",
        "",
        f"```",
        f"Structure depth  [{bar}]  {avg_h:.1f} / 10",
        f"```",
        "",
    ]
    if note:
        lines += [f"> {note}", ""]

    return "\n".join(lines)


def _section_skills(analysis: dict) -> str:
    skill = analysis.get("skill_evolution_analysis", {})
    formats = skill.get("dominant_formats", {})
    note = skill.get("skill_trace_note", "")

    lines = ["## Format & Skill Traces", ""]

    if formats:
        total = sum(formats.values()) or 1
        lines += ["| Format | Count | Share | Distribution |", "|--------|-------|-------|--------------|"]
        for fmt, count in sorted(formats.items(), key=lambda x: -x[1]):
            pct = count / total * 100
            bar = _bar(count, total * 1.0, width=15)
            lines.append(f"| `{fmt}` | {count} | {pct:.1f}% | `{bar}` |")
    else:
        lines.append("_No format data available._")

    if note:
        lines += ["", f"> {note}"]

    lines.append("")
    return "\n".join(lines)


def _section_gaps(analysis: dict) -> str:
    gap = analysis.get("knowledge_gap_analysis", {})
    low_density = gap.get("low_density_materials", [])
    note = gap.get("gap_note", "")

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
    insight = analysis.get("ai_stage_insight", "")

    lines = [
        "## AI Stage Insight",
        "",
    ]

    if insight:
        # Wrap in a blockquote-style callout box
        for line in insight.splitlines():
            lines.append(line)
    else:
        lines.append("_No AI insight available for this stage._")

    lines.append("")
    return "\n".join(lines)


def _section_trending(analysis: dict) -> str:
    """Optional section rendered only when trending data is present."""
    trending = analysis.get("trending_context")
    if not trending:
        return ""

    scraped_at = trending.get("scraped_at", "unknown")
    repos = trending.get("repositories", [])

    lines = [
        "## Trending Context (GitHub)",
        "",
        f"_Scraped at: {scraped_at}_",
        "",
    ]

    if repos:
        lines += ["| Rank | Repository | Language | Stars | Description |",
                  "|------|-----------|----------|-------|-------------|"]
        for repo in repos[:10]:
            rank = repo.get("rank", "—")
            name = repo.get("full_name") or repo.get("name", "unknown")
            lang = repo.get("language") or "—"
            stars = _fmt_number(repo.get("stars_today") or repo.get("stars", 0))
            desc = (repo.get("description") or "")[:60]
            if len(repo.get("description", "")) > 60:
                desc += "…"
            lines.append(f"| {rank} | **{name}** | {lang} | {stars} | {desc} |")
    else:
        lines.append("_No trending repositories in this snapshot._")

    lines.append("")
    return "\n".join(lines)


def _section_footer() -> str:
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

def generate_report(analysis: dict) -> str:
    sections = [
        _section_header(analysis),
        _section_overview(analysis),
        _section_themes(analysis),
        _section_cognitive(analysis),
        _section_skills(analysis),
        _section_gaps(analysis),
        _section_trending(analysis),
        _section_ai(analysis),
        _section_footer(),
    ]
    return "\n".join(s for s in sections if s)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main():
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
    args = parser.parse_args()

    analysis_path = Path(args.analysis)
    if not analysis_path.exists():
        print(f"[reporter] ERROR: analysis file not found: {args.analysis}", file=sys.stderr)
        sys.exit(1)

    with open(analysis_path, "r", encoding="utf-8") as f:
        analysis = json.load(f)

    report_md = generate_report(analysis)

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(report_md)
        print(f"[reporter] Report written to: {args.output}")
    else:
        print(report_md)


if __name__ == "__main__":
    main()
