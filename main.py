"""
Flowith Hub — AI-Driven Personal Knowledge Automator
Entry point script. Implements an Engine pattern for clean stage orchestration.

Usage:
    # Full pipeline (scrape → detect → analyze → report):
    python main.py --scrape [--simulate] [--language python] [--since daily]
                   [--materials materials.json] [--output analysis.json]
                   [--report report.md]

    # Analyze existing materials file:
    python main.py --materials <path_to_materials.json> [--output <analysis.json>] [--report <report.md>]

    # Generate report from existing analysis JSON:
    python main.py --materials <path> --output analysis.json --report report.md

    # Run a health check (verify dependencies and skill linkages):
    python main.py --check

Flags:
    --scrape              Run the trend scraper before analysis
    --simulate            Use simulated data (no network call)
    --language LANG       Filter trending repos by language (used with --scrape)
    --since PERIOD        Trending period: daily|weekly|monthly (default: daily)
    --materials PATH      Path to materials JSON (input for detect/analyze stages)
    --output PATH         Path to write analysis JSON output
    --report PATH         Path to write the Markdown report
    --auto-evolve         After the main pipeline completes, run evolve.py to
                          research trending features and update the roadmap
    --check               Run a health check: verify dependencies and skill linkages
"""

import argparse
import json
import sys
import subprocess
import importlib.util
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Ensure UTF-8 I/O on Windows (avoids cp950/cp1252 encoding errors)
# ---------------------------------------------------------------------------
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
# Unified Logger
# ---------------------------------------------------------------------------

class Logger:
    """Centralized, timestamped logger for all pipeline stages."""

    PREFIX = "flowith-hub"

    @classmethod
    def info(cls, msg: str) -> None:
        """Log an informational message to stdout."""
        ts = datetime.now().strftime("%H:%M:%S")
        print(f"[{cls.PREFIX} | {ts}] {msg}")

    @classmethod
    def warn(cls, msg: str) -> None:
        """Log a warning message to stderr."""
        ts = datetime.now().strftime("%H:%M:%S")
        print(f"[{cls.PREFIX} | {ts}] WARNING: {msg}", file=sys.stderr)

    @classmethod
    def error(cls, msg: str) -> None:
        """Log an error message to stderr."""
        ts = datetime.now().strftime("%H:%M:%S")
        print(f"[{cls.PREFIX} | {ts}] ERROR: {msg}", file=sys.stderr)

    @classmethod
    def stage(cls, label: str) -> None:
        """Print a visual stage separator banner."""
        print(f"\n[{cls.PREFIX}] ── {label} {'─' * max(1, 50 - len(label))}")


log = Logger()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_materials(path: str) -> tuple:
    """
    Load materials list from a JSON file.

    The file may be either:
      - A plain JSON array (legacy format).
      - A dict with a ``materials`` key (envelope format from the scraper).

    Returns:
        (materials: list, raw_data: dict)
            ``materials`` is the list of material dicts.
            ``raw_data``  is the full envelope (used to forward trending_context).

    Raises:
        FileNotFoundError: If ``path`` does not exist.
        json.JSONDecodeError: If the file contains invalid JSON.
    """
    mat_path = Path(path)
    if not mat_path.exists():
        raise FileNotFoundError(f"Materials file not found: {path}")

    with open(mat_path, "r", encoding="utf-8") as f:
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
    """
    Invoke ``scripts/scraper.py`` as a subprocess.

    Args:
        output_path: Destination path for the generated ``materials.json``.
        language:    Optional GitHub Trending language filter (e.g. ``"python"``).
        since:       Trending period — ``"daily"``, ``"weekly"``, or ``"monthly"``.
        simulate:    If ``True``, use the built-in simulated dataset instead of
                     making a live network request.

    Raises:
        SystemExit: If the scraper subprocess exits with a non-zero code.
    """
    scraper = Path(__file__).parent / "scripts" / "scraper.py"
    if not scraper.exists():
        log.error(f"scraper.py not found at: {scraper}")
        sys.exit(1)

    cmd = [sys.executable, str(scraper), "--output", output_path, "--since", since]
    if language:
        cmd += ["--language", language]
    if simulate:
        cmd.append("--simulate")

    try:
        result = subprocess.run(cmd, capture_output=False)
    except OSError as exc:
        log.error(f"Failed to launch scraper: {exc}")
        sys.exit(1)

    if result.returncode != 0:
        log.error(f"scraper exited with code {result.returncode}")
        sys.exit(result.returncode)


