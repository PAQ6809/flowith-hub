# Flowith Hub

**AI-Driven Personal Knowledge Automator**

[![License: MIT](https://img.shields.io/badge/License-MIT-7C3AED.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.10%2B-3B82F6.svg)](https://www.python.org/)
[![Status](https://img.shields.io/badge/Status-Alpha-F59E0B.svg)]()
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-10B981.svg)](CONTRIBUTING.md)

---

> Transform how you capture, structure, and revisit knowledge.
> Flowith Hub detects your active learning stages, surfaces themes, and delivers AI-powered insight — all from your own local files.

---

## What It Does

Most knowledge tools tell you *what* to do. Flowith Hub tells you *what you've already done* — and makes it visible.

It scans your local materials, applies a sliding-window algorithm to identify concentrated learning periods, then returns structured analysis: themes, cognitive patterns, knowledge gaps, and an AI prompt layer ready for any LLM.

No cloud. No subscriptions. **Your files stay yours.**

---

## Core Modules

| Module | Role |
|--------|------|
| `detect_stage` | Sliding-window algorithm over ingestion timestamps — finds 14-day peaks of concentrated input |
| `analyze_stage` | Extracts themes, heading density, format distribution, and knowledge gaps from detected stages |
| `reporter` | Renders a polished Markdown report with ASCII gauges, tables, and AI insight callouts |
| `scraper` | Pulls GitHub Trending context to correlate your learning with ecosystem momentum |

---

## Key Features

- **Automatic Stage Detection** — identifies when you were most actively learning from file density and content mass
- **Theme Extraction** — surfaces recurring headings and topics across your materials
- **Cognitive Pattern Analysis** — measures structural complexity as a proxy for depth of thinking
- **Knowledge Gap Flagging** — highlights low-density files that may need expansion
- **AI Insight Layer** — plug in any LLM; a prompt template is generated automatically for each stage
- **Trending Context** — optional GitHub Trending overlay to map your learning against the ecosystem
- **Zero Core Dependencies** — runs on Python stdlib; no bloated requirements for the analysis pipeline

---

## Quick Start

```bash
# 1. Clone
git clone https://github.com/flowith/flowith-hub.git
cd flowith-hub

# 2. Analyze your materials (provide your own JSON)
python main.py --materials materials.json

# 3. Save full analysis + generate a Markdown report
python main.py --materials materials.json --output analysis.json --report report.md

# 4. Full pipeline: scrape GitHub Trending → detect → analyze → report
python main.py --scrape --language python --since daily --output analysis.json --report report.md

# 5. Simulated run (no network, great for testing)
python main.py --scrape --simulate --output analysis.json --report report.md
```

### Generate Report from Existing Analysis

```bash
python scripts/reporter.py --analysis analysis.json --output report.md
```

---

## Materials Format

Your materials file is a JSON array. Each entry represents one file from your knowledge base:

```json
[
  {
    "relative_path": "notes/2025-01-deep-learning.md",
    "file_type": "md",
    "ingest_time": "2025-01-15T10:30:00",
    "content_length": 4200,
    "heading_count": 8,
    "headings": ["Backpropagation", "Gradient Descent", "Activation Functions"]
  },
  {
    "relative_path": "notes/2025-01-transformers.md",
    "file_type": "md",
    "ingest_time": "2025-01-18T14:10:00",
    "content_length": 6800,
    "heading_count": 12,
    "headings": ["Self-Attention", "Positional Encoding", "BERT", "GPT Architecture"]
  }
]
```

---

## Example Report Output

Running the reporter on a stage analysis produces output like this:

```
# Flowith Hub — Stage Analysis Report

> **Stage ID:** `stage_2025-01-01_2025-01-14`
> **Period:** 2025-01-01 → 2025-01-14
> **Generated:** 2025-01-20 09:42:11

---

## Overview

| Metric                  | Value          |
|-------------------------|----------------|
| Materials in stage      | 23             |
| Total content length    | 142,800 chars  |
| Stage detection reason  | Peak 14-day window by content density |

## Core Themes

1. **Backpropagation**
2. **Transformer Architecture**
3. **Gradient Descent**
4. **Attention Mechanisms**
5. **Positional Encoding**

> 5 dominant themes across 23 materials

## Cognitive Structure

Average heading count per material: **7.4**

```
Structure depth  [███████████████░░░░░]  7.4 / 10
```

> High structural density — materials show deliberate, well-organised notes.

## Format & Skill Traces

| Format | Count | Share | Distribution    |
|--------|-------|-------|-----------------|
| `md`   | 19    | 82.6% | `███████████░░░` |
| `pdf`  | 3     | 13.0% | `██░░░░░░░░░░░░░` |
| `txt`  | 1     |  4.3% | `█░░░░░░░░░░░░░░` |

## Knowledge Gap Analysis

**2 low-density material(s) identified** (< 300 chars):

- `notes/2025-01-scratch.md`
- `notes/2025-01-todo.txt`

## AI Stage Insight

This stage reflects a focused deep-dive into foundational deep learning theory,
with particular concentration on transformer-based architectures. The high
heading density (7.4 avg) suggests structured, active note-taking rather than
passive consumption. Recommended next focus: implementation practice and
comparative analysis of BERT vs GPT fine-tuning strategies.

---
_Report generated by **Flowith Hub** · 2025-01-20 09:42:11_
```

---

## Project Structure

```
flowith-hub/
├── main.py                        # Entry point — full pipeline orchestrator
├── materials.json                 # Sample materials input
├── scripts/
│   ├── analyzer/
│   │   ├── detect_stage.py        # Stage detection — sliding window algorithm
│   │   └── analyze_stage.py       # Stage analysis + AI prompt layer
│   ├── reporter.py                # Markdown report generator
│   └── scraper.py                 # GitHub Trending context scraper
└── docs/                          # Extended documentation
```

---

## Design System

Built on the **Modern AI** pattern: minimal, dark, professional.

| Token | Value |
|-------|-------|
| Surface | `#0F1117` |
| Card | `#1A1D27` |
| Accent | `#7C3AED` |
| Text Primary | `#F8FAFC` |
| Text Secondary | `#94A3B8` |
| Success | `#10B981` |
| Warning | `#F59E0B` |
| Typography | Inter (UI) · JetBrains Mono (code) |

---

## Roadmap

- [ ] CLI with rich terminal output (colors, progress bars)
- [ ] Markdown report export (stable)
- [ ] LLM integration — OpenAI, Ollama, local models
- [ ] Web dashboard (Minimal Dark UI)
- [ ] Plugin system for custom analyzers
- [ ] Export to Notion / Obsidian format

---

## Contributing

PRs are welcome. Open an issue first to discuss what you'd like to change.
Keep it minimal. Keep it sharp.

---

---

<!-- auto_optimize:start -->

## Overview — Latest Trending Stats

> Last updated: **2026-03-15 10:22 UTC** · Source: `simulated`

| Rank | Repository | Language | ★ Today |
|------|-----------|----------|---------|
| 1 | `anthropics/claude-code` | TypeScript | +342 |
| 2 | `openai/openai-python` | Python | +278 |
| 3 | `vercel/next.js` | JavaScript | +215 |
| 4 | `microsoft/vscode` | TypeScript | +198 |
| 5 | `huggingface/transformers` | Python | +187 |
| 6 | `rust-lang/rust` | Rust | +163 |
| 7 | `ggerganov/llama.cpp` | C++ | +154 |
| 8 | `langchain-ai/langchain` | Python | +142 |
| 9 | `astral-sh/uv` | Rust | +136 |
| 10 | `facebook/react` | JavaScript | +121 |

<!-- auto_optimize:end -->

---

## License

[MIT](LICENSE) — built with intent by the Flowith team.
