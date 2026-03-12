"""
Flowith Hub — Daily Optimization Script
Runs the full daily pipeline:
  1. Scrapes fresh GitHub Trending data via scraper.py
  2. Updates README.md Overview/Stats section with latest trend summary
  3. Commits all changes via emoji-commit.sh
  4. Reports the result

Usage:
    python scripts/auto_optimize.py [--simulate] [--language <lang>] [--since <daily|weekly|monthly>]
"""

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths — all relative to the project root
# ---------------------------------------------------------------------------

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
SCRAPER = SCRIPT_DIR / "scraper.py"
EVOLVE = SCRIPT_DIR / "evolve.py"
README = PROJECT_ROOT / "README.md"
MATERIALS_OUT = PROJECT_ROOT / "materials.json"

# Locations where emoji-commit.sh may live (checked in order)
EMOJI_COMMIT_CANDIDATES = [
    PROJECT_ROOT / "scripts" / "emoji-commit.sh",
    PROJECT_ROOT / "emoji-commit.sh",
    Path.home()
    / "AppData/Roaming/flowith-os-beta/data/os-filesystem/Skills/gitpretty/scripts/emoji-commit.sh",
    Path.home()
    / "AppData/Roaming/flowith-os-beta/data/os-filesystem/.claude/skills/gitpretty/scripts/emoji-commit.sh",
]

COMMIT_MSG = "chore: daily project optimization and trend update"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def log(msg: str) -> None:
    ts = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    print(f"[auto_optimize | {ts}] {msg}")


def find_emoji_commit() -> Path | None:
    for candidate in EMOJI_COMMIT_CANDIDATES:
        if candidate.exists():
            return candidate
    return None


# ---------------------------------------------------------------------------
# Step 1 — Scrape
# ---------------------------------------------------------------------------

def run_scraper(language: str, since: str, simulate: bool) -> dict:
    log("Running scraper.py …")
    cmd = [sys.executable, str(SCRAPER), "--output", str(MATERIALS_OUT)]
    if language:
        cmd += ["--language", language]
    if since:
        cmd += ["--since", since]
    if simulate:
        cmd.append("--simulate")

    result = subprocess.run(cmd, capture_output=True, text=True, cwd=PROJECT_ROOT)
    print(result.stdout.strip())
    if result.returncode != 0:
        print(result.stderr.strip())
        raise RuntimeError(f"scraper.py exited with code {result.returncode}")

    with open(MATERIALS_OUT, encoding="utf-8") as f:
        data = json.load(f)

    log(f"Scraper OK — {data.get('repository_count', 0)} repos, source={data.get('source')}")
    return data


# ---------------------------------------------------------------------------
# Step 2 — Update README.md
# ---------------------------------------------------------------------------

README_MARKER_START = "<!-- auto_optimize:start -->"
README_MARKER_END = "<!-- auto_optimize:end -->"


def build_stats_block(data: dict) -> str:
    """Build a Markdown stats block from scraped data."""
    now = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    repos = data.get("trending_context", {}).get("repositories", [])
    source = data.get("source", "unknown")

    lines = [
        README_MARKER_START,
        "",
        "## Overview — Latest Trending Stats",
        "",
        f"> Last updated: **{now}** · Source: `{source}`",
        "",
        f"| Rank | Repository | Language | ★ Today |",
        f"|------|-----------|----------|---------|",
    ]
    for repo in repos[:10]:
        rank = repo.get("rank", "—")
        full = repo.get("full_name", "—")
        lang = repo.get("language") or "—"
        stars_today = repo.get("stars_today", 0)
        lines.append(f"| {rank} | `{full}` | {lang} | +{stars_today:,} |")

    lines += ["", README_MARKER_END]
    return "\n".join(lines)