def run_reporter(analysis_path: str, report_path: str) -> None:
    """
    Invoke ``scripts/reporter.py`` as a subprocess.

    Args:
        analysis_path: Path to the analysis JSON file produced by ``analyze_stage``.
        report_path:   Destination path for the generated Markdown report.

    Raises:
        SystemExit: If the reporter subprocess exits with a non-zero code.
    """
    reporter = Path(__file__).parent / "scripts" / "reporter.py"
    if not reporter.exists():
        log.error(f"reporter.py not found at: {reporter}")
        sys.exit(1)

    cmd = [sys.executable, str(reporter), "--analysis", analysis_path, "--output", report_path]

    try:
        result = subprocess.run(cmd, capture_output=False)
    except OSError as exc:
        log.error(f"Failed to launch reporter: {exc}")
        sys.exit(1)

    if result.returncode != 0:
        log.error(f"reporter exited with code {result.returncode}")
        sys.exit(result.returncode)


def _merge_trending_context(analysis: dict, raw_data: dict) -> dict:
    """
    Attach the ``trending_context`` block from the scraper envelope to the
    analysis dict so the reporter can render the trending table.

    If the analysis already contains a ``trending_context`` key (e.g. from a
    previous run), it is left untouched to avoid overwriting newer data.

    Args:
        analysis:  The analysis dict produced by ``analyze_stage``.
        raw_data:  The full envelope dict loaded from the materials file.

    Returns:
        The (potentially mutated) ``analysis`` dict.
    """
    if "trending_context" in raw_data and "trending_context" not in analysis:
        analysis["trending_context"] = raw_data["trending_context"]
    return analysis


# ---------------------------------------------------------------------------
# Health Check
# ---------------------------------------------------------------------------

