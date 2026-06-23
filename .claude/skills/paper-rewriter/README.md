# English Academic Paper Rewriter

Claude Code skill for rewriting English academic papers to pass Turnitin plagiarism detection.

## Quick Start

**Send text directly:**
```
Help me rewrite this paragraph from my paper: [paste text]
```

**Send a file:**
```
Rewrite the abstract of this paper: E:\Desktop\paper.docx
```

**Pipeline with .docx/.pdf directly:**
```bash
$PY scripts/run_pipeline.py original.docx rewritten.docx
$PY scripts/run_pipeline.py original.pdf rewritten.pdf
```

**With options:**
```
Rewrite this ecology/hydrology abstract with medium intensity: [paste text]
```

**One-click pipeline (after rewriting):**
```bash
$PY scripts/run_pipeline.py original.txt rewritten.txt [domain] [intensity]
```

## How It Works

1. User provides original text (and optionally rewritten text)
2. Pipeline analyzes similarity, detects hot sentences, auto-evaluates
3. If `needs_iteration` is true, rewrite hot sentences and re-analyze (max 3 rounds)
4. Collect feedback → system learns for next time

## Features

- **Analyzer engine**: 8 modules (syntax, vocabulary, AI traces, English-specific, etc.)
- **Pattern library**: 50+ built-in rules for cliché phrases, connectors, verbose expressions
- **Similarity calculator**: LCS + N-gram + Turnitin consecutive match detection
- **Sentence-level hotspot detection**: pinpoints exactly which sentences need rework
- **Auto-evaluation**: objective verdict (excellent/success/warning/fail) based on metrics
- **Feedback learning**: learns from user feedback to improve over time
- **Turnitin report parsing**: auto-detect high-priority sections from Turnitin reports

## Turnitin Rules

- **≥8 consecutive words** = fail (must break)
- **Trigram precision ≥30%** = warning

## Intensity Levels

| Level | Approach | Use case |
|-------|----------|----------|
| 🟢 Light | Synonym replacement only | Low similarity (<25%) |
| 🟡 Medium | Synonyms + structure adjustment | Medium similarity (25-50%) |
| 🔴 Heavy | Full restructuring, all techniques | High similarity (>50%) |

## Section Thresholds

| Section | Threshold | Notes |
|---------|-----------|-------|
| Abstract | 50 | Highest scrutiny |
| Introduction | 60 | Literature review risk |
| Methods | 70 | Standard procedures OK |
| Results | 70 | Data description OK |
| Discussion | 60 | Analysis needs variation |

## File Structure

```
paper-rewriter/
├── SKILL.md                    # Core instructions (read by Claude)
├── README.md                   # This file
├── analyze.py                  # Analyzer CLI entry point
├── analyzer/                   # Analysis engine
│   ├── syntax.py               # Syntax (sentence length, passive voice, nesting)
│   ├── vocabulary.py           # Vocabulary (CTTR, connectors, clichés)
│   ├── ai_traces.py            # AI trace detection (fluency, burstiness)
│   ├── english.py              # English-specific (articles, hedging, nominalization)
│   ├── structure.py            # Structure (paragraph length, opening patterns)
│   ├── paragraphs.py           # Paragraph splitting & section detection
│   ├── patterns.py             # Pattern library loader
│   └── scorer.py               # Composite scoring & priority ranking
├── scripts/
│   ├── run_pipeline.py         # One-click analysis pipeline
│   ├── similarity_calculator.py # Similarity metrics (LCS, n-gram, consecutive)
│   ├── feedback_system.py      # Feedback recording & learning
│   ├── rewrite_with_feedback.py # Rewrite analysis & suggestions
│   ├── document_parser.py      # Document parsing (docx/pdf)
│   └── turnitin_parser.py      # Turnitin report parsing
├── patterns/                   # Pattern library (50+ rules)
├── references/                 # Reference materials
│   ├── domains.md              # Domain-specific terminology (20 fields)
│   ├── synonyms.md             # Synonym replacement table
│   ├── techniques.md           # Rewriting techniques guide
│   ├── examples.md             # Rewrite examples
│   └── edge_cases.md           # Edge case handling
├── feedback/                   # Feedback data (persisted per project)
│   ├── sessions/               # Rewrite session records
│   └── learning/               # Learned strategies
└── evals/                      # Evaluation benchmarks
```

## Common Mistakes

| ❌ Don't | ✅ Do |
|----------|-------|
| "Rewrite this paragraph" | "Rewrite this paragraph, domain: ecology, intensity: medium" |
| Heavy intensity for low similarity | Light intensity for low similarity |
| Accept first rewrite without checking | Run pipeline, check hot sentences |
| Skip terminology verification | Check that domain terms are preserved |

## Troubleshooting

**Terminology was changed:**
→ Specify your domain when requesting. Check `references/domains.md` for supported terms.

**Citations were modified:**
→ Citations like [1] or (Smith, 2020) should always be preserved exactly. If changed, it's a bug.

**Formulas were modified:**
→ Math formulas ($...$, $$...$$) should always be preserved exactly.

**Rewrite sounds unnatural:**
→ Try Medium intensity. Specify section type for appropriate style (Methods → past passive, Discussion → present active).

**Similarity still too high:**
→ Use Heavy intensity. Check for ≥8 consecutive word matches. Consider restructuring the entire paragraph.

**Script import errors:**
→ Use `$PY` (not `python`). Install dependencies: `$PY -m pip install python-docx PyPDF2 nltk`

## Supported Domains

Ecological hydrology | Civil/hydraulic engineering | Green building | Building energy | BIPV | Photovoltaic | Ecological security pattern | SHAP analysis | Groundwater vulnerability | Ecosystem services | Semi-arid coupling | InVEST model | Improved DRASTIC | Circuit theory | OWA algorithm | Ecological source/corridor/resistance

Full terminology list: `references/domains.md`