def update_readme(data: dict) -> bool:
    """
    Insert/replace the auto_optimize block in README.md.
    Returns True if the file was modified.
    """
    if not README.exists():
        log(f"WARNING: README not found at {README} — skipping update.")
        return False

    content = README.read_text(encoding="utf-8")
    new_block = build_stats_block(data)

    if README_MARKER_START in content and README_MARKER_END in content:
        start_idx = content.index(README_MARKER_START)
        end_idx = content.index(README_MARKER_END) + len(README_MARKER_END)
        new_content = content[:start_idx] + new_block + content[end_idx:]
    else:
        # Append before the final HR/license section if present, else at end
        separator = "\n\n---\n\n"
        if "## License" in content:
            insert_at = content.rindex("## License")
            new_content = (
                content[:insert_at].rstrip()
                + separator
                + new_block
                + separator
                + content[insert_at:]
            )
        else:
            new_content = content.rstrip() + separator + new_block + "\n"

    if new_content == content:
        log("README.md already up to date — no changes.")
        return False

    README.write_text(new_content, encoding="utf-8")
    log("README.md updated with latest trend stats.")
    return True


# ---------------------------------------------------------------------------
# Step 3 — Commit
# ---------------------------------------------------------------------------

def run_commit() -> bool:
    """
    Stage all changes and commit using emoji-commit.sh if available,
    otherwise fall back to plain git commit.
    Returns True if a commit was made.
    """
    # Check if there is anything to commit
    status = subprocess.run(
        ["git", "status", "--porcelain"],
        capture_output=True, text=True, cwd=PROJECT_ROOT,
    )
    if not status.stdout.strip():
        log("Nothing to commit — working tree clean.")
        return False

    # Stage everything
    subprocess.run(["git", "add", "-A"], cwd=PROJECT_ROOT, check=True)

    emoji_script = find_emoji_commit()
    if emoji_script:
        log(f"Committing via emoji-commit.sh ({emoji_script}) …")
        result = subprocess.run(
            ["bash", str(emoji_script), COMMIT_MSG],
            capture_output=True, text=True, cwd=PROJECT_ROOT,
        )
    else:
        log("emoji-commit.sh not found — using plain git commit …")
        result = subprocess.run(
            ["git", "commit", "-m", COMMIT_MSG],
            capture_output=True, text=True, cwd=PROJECT_ROOT,
        )

    print(result.stdout.strip())
    if result.returncode != 0:
        print(result.stderr.strip())
        raise RuntimeError(f"Commit step failed with code {result.returncode}")

    log("Commit successful.")
    return True


# ---------------------------------------------------------------------------
# Step 4 — Evolve
# ---------------------------------------------------------------------------

def run_evolve() -> None:
    """Invoke evolve.py to research trending features and update the roadmap."""
    if not EVOLVE.exists():
        log(f"WARNING: evolve.py not found at {EVOLVE} — skipping evolution step.")
        return

    log("Running evolve.py …")
    result = subprocess.run(
        [sys.executable, str(EVOLVE)],
        capture_output=True, text=True, cwd=PROJECT_ROOT,
    )
    print(result.stdout.strip())
    if result.returncode != 0:
        print(result.stderr.strip())
        log(f"WARNING: evolve.py exited with code {result.returncode} — continuing pipeline.")
    else:
        log("evolve.py completed successfully.")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Flowith Hub — Daily Optimization Pipeline"
    )
    parser.add_argument("--simulate", action="store_true",
                        help="Skip live network scrape, use simulated data")
    parser.add_argument("--language", default="",
                        help="Filter trending by language (e.g. python)")
    parser.add_argument("--since", default="daily",
                        choices=["daily", "weekly", "monthly"],
                        help="Trending period (default: daily)")
    args = parser.parse_args()

    log("=== Daily Optimization Pipeline START ===")

    try:
        # 1. Scrape
        data = run_scraper(args.language, args.since, args.simulate)

        # 2. Update README
        update_readme(data)

        # 3. Commit
        committed = run_commit()

        # 4. Evolve — research new features and update roadmap
        run_evolve()

        # 5. Report
        log("=== Daily Optimization Pipeline COMPLETE ===")
        repo_count = data.get("repository_count", 0)
        source = data.get("source", "unknown")
        commit_note = "committed" if committed else "nothing to commit"
        print(
            f"\nResult:\n"
            f"  Repos fetched : {repo_count}\n"
            f"  Source        : {source}\n"
            f"  README        : updated\n"
            f"  Git           : {commit_note}\n"
        )

    except Exception as exc:
        log(f"PIPELINE ERROR: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
