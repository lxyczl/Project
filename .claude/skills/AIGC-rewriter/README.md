# AIGC-rewriter

English academic paper AIGC detection rate reduction tool, targeting **Turnitin AI detection** and **GPTZero**.

## Overview

This skill helps reduce AI-generated content (AIGC) detection rates in English academic papers. It uses a five-dimensional analysis engine to identify AI writing patterns and provides targeted rewrite suggestions.

## Features

- **Five-dimensional risk analysis**: vocabulary, AI traces, English-specific, syntax, structure
- **Platform-aware scoring**: Turnitin and GPTZero weighted detection
- **Interactive/semi-auto/full-auto modes**: flexible workflow
- **Feedback learning system**: improves strategies over time
- **Document parsing**: supports .txt, .md, .docx, .pdf
- **Reference database**: 15+ discipline domains, ~140 synonym groups, 15 rewrite techniques

## Quick Start

```bash
# Interactive mode
/AIGC-rewriter

# Semi-auto mode (analyze file)
/AIGC-rewriter path/to/paper.md

# Full-auto mode
/AIGC-rewriter path/to/paper.md --auto
```

## Analysis Engine

### Five Dimensions

| Dimension | Weight | Description |
|-----------|--------|-------------|
| Vocabulary | 0.25 | CTTR, connector frequency, cliche detection |
| AI Traces | 0.30 | Fluency, burstiness, personal voice |
| English | 0.25 | Passive voice, nominalization, hedging |
| Syntax | 0.20 | Sentence length CV, parallelism, nesting |
| Structure | +0.15 | Paragraph length/opening uniformity |

### Issue Types (14)

- `cliche_detected` — AI cliches found
- `connector_overuse` — excessive connectors
- `uniform_sentence_length` — sentences too uniform
- `low_burstiness` — consecutive similar-length sentences
- `too_fluent` — writing too polished
- `no_personal_voice` — lack of subjective markers
- `excessive_passive` — passive voice overuse
- `nominalization_overuse` — nominalization excess
- `hedging_overuse` — hedging markers excess
- `deep_nesting` — clause nesting too deep
- `excessive_parallelism` — parallel structures excess
- `uniform_para_length` — paragraphs too uniform
- `uniform_para_start` — paragraph openings repetitive
- `low_cttr` — vocabulary diversity low

## Dependencies

| Package | Type | Description |
|---------|------|-------------|
| Python 3.14+ | Runtime | Uses `str \| None` union syntax |
| nltk | Optional | English tokenization, degrades to regex |
| python-docx | Optional | .docx parsing |
| PyMuPDF | Optional | .pdf parsing |
| pytest | Dev | Test framework |

## Directory Structure

```
AIGC-rewriter/
├── SKILL.md              # Claude interaction protocol
├── README.md
├── analyzer/             # Five-dimensional analysis engine
├── rewriter/             # Rewrite support modules
├── utils/                # Utility modules
├── scripts/              # CLI scripts
├── patterns/             # Pattern library (92 rules)
├── references/           # Reference documents
├── evals/                # Evaluation benchmarks
├── feedback/             # Feedback learning data
└── tests/                # Test suite
```

## License

Internal tool for academic research assistance.