def run_health_check() -> None:
    """
    Run a comprehensive health check of the Flowith Hub installation.

    Verifies:
      - All required script files are present.
      - Python stdlib modules used by the pipeline are importable.
      - Optional third-party packages (requests, beautifulsoup4) are available.
      - The Skills/gitpretty emoji-commit.sh script is discoverable.
      - The analyzer package (detect_stage, analyze_stage) can be imported.

    Exits with code 0 on full pass, code 1 if any critical checks fail.
    """
    print("\n[flowith-hub] Health Check\n" + "=" * 44)

    project_root = Path(__file__).parent
    issues: list[str] = []
    ok_count = 0

    def check(label: str, ok: bool, detail: str = "") -> None:
        nonlocal ok_count
        status = "  OK " if ok else "FAIL"
        suffix = f"  — {detail}" if detail else ""
        print(f"  [{status}]  {label}{suffix}")
        if ok:
            ok_count += 1
        else:
            issues.append(label)

    # --- Script presence ---
    print("\nScript files:")
    script_files = {
        "main.py":                     project_root / "main.py",
        "scripts/scraper.py":          project_root / "scripts" / "scraper.py",
        "scripts/reporter.py":         project_root / "scripts" / "reporter.py",
        "scripts/evolve.py":           project_root / "scripts" / "evolve.py",
        "scripts/auto_optimize.py":    project_root / "scripts" / "auto_optimize.py",
        "scripts/analyzer/detect_stage.py":  project_root / "scripts" / "analyzer" / "detect_stage.py",
        "scripts/analyzer/analyze_stage.py": project_root / "scripts" / "analyzer" / "analyze_stage.py",
    }
    for label, path in script_files.items():
        check(label, path.exists(), "" if path.exists() else f"not found at {path}")

    # --- Stdlib imports ---
    print("\nStandard library modules:")
    stdlib_mods = ["argparse", "json", "sys", "subprocess", "pathlib",
                   "datetime", "collections", "importlib"]
    for mod in stdlib_mods:
        ok = importlib.util.find_spec(mod) is not None
        check(mod, ok)

    # --- Optional third-party packages ---
    print("\nOptional packages (needed for live scraping):")
    for pkg in ["requests", "bs4"]:
        ok = importlib.util.find_spec(pkg) is not None
        label = "requests" if pkg == "requests" else "beautifulsoup4 (bs4)"
        check(label, ok, "install with: pip install requests beautifulsoup4" if not ok else "")

    # --- Analyzer import test ---
    print("\nAnalyzer package:")
    try:
        import detect_stage as _ds   # noqa: F401
        check("detect_stage importable", True)
    except ImportError as exc:
        check("detect_stage importable", False, str(exc))

    try:
        import analyze_stage as _as  # noqa: F401
        check("analyze_stage importable", True)
    except ImportError as exc:
        check("analyze_stage importable", False, str(exc))

    # --- Skills linkage ---
    print("\nSkill linkages:")
    skills_root = project_root.parent.parent / "Skills"  # repo root / Skills/
    skill_checks = {
        "Skills/gitpretty/scripts/emoji-commit.sh": skills_root / "gitpretty" / "scripts" / "emoji-commit.sh",
        "Skills/docx/SKILL.md":                     skills_root / "docx" / "SKILL.md",
        "Skills/pptx/SKILL.md":                     skills_root / "pptx" / "SKILL.md",
    }
    for label, path in skill_checks.items():
        check(label, path.exists(), "" if path.exists() else f"not found at {path}")

    # --- docs/ directory ---
    print("\nDocs / output directories:")
    docs_dir = project_root / "docs"
    check("docs/ directory", docs_dir.exists(), "run mkdir docs if missing" if not docs_dir.exists() else "")

    # --- Summary ---
    total = ok_count + len(issues)
    print(f"\n{'=' * 44}")
    print(f"  Result: {ok_count}/{total} checks passed")
    if issues:
        print(f"\n  Failed checks:")
        for issue in issues:
            print(f"    - {issue}")
        print()
        sys.exit(1)
    else:
        print("  All checks passed. Flowith Hub is healthy.\n")
        sys.exit(0)


# ---------------------------------------------------------------------------
# Engine — pipeline orchestrator
# ---------------------------------------------------------------------------

