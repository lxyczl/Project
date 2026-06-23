# Best Practices

## Workflow

### For Individual Paragraphs
1. Copy the paragraph
2. Specify domain and intensity: `改写这段话，学科：生态水文，强度：中度`
3. Review rewritten text and similarity report
4. Provide feedback (1-5 scores)

### For Entire Sections
1. Extract text: `$PY scripts/document_parser.py paper.docx abstract`
2. Specify section type for appropriate style
3. Process paragraphs sequentially, maintaining consistency
4. Verify cross-paragraph terminology consistency

### For High-Similarity Text (Turnitin)
1. Parse Turnitin report to identify red/orange sections
2. Use Heavy intensity for red sections (25-49%)
3. Use Medium intensity for orange sections (50-74%)
4. Skip green (citations) and blue (0%) sections

## Common Mistakes

| ❌ Don't | ✅ Do |
|----------|-------|
| "改写这段话" | "改写这段话，学科：生态水文" |
| Heavy intensity for low similarity | Light intensity for low similarity |
| Accept first rewrite without checking | Run similarity check, request multiple options |
| Skip terminology verification | Check that domain terms are preserved |

## Quality Checklist

After rewriting, verify:
- [ ] Professional terminology preserved
- [ ] Citations intact: [1], [2,3], (Author, Year)
- [ ] Formulas preserved: $...$, $$...$$
- [ ] No more than 5 consecutive words matching original
- [ ] Meaning unchanged
- [ ] Academic tone maintained
