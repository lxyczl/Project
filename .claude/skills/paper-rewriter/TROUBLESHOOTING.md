# Troubleshooting

## Common Issues

### 1. Professional Terminology Was Modified

**Problem:** Domain-specific terms were changed during rewriting.

**Solution:**
1. Specify your domain when requesting: `改写这段话，学科：生态水文`
2. Check that the term is in `references/domains.md`
3. If missing, report it so it can be added

### 2. Citations Were Changed

**Problem:** Citations like [1] or (Smith, 2020) were modified.

**Solution:** Citations should always be preserved exactly. If changed, this is a bug — report it.

### 3. Formulas Were Modified

**Problem:** Mathematical formulas were changed.

**Solution:** Formulas ($...$, $$...$$) should always be preserved exactly. If changed, report it.

### 4. The Rewrite Doesn't Sound Natural

**Problem:** Rewritten text sounds awkward.

**Solution:**
1. Try Medium intensity (Heavy may produce less natural text)
2. Provide section type for appropriate style (Methods → past passive, Discussion → present active)
3. Request multiple options and choose the best

### 5. Similarity Is Still Too High

**Problem:** After rewriting, similarity score is still high.

**Solution:**
1. Use Heavy intensity for high-similarity sections
2. Check for ≥5 consecutive word matches in the report
3. Consider restructuring the entire paragraph, not just swapping words

### 6. Missing Domain Vocabulary

**Problem:** Your domain is not supported or missing terms.

**Solution:**
1. Check `references/domains.md` for supported domains
2. Provide domain-specific terms in your request
3. Report missing terms so they can be added

### 7. Script Import Errors

**Problem:** `ModuleNotFoundError` when running scripts.

**Solution:**
1. Ensure you're using `$PY` (not `python`) to run scripts
2. Scripts import from each other via `sys.path` — run from the skill directory
3. Install dependencies: `$PY -m pip install python-docx PyPDF2`