class FlowithEngine:
    """
    Orchestrates the full Flowith Hub pipeline.

    The engine encapsulates each stage as a discrete method, keeping ``main()``
    declarative and easy to extend. Stages run in order:

        1. Scrape  (optional)
        2. Load
        3. Detect
        4. Analyze
        5. Output / Report
        6. Auto-Evolve (optional)
    """

    def __init__(self, args: argparse.Namespace) -> None:
        """
        Initialise the engine with parsed CLI arguments.

        Args:
            args: The ``argparse.Namespace`` returned by ``parser.parse_args()``.
        """
        self.args = args
        self.materials_path: str = ""
        self.materials: list = []
        self.raw_data: dict = {}
        self.stage: dict | None = None
        self.analysis: dict = {}

    # ------------------------------------------------------------------
    # Stage 1 — Scrape
    # ------------------------------------------------------------------

    def stage_scrape(self) -> None:
        """
        Invoke the GitHub Trending scraper to generate or refresh materials.json.

        Skipped when ``--scrape`` is not passed. Uses ``--simulate`` mode when
        the flag is set, avoiding any live network requests.
        """
        log.stage("Stage 1: Scrape")
        run_scraper(
            output_path=self.materials_path,
            language=self.args.language,
            since=self.args.since,
            simulate=self.args.simulate,
        )

    # ------------------------------------------------------------------
    # Stage 2 — Load
    # ------------------------------------------------------------------

    def stage_load(self) -> None:
        """
        Load and validate the materials JSON from disk.

        Populates ``self.materials`` (list of material dicts) and
        ``self.raw_data`` (full envelope for downstream trending_context merging).

        Raises:
            SystemExit: If the file is missing or contains invalid JSON.
        """
        log.stage("Stage 2: Load")
        log.info(f"Loading materials from: {self.materials_path}")

        try:
            self.materials, self.raw_data = load_materials(self.materials_path)
        except FileNotFoundError as exc:
            log.error(str(exc))
            sys.exit(1)
        except json.JSONDecodeError as exc:
            log.error(f"Invalid JSON in {self.materials_path}: {exc}")
            sys.exit(1)

        log.info(f"{len(self.materials)} material(s) loaded.")

    # ------------------------------------------------------------------
    # Stage 3 — Detect
    # ------------------------------------------------------------------

    def stage_detect(self) -> None:
        """
        Run the sliding-window stage detection algorithm over the loaded materials.

        Sets ``self.stage`` to the detected stage dict, or exits with code 0 if
        no concentrated learning stage is found.
        """
        log.stage("Stage 3: Detect")
        self.stage = detect_stage(self.materials)

        if not self.stage:
            log.info("No concentrated learning stage detected.")
            sys.exit(0)

        log.info(f"Stage detected: {self.stage['stage_id']}")
        log.info(f"  Reason: {self.stage['stage_detected_reason']}")

    # ------------------------------------------------------------------
    # Stage 4 — Analyze
    # ------------------------------------------------------------------

    def stage_analyze(self) -> None:
        """
        Perform structural analysis on the detected stage.

        Populates ``self.analysis`` with theme extraction, cognitive pattern
        data, format distribution, knowledge gap flagging, and an AI insight
        placeholder. Also merges any trending_context from the scraper envelope.
        """
        log.stage("Stage 4: Analyze")
        self.analysis = analyze_stage(self.materials, self.stage)
        self.analysis = _merge_trending_context(self.analysis, self.raw_data)
        log.info(f"Analysis complete (generated at {self.analysis['generated_at']}).")

    # ------------------------------------------------------------------
    # Stage 5 — Output / Report
    # ------------------------------------------------------------------

    def stage_output(self) -> str | None:
        """
        Write the analysis JSON to disk and/or print a console summary.

        Returns:
            The resolved analysis output path (str) if written to disk,
            or ``None`` if only a console summary was printed.
        """
        log.stage("Stage 5: Output")
        args = self.args

        analysis_output = args.output
        temp_analysis = False

        # If a report is requested but no explicit output path is given,
        # write a temporary analysis file alongside the report.
        if args.report and not analysis_output:
            report_dir = Path(args.report).parent
            analysis_output = str(report_dir / "analysis_temp.json")
            temp_analysis = True

        if analysis_output:
            out_path = Path(analysis_output)
            try:
                out_path.parent.mkdir(parents=True, exist_ok=True)
                with open(out_path, "w", encoding="utf-8") as f:
                    json.dump(self.analysis, f, ensure_ascii=False, indent=2)
                log.info(f"Analysis written to: {analysis_output}")
            except OSError as exc:
                log.error(f"Could not write analysis file: {exc}")
                sys.exit(1)
        else:
            # Console summary
            print("\n── Analysis Summary ─────────────────────────────────────────")
            ctx = self.analysis.get("stage_context_analysis", {})
            print(f"  Time range  : {ctx.get('time_range', {})}")
            print(f"  Materials   : {ctx.get('material_count')}")
            print(f"  Total chars : {ctx.get('total_content_length')}")

            themes = self.analysis.get("theme_structure_analysis", {}).get("core_themes", [])
            if themes:
                print(f"  Core themes : {', '.join(themes)}")

            gaps = self.analysis.get("knowledge_gap_analysis", {}).get("low_density_materials", [])
            if gaps:
                print(f"  Knowledge gaps ({len(gaps)} file(s)):")
                for g in gaps[:5]:
                    print(f"    - {g}")

            print("\n── AI Insight ───────────────────────────────────────────────")
            print(self.analysis.get("ai_stage_insight", "(none)"))

        return analysis_output if not temp_analysis else analysis_output

    # ------------------------------------------------------------------
    # Stage 6 — Report
    # ------------------------------------------------------------------

    def stage_report(self, analysis_output: str | None, temp_analysis: bool) -> None:
        """
        Invoke the Markdown reporter as a subprocess.

        Args:
            analysis_output: Path to the analysis JSON file.
            temp_analysis:   If ``True``, delete ``analysis_output`` after the
                             reporter finishes (it was a temporary file).

        Raises:
            SystemExit: If ``analysis_output`` is None (nothing to report from).
        """
        log.stage("Stage 6: Report")
        if not analysis_output:
            log.error("Cannot generate report without an analysis file path.")
            sys.exit(1)

        run_reporter(analysis_path=analysis_output, report_path=self.args.report)

        if temp_analysis:
            try:
                Path(analysis_output).unlink()
            except OSError:
                pass  # Non-critical cleanup failure

    # ------------------------------------------------------------------
    # Stage 7 — Auto-Evolve
    # ------------------------------------------------------------------

    def stage_evolve(self) -> None:
        """
        Run ``evolve.py`` to research trending AI developer features and
        append proposals to the evolution roadmap.

        Failures are treated as warnings — the overall pipeline is not
        aborted if the evolution step encounters an error.
        """
        log.stage("Stage 7: Auto-Evolve")
        evolve_script = Path(__file__).parent / "scripts" / "evolve.py"

        if not evolve_script.exists():
            log.warn(f"evolve.py not found at {evolve_script} — skipping.")
            return

        try:
            result = subprocess.run(
                [sys.executable, str(evolve_script)],
                capture_output=False,
            )
        except OSError as exc:
            log.warn(f"Could not launch evolve.py: {exc}")
            return

        if result.returncode != 0:
            log.warn(f"evolve.py exited with code {result.returncode}")

    # ------------------------------------------------------------------
    # Full pipeline runner
    # ------------------------------------------------------------------

    def run(self) -> None:
        """
        Execute the full pipeline based on the CLI flags stored in ``self.args``.

        Pipeline order:
          1. Scrape (if ``--scrape``)
          2. Load
          3. Detect
          4. Analyze
          5. Output / Report
          6. Auto-Evolve (if ``--auto-evolve``)
        """
        args = self.args

        # Resolve materials path
        self.materials_path = args.materials or ""
        if args.scrape and not self.materials_path:
            self.materials_path = "materials.json"

        if not self.materials_path:
            log.error("--materials is required unless --scrape is specified.")
            sys.exit(1)

        # Determine whether the analysis file is temporary
        analysis_output = args.output
        temp_analysis = False
        if args.report and not analysis_output:
            report_dir = Path(args.report).parent
            analysis_output = str(report_dir / "analysis_temp.json")
            temp_analysis = True

        if args.scrape:
            self.stage_scrape()

        self.stage_load()
        self.stage_detect()
        self.stage_analyze()
        written_path = self.stage_output()

        if args.report:
            self.stage_report(written_path or analysis_output, temp_analysis)

        log.info("Done.")

        if args.auto_evolve:
            self.stage_evolve()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    """
    Parse CLI arguments and dispatch to either health check or the main engine.

    Entry point called when ``main.py`` is executed directly. Builds an
    ``argparse`` parser, resolves the argument namespace, and either runs
    ``run_health_check()`` (if ``--check``) or delegates to ``FlowithEngine``.
    """
    parser = argparse.ArgumentParser(
        description="Flowith Hub — Personal Knowledge Stage Analyzer"
    )

    # --- Health check ---
    parser.add_argument(
        "--check",
        action="store_true",
        help="Run a health check: verify all dependencies and skill linkages, then exit",
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

    # --- Evolution flag ---
    parser.add_argument(
        "--auto-evolve",
        action="store_true",
        help="After the main pipeline completes, run evolve.py to research features and update the roadmap",
    )

    args = parser.parse_args()

    if args.check:
        run_health_check()
        return  # run_health_check calls sys.exit internally; this is a safety return

    if not args.scrape and not args.materials:
        parser.error("--materials is required unless --scrape or --check is specified.")

    engine = FlowithEngine(args)
    engine.run()


if __name__ == "__main__":
    main()
