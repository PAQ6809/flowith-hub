"""
Flowith Hub — Stage Detection Algorithm
Identifies concentrated learning periods from a list of material entries using
a sliding-window approach over ingestion timestamps.

Usage (standalone CLI):
    python scripts/analyzer/detect_stage.py --materials materials.json [--output stage.json]
"""

import argparse
import json
from datetime import datetime, timedelta, date
from collections import defaultdict
from typing import Dict, List, Optional


# ---------------------------------------------------------------------------
# Tuning parameters (conservative defaults)
# ---------------------------------------------------------------------------

MIN_FILES_IN_STAGE = 3    # Minimum number of distinct material files in the window
MIN_TOTAL_LENGTH   = 3000 # Minimum total character count across all window materials
WINDOW_DAYS        = 14   # Sliding window width in calendar days


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _parse_iso_time(s: str) -> datetime:
    """
    Parse an ISO-8601 datetime string into a :class:`datetime` object.

    Handles both bare date strings (``YYYY-MM-DD``) and full datetimes
    (``YYYY-MM-DDTHH:MM:SS`` with optional timezone offsets).

    Args:
        s: The ISO-format string to parse.

    Returns:
        A :class:`datetime` object (timezone-naive).
    """
    return datetime.fromisoformat(s)


def _group_by_day(materials: List[Dict]) -> Dict[date, List[Dict]]:
    """
    Bucket materials by their ingestion date.

    Materials that lack an ``ingest_time`` field are silently skipped so
    that malformed entries do not abort the pipeline.

    Args:
        materials: List of material dicts, each expected to have an
                   ``ingest_time`` ISO string.

    Returns:
        A :class:`defaultdict` mapping ``datetime.date`` → list of material dicts.
    """
    buckets: Dict[date, List[Dict]] = defaultdict(list)
    for m in materials:
        ingest_time = m.get("ingest_time")
        if not ingest_time:
            continue
        try:
            day = _parse_iso_time(ingest_time).date()
        except (ValueError, TypeError):
            # Skip unparseable timestamps without crashing
            continue
        buckets[day].append(m)
    return buckets


def _sliding_windows(sorted_days: List[date], window_days: int):
    """
    Generate all ``(start_day, end_day, window_day_list)`` tuples for a
    sliding window of ``window_days`` days over ``sorted_days``.

    Each iteration advances the window start by exactly one calendar day
    (equal to the earliest date in ``sorted_days`` that falls within the
    window).  The returned ``window_day_list`` contains only days that are
    present in ``sorted_days`` — gaps between material dates are ignored.

    Args:
        sorted_days:  Ascending list of :class:`datetime.date` values that
                      have at least one material.
        window_days:  Width of the sliding window in calendar days.

    Yields:
        ``(start_day, end_day, window_day_list)`` tuples where
        ``end_day = start_day + window_days - 1``.
    """
    for start_day in sorted_days:
        end_day = start_day + timedelta(days=window_days - 1)
        window = [d for d in sorted_days if start_day <= d <= end_day]
        yield start_day, end_day, window


# ---------------------------------------------------------------------------
# Core detection logic
# ---------------------------------------------------------------------------

def detect_stage(materials: List[Dict]) -> Optional[Dict]:
    """
    Identify the first window in the materials timeline that meets the
    concentrated-learning thresholds.

    The algorithm groups materials by ingestion date, then slides a
    ``WINDOW_DAYS``-wide window over the sorted date list.  The first window
    where ``file_count >= MIN_FILES_IN_STAGE`` **and**
    ``total_content_length >= MIN_TOTAL_LENGTH`` is returned as the detected
    stage.

    The stage end time is clamped to the current calendar date so that
    future-dated materials do not produce unrealistic stage IDs.

    Args:
        materials: List of material dicts.  Each dict must include at least
                   ``ingest_time`` (ISO string) and ``content_length`` (int).

    Returns:
        A stage dict with the following keys if a stage is detected::

            {
                "stage_id":             str,   # "<start>__<end>" date pair
                "stage_start_time":     str,   # ISO date string
                "stage_end_time":       str,   # ISO date string (clamped to today)
                "signals": {
                    "file_count":       int,
                    "total_length":     int,
                    "heading_sum":      int,
                },
                "stage_detected_reason": str,
            }

        Returns ``None`` if no qualifying window is found.
    """
    if not materials:
        return None

    buckets = _group_by_day(materials)
    if not buckets:
        return None

    days = sorted(buckets.keys())
    today = datetime.now().date()

    for start_day, theoretical_end_day, window_days in _sliding_windows(days, WINDOW_DAYS):
        window_materials: List[Dict] = []
        for d in window_days:
            window_materials.extend(buckets[d])

        file_count    = len(window_materials)
        total_length  = sum(m.get("content_length", 0) for m in window_materials)
        heading_sum   = sum(m.get("heading_count", 0) for m in window_materials)

        if file_count >= MIN_FILES_IN_STAGE and total_length >= MIN_TOTAL_LENGTH:
            # Clamp end date to today — prevents future-dated stage IDs
            actual_end_day = min(theoretical_end_day, today)
            stage_id = f"{start_day.isoformat()}__{actual_end_day.isoformat()}"

            return {
                "stage_id": stage_id,
                "stage_start_time": start_day.isoformat(),
                "stage_end_time": actual_end_day.isoformat(),
                "signals": {
                    "file_count": file_count,
                    "total_length": total_length,
                    "heading_sum": heading_sum,
                },
                "stage_detected_reason": (
                    f"{WINDOW_DAYS}-day window with concentrated input: "
                    f"{file_count} file(s), ~{total_length:,} chars"
                ),
            }

    return None


# ---------------------------------------------------------------------------
# CLI debug entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """
    Standalone CLI entry point for testing the detection stage in isolation.

    Loads a materials JSON file, runs :func:`detect_stage`, and either writes
    the result to ``--output`` or prints a summary to stdout.
    """
    parser = argparse.ArgumentParser(
        description="Flowith Hub — Stage Detection (standalone)"
    )
    parser.add_argument(
        "--materials",
        required=True,
        help="Path to materials JSON file",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Optional path to write stage JSON output",
    )
    args = parser.parse_args()

    with open(args.materials, "r", encoding="utf-8") as f:
        data = json.load(f)

    materials = data["materials"] if isinstance(data, dict) and "materials" in data else data
    stage = detect_stage(materials)

    if not stage:
        print("[detect_stage] No stage detected.")
        return

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(stage, f, ensure_ascii=False, indent=2)
        print(f"[detect_stage] Stage written to: {args.output}")
    else:
        print("[detect_stage] Stage detected:")
        for k, v in stage.items():
            print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
