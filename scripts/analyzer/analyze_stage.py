import argparse
import json
from collections import Counter
from typing import Dict, List
from datetime import datetime


# ======================================================
# AI 占位层（用于验证模型是否真正介入）
# ======================================================

def build_ai_prompt(stage_summary: Dict) -> str:
    """
    冻结版 Prompt：只允许阶段语义深化，不允许长期定性
    """
    return f"""
你正在分析一个用户在某一时间阶段内的知识输入与表达材料。
这些材料已经被结构化处理，以下是该阶段的客观统计结果。

时间范围：{stage_summary['time_range']['start']} → {stage_summary['time_range']['end']}
材料数量：{stage_summary['material_count']}
总字数：{stage_summary['total_content_length']}

主题关键词：
{', '.join(stage_summary['themes'])}

结构特征说明：
{stage_summary['structure_notes']}

平均标题数量：{stage_summary['average_heading_count']}

主要文件格式分布：
{stage_summary['skill_traces']}

潜在低密度材料：
{stage_summary['knowledge_gaps']}

请完成阶段性语义分析，遵循以下约束：
1. 只描述“这一阶段”的特征，不上升为长期结论
2. 可指出变化、趋势或异常，但需保持可被修正的语气
3. 不对用户能力、性格或长期身份做定性判断
4. 不使用“一贯”“长期如此”等表述
5. 不假设你了解该用户的全部背景

你的输出必须包含三部分：
【阶段核心特征】
【可能的变化信号】
【当前分析的边界与不确定性】

请直接输出分析文本。
""".strip()


def ai_stage_insight(stage_summary: Dict) -> str:
    """
    AI 阶段语义分析 —— 明确占位标记版
    如果你在最终 Markdown 中仍然看到这段文字，
    说明当前阶段并没有由 Agent / 模型生成真实语义分析。
    """

    return (
        "【阶段核心特征】\n"
        "（占位标记：如果你看到这段文字，说明当前阶段尚未由模型生成语义分析。）\n\n"
        "【可能的变化信号】\n"
        "（占位标记：模型尚未介入，暂无变化信号判断。）\n\n"
        "【当前分析的边界与不确定性】\n"
        "（占位标记：此处未使用任何大模型生成内容。）"
    )


# ======================================================
# 主分析逻辑（结构化分析 + AI 字段）
# ======================================================

def analyze_stage(materials: List[Dict], stage: Dict) -> Dict:
    # 兼容 detect_stage.py 返回的字符串格式时间
    stage_start = datetime.fromisoformat(stage["stage_start_time"]) if isinstance(stage.get("stage_start_time"), str) else stage.get("start_time")
    stage_end = datetime.fromisoformat(stage["stage_end_time"]) if isinstance(stage.get("stage_end_time"), str) else stage.get("end_time")

    stage_files = [
        m for m in materials
        if m.get("ingest_time")
        and stage_start <= datetime.fromisoformat(m["ingest_time"]) <= stage_end
    ]

    material_count = len(stage_files)
    total_content_length = sum(m["content_length"] for m in stage_files)

    # ---------- 主题结构分析 ----------
    all_titles = []
    for m in stage_files:
        all_titles.extend(m.get("headings", []))

    theme_counter = Counter(all_titles)
    core_themes = [k for k, _ in theme_counter.most_common(5)]

    theme_structure_analysis = {
        "core_themes": core_themes,
        "structure_notes": (
            "标题与主题出现频率较为集中，材料整体具备一定主题聚焦度。"
            if core_themes else
            "标题信息有限，主题结构尚不明显。"
        )
    }

    # ---------- 认知模式 ----------
    avg_heading_count = (
        sum(m["heading_count"] for m in stage_files) / material_count
        if material_count else 0
    )

    cognitive_pattern_analysis = {
        "average_heading_count": round(avg_heading_count, 2),
        "pattern_note": (
            "文本结构清晰，具备较强的分段与组织意识。"
            if avg_heading_count >= 5 else
            "文本结构相对扁平，更多呈现为连续记录。"
        )
    }

    # ---------- 技能使用痕迹 ----------
    format_counter = Counter(m["file_type"] for m in stage_files)

    skill_evolution_analysis = {
        "dominant_formats": dict(format_counter),
        "skill_trace_note": "当前阶段主要通过文本方式进行知识记录与整理。"
    }

    # ---------- 知识断层 ----------
    low_density = [
        m["relative_path"]
        for m in stage_files
        if m["content_length"] < 300
    ]

    knowledge_gap_analysis = {
        "low_density_materials": low_density,
        "gap_note": (
            "部分材料内容较为简略，可能仍处于占位或初步记录状态。"
            if low_density else
            "当前阶段材料整体信息密度较为均衡。"
        )
    }

    # ---------- 阶段上下文 ----------
    stage_context_analysis = {
        "time_range": {
            "start": stage_start.strftime("%Y-%m-%d"),
            "end": stage_end.strftime("%Y-%m-%d")
        },
        "material_count": material_count,
        "total_content_length": total_content_length,
        "stage_rationale": stage.get(
            "stage_detected_reason", "在指定时间窗口内检测到集中输入。"
        )
    }

    # ---------- AI 阶段语义深化 ----------
    stage_summary_for_ai = {
        "time_range": stage_context_analysis["time_range"],
        "material_count": material_count,
        "total_content_length": total_content_length,
        "themes": theme_structure_analysis["core_themes"],
        "structure_notes": theme_structure_analysis["structure_notes"],
        "average_heading_count": cognitive_pattern_analysis["average_heading_count"],
        "skill_traces": dict(format_counter),
        "knowledge_gaps": low_density
    }

    ai_insight = ai_stage_insight(stage_summary_for_ai)

    # ---------- 汇总输出 ----------
    return {
        "stage_id": stage["stage_id"],
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "analysis_completeness": "complete",
        "stage_context_analysis": stage_context_analysis,
        "theme_structure_analysis": theme_structure_analysis,
        "cognitive_pattern_analysis": cognitive_pattern_analysis,
        "skill_evolution_analysis": skill_evolution_analysis,
        "knowledge_gap_analysis": knowledge_gap_analysis,
        "ai_stage_insight": ai_insight
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--materials")
    parser.add_argument("--stage")
    parser.add_argument("--output")
    args = parser.parse_args()

    if not args.materials or not args.stage:
        print("[analyze_stage] materials and stage files required")
    else:
        with open(args.materials, "r", encoding="utf-8") as f:
            data = json.load(f)
        materials = data["materials"] if isinstance(data, dict) and "materials" in data else data

        with open(args.stage, "r", encoding="utf-8") as f:
            stage = json.load(f)

        analysis = analyze_stage(materials, stage)

        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                json.dump(analysis, f, ensure_ascii=False, indent=2)
        else:
            print("[analyze_stage] analysis generated")
