"""
Flowith Hub — AI-Driven Personal Knowledge Automator
Entry point script.

Usage:
    # Full pipeline (scrape → detect → analyze → report):
    python main.py --scrape [--simulate] [--language python] [--since daily]
                   [--materials materials.json] [--output analysis.json]
                   [--report report.md]

    # Analyze existing materials file:
    python main.py --materials <path_to_materials.json> [--output <analysis.json>] [--report <report.md>]

    # Generate report from existing analysis JSON:
    python main.py --materials <path> --output analysis.json --report report.md

Flags:
    --scrape              Run the trend scraper before analysis
    --simulate            Use simulated data (no network call)
    --language LANG       Filter trending repos by language (used with --scrape)
    --since PERIOD        Trending period: daily|weekly|monthly (default: daily)
    --materials PATH      Path to materials JSON (input for detect/analyze stages)
    --output PATH         Path to write analysis JSON output
    --report PATH         Path to write the Markdown report
"""

import argparse
import json
import sys
import subprocess
import io
from pathlib import Path

# Ensure UTF-8 output on Windows (avoids cp950 encoding errors)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# ---------------------------------------------------------------------------
# Resolve the analyzer package from scripts/analyzer/
# ---------------------------------------------------------------------------
SCRIPTS_DIR = Path(__file__).parent / "scripts" / "analyzer"
sys.path.insert(0, str(SCRIPTS_DIR))

from detect_stage import detect_stage      # noqa: E402
from analyze_stage import analyze_stage    # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_materials(path: str) -> tuple:
    """Load materials list from JSON file. Returns (materials, raw_data)."""
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict) and "materials" in data:
        return data["materials"], data
    return data, {"materials": data}


def run_scraper(
    output_path: str,
    language: str = "",
    since: str = "daily",
    simulate: bool = False,
) -> None:
    """Invoke scripts/scraper.py as a subprocess."""
    scraper = Path(__file__).parent / "scripts" / "scraper.py"
    cmd = [sys.executable, str(scraper), "--output", output_path, "--since", since]
    if language:
        cmd += ["--language", language]
    if simulate:
        cmd.append("--simulate")

    result = subprocess.run(cmd, capture_output=False)
    if result.returncode != 0:
        print(f"[flowith-hub] ERROR: scraper exited with code {result.returncode}", file=sys.stderr)
        sys.exit(result.returncode)


def run_reporter(analysis_path: str, report_path: str) -> None:
    """Invoke scripts/reporter.py as a subprocess."""
    reporter = Path(__file__).parent / "scripts" / "reporter.py"
    cmd = [sys.executable, str(reporter), "--analysis", analysis_path, "--output", report_path]

    result = subprocess.run(cmd, capture_output=False)
    if result.returncode != 0:
        print(f"[flowith-hub] ERROR: reporter exited with code {result.returncode}", file=sys.stderr)
        sys.exit(result.returncode)


