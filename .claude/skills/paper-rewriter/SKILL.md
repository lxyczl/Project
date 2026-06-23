---
name: paper-rewriter
description: |
  Rewrite English academic papers to pass Turnitin plagiarism detection.
  When the user wants to:
  - Rewrite/paraphrase English academic text
  - Reduce plagiarism rate
  - Pass Turnitin check
  - "rewrite", "paraphrase", "reduce similarity", "pass Turnitin"
  This skill applies systematic rewriting techniques including voice conversion,
  synonym replacement, clause insertion, and word order change.
---

# English Academic Paper Rewriter

## Quick Flow (must follow for every rewrite)

```
$PY scripts/run_pipeline.py <original> <rewritten> [domain] [intensity]
```

Pipeline automatically completes: similarity analysis → sentence-level hotspot detection → auto-evaluation → iteration decision.

### Steps

1. **User provides original and rewritten text** (file or paste)
2. **Run pipeline**, get evaluation result
3. **If `needs_iteration` is true**: rewrite hot sentences one by one, then re-run pipeline (max 3 rounds)
4. **If passed**: output final report

### Pipeline Output

- `verdict`: excellent / success / warning / fail
- `hot_sentences`: sentences needing rework, with recommended techniques
- `needs_iteration`: true → must continue rewriting
- `suggestions`: historically effective techniques and targeted advice

### Turnitin Rules

- Consecutive ≥8 words = fail (must break)
- Trigram precision ≥30% = warning

## Rewrite Rules

### General Techniques

Choose from these techniques (pipeline recommends based on metrics):

- **Voice conversion**: active ↔ passive
- **Clause insertion**: add relative clauses, appositives
- **Word order change**: rearrange sentence components
- **Synonym replacement**: swap keywords with synonyms
- **Sentence splitting**: one long sentence → two short ones
- **Sentence merging**: multiple short sentences → one
- **Abstraction**: replace specific examples with general statements
- **Concretization**: replace general statements with specific examples

### Core Constraints

- Preserve original academic meaning
- Do not fabricate or add content not in the original
- Technical terms must be preserved
- Fluent and conform to academic writing standards
- No colloquial expressions

## Scenarios

### Scenario 1: User sends text

```
User: Help me rewrite this paragraph (original)...
```

1. Use user's text as original, run pipeline to analyze
2. If user already provided rewritten text, directly compare with pipeline
3. If user only gave original, rewrite first then analyze
4. Iterate based on hot_sentences

### Scenario 2: User sends two files

```
User: Original in original.txt, rewritten in rewritten.txt
```

1. Run `$PY scripts/run_pipeline.py original.txt rewritten.txt [domain]`
2. Decide if iteration needed based on result

### Scenario 3: User sends .docx/.pdf

1. Run pipeline directly: `$PY scripts/run_pipeline.py original.docx rewritten.docx`
2. Pipeline auto-extracts text from document
3. Iterate sections that need improvement

### Scenario 4: Batch processing

Run pipeline per paragraph, optimize each until all pass.

## Project-level Data Storage

Pipeline stores feedback data in current project's `.paper-rewriter/` (not in skill directory).
- Each project's rewrite history is independent
- Feedback data persists with the project
- Use `--project <dir>` to specify project root

## Section-specific Thresholds

| Section    | Threshold | Notes |
|------------|-----------|-------|
| Abstract   | 50        | Highest scrutiny |
| Introduction | 60      | Literature review risk |
| Methods    | 70        | Standard procedures OK |
| Results    | 70        | Data description OK |
| Discussion | 60        | Analysis needs variation |
| Default    | 65        | General text |

## Advanced: Manual Control (optional)

For finer control, call underlying scripts directly:

```bash
# Get suggestions
$PY scripts/rewrite_with_feedback.py suggest <domain> <intensity>

# Analyze rewrite (no session recording)
$PY scripts/similarity_calculator.py <original> <rewritten>

# View strategy report
$PY scripts/rewrite_with_feedback.py report
```
