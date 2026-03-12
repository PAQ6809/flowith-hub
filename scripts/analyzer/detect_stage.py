import argparse
import json
from datetime import datetime, timedelta
from collections import defaultdict

# -------------------------
# 参数（保守默认）
# -------------------------

MIN_FILES_IN_STAGE = 3
MIN_TOTAL_LENGTH = 3000
WINDOW_DAYS = 14

# -------------------------
# 工具函数
# -------------------------

def parse_iso_time(s):
    return datetime.fromisoformat(s)

def group_by_day(materials):
    buckets = defaultdict(list)
    for m in materials:
        ingest_time = m.get("ingest_time")
        if not ingest_time:
            continue
        day = parse_iso_time(ingest_time).date()
        buckets[day].append(m)
    return buckets

def sliding_windows(sorted_days, window_days):
    for start_day in sorted_days:
        end_day = start_day + timedelta(days=window_days - 1)
        window = [d for d in sorted_days if start_day <= d <= end_day]
        yield start_day, end_day, window

# -------------------------
# 核心逻辑
# -------------------------

def detect_stage(materials):
    """
    返回最近一个满足条件的阶段（v1 设计）
    """
    if not materials:
        return None

    buckets = group_by_day(materials)
    days = sorted(buckets.keys())

    now = datetime.now().date()

    for start_day, theoretical_end_day, window_days in sliding_windows(days, WINDOW_DAYS):
        window_materials = []
        for d in window_days:
            window_materials.extend(buckets[d])

        file_count = len(window_materials)
        total_length = sum(m["content_length"] for m in window_materials)
        heading_sum = sum(m["heading_count"] for m in window_materials)

        if file_count >= MIN_FILES_IN_STAGE and total_length >= MIN_TOTAL_LENGTH:
            # ✅ 关键修复：阶段结束时间不得超过当前日期
            actual_end_day = min(theoretical_end_day, now)

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
                    f"{WINDOW_DAYS} 天窗口内出现集中输入："
                    f"{file_count} 个文件，约 {total_length} 字"
                ),
            }

    return None

# -------------------------
# CLI 调试入口
# -------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--materials")
    parser.add_argument("--output")
    args = parser.parse_args()

    if not args.materials:
        print("[detect_stage] materials file required")
    else:
        with open(args.materials, "r", encoding="utf-8") as f:
            data = json.load(f)
        materials = data["materials"] if isinstance(data, dict) and "materials" in data else data

        stage = detect_stage(materials)

        if not stage:
            print("[detect_stage] no stage detected")
        elif args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                json.dump(stage, f, ensure_ascii=False, indent=2)
        else:
            print("[detect_stage] stage detected:")
            for k, v in stage.items():
                print(f"  {k}: {v}")