def _merge_trending_context(analysis: dict, raw_data: dict) -> dict:
    """
    If the materials file contains a trending_context block (from scraper),
    attach it to the analysis so the reporter can render the trending table.
    """
    if "trending_context" in raw_data and "trending_context" not in analysis:
        analysis["trending_context"] = raw_data["trending_context"]
    return analysis


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Flowith Hub — Personal Knowledge Stage Analyzer"
    )

    # --- Input ---
    parser.add_argument(
        "--materials",
        default=None,
        help="Path to materials JSON file (default: materials.json when --scrape is used)",
    )

    # --- Scrape flags ---
    scrape_group = parser.add_argument_group("Scraper options")
    scrape_group.add_argument(
        "--scrape",
        action="store_true",
        help="Run the trend scraper to generate/refresh materials.json before analysis",
    )
    scrape_group.add_argument(
        "--simulate",
        action="store_true",
        help="Use simulated trending data instead of a live network request",
    )
    scrape_group.add_argument(
        "--language",
        default="",
        help="Filter GitHub Trending by language (e.g. python, typescript)",
    )
    scrape_group.add_argument(
        "--since",
        default="daily",
        choices=["daily", "weekly", "monthly"],
        help="Trending period for scraper (default: daily)",
    )

    # --- Output flags ---
    output_group = parser.add_argument_group("Output options")
    output_group.add_argument(
        "--output",
        default=None,
        help="Path to write analysis JSON (optional)",
    )
    output_group.add_argument(
        "--report",
        default=None,
        help="Path to write Markdown report (requires --output or auto-creates a temp file)",
    )

    args = parser.parse_args()

    # ------------------------------------------------------------------
    # 0. Determine materials path
    # ------------------------------------------------------------------
    materials_path = args.materials
    if args.scrape and not materials_path:
        materials_path = "materials.json"

    if not materials_path:
        parser.error("--materials is required unless --scrape is specified.")

    # ------------------------------------------------------------------
    # 1. SCRAPE
    # ------------------------------------------------------------------
    if args.scrape:
        print("[flowith-hub] ── Stage 1: Scrape ─────────────────────────────")
        run_scraper(
            output_path=materials_path,
            language=args.language,
            since=args.since,
            simulate=args.simulate,
        )

    # ------------------------------------------------------------------
    # 2. LOAD
    # ------------------------------------------------------------------
    print(f"[flowith-hub] ── Stage 2: Load ──────────────────────────────────")
    print(f"[flowith-hub] Loading materials from: {materials_path}")
    materials, raw_data = load_materials(materials_path)
    print(f"[flowith-hub] {len(materials)} material(s) loaded.")

    # ------------------------------------------------------------------
    # 3. DETECT
    # ------------------------------------------------------------------
    print(f"[flowith-hub] ── Stage 3: Detect ───────────────────────────────")
    stage = detect_stage(materials)
    if not stage:
        print("[flowith-hub] No concentrated learning stage detected.")
        sys.exit(0)

    print(f"[flowith-hub] Stage detected: {stage['stage_id']}")
    print(f"              {stage['stage_detected_reason']}")

    # ------------------------------------------------------------------
    # 4. ANALYZE
    # ------------------------------------------------------------------
    print(f"[flowith-hub] ── Stage 4: Analyze ──────────────────────────────")
    analysis = analyze_stage(materials, stage)
    analysis = _merge_trending_context(analysis, raw_data)
    print(f"[flowith-hub] Analysis complete (generated at {analysis['generated_at']}).")

    # ------------------------------------------------------------------
    # 5. OUTPUT / REPORT
    # ------------------------------------------------------------------
    print(f"[flowith-hub] ── Stage 5: Output ───────────────────────────────")

    # Determine analysis JSON output path
    analysis_output = args.output
    temp_analysis = False
    if args.report and not analysis_output:
        # Need a file path for the reporter; create one in the same dir as report
        report_dir = Path(args.report).parent
        analysis_output = str(report_dir / "analysis_temp.json")
        temp_analysis = True

    if analysis_output:
        out_path = Path(analysis_output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(analysis, f, ensure_ascii=False, indent=2)
        print(f"[flowith-hub] Analysis written to: {analysis_output}")
    else:
        # Print a quick summary when no output path given
        print("\n── Analysis Summary ─────────────────────────────────────────")
        ctx = analysis.get("stage_context_analysis", {})
        print(f"  Time range  : {ctx.get('time_range', {})}")
        print(f"  Materials   : {ctx.get('material_count')}")
        print(f"  Total chars : {ctx.get('total_content_length')}")

        themes = analysis.get("theme_structure_analysis", {}).get("core_themes", [])
        if themes:
            print(f"  Core themes : {', '.join(themes)}")

        gaps = analysis.get("knowledge_gap_analysis", {}).get("low_density_materials", [])
        if gaps:
            print(f"  Knowledge gaps ({len(gaps)} file(s)):")
            for g in gaps[:5]:
                print(f"    - {g}")

        print("\n── AI Insight ───────────────────────────────────────────────")
        print(analysis.get("ai_stage_insight", "(none)"))

    # ------------------------------------------------------------------
    # 6. REPORT
    # ------------------------------------------------------------------
    if args.report:
        print(f"[flowith-hub] ── Stage 6: Report ───────────────────────────────")
        if not analysis_output:
            print("[flowith-hub] ERROR: Cannot generate report without an analysis file path.", file=sys.stderr)
            sys.exit(1)
        run_reporter(analysis_path=analysis_output, report_path=args.report)

        # Clean up temp analysis file if we created one
        if temp_analysis:
            try:
                Path(analysis_output).unlink()
            except OSError:
                pass

    print("[flowith-hub] Done.")


if __name__ == "__main__":
    main()
