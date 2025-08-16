## Future Features and Improvements

This document collects vetted, low-risk ideas that build on the current pipeline without disrupting flow or performance. Items are grouped by priority and scope.

### Near-term (low‑risk, surgical)
- Skills selection hygiene (extensions)
  - Expand generic/soft-term denylist (e.g., "stakeholder management", "presentations") with config file.
  - Add alias map for tools/skills (Postgres↔PostgreSQL, Power BI↔PowerBI, TensorFlow↔TF, Excel↔Microsoft Excel) for better dedup and new-only diffs.
  - Prefer JD wording on close duplicates (implemented) and expand tie-break rules to consider JD context length.
  - Persist true new-only skills (implemented as `jd_added_skills_by_category`); expose via API doc for FE.

- Categorizer robustness
  - Strip noisy prefixes in categories (implemented); extend normalization (trim punctuation, case, whitespace).
  - Optional: fallback to heuristic category mapping when model response is empty/unknown.

- Fit summaries
  - Numeric scores: already clamped (+15–50%, ≤90). Add small alias-aware coverage count (done).
  - Narrative: keep 2–3 sentences with paragraph break (done); add domain phrasing presets (PM/Data/Eng) via prompt tag.

- PDF/Renderer polish
  - Optional: order Skills categories by JD relevance (count of matched skills), opt-in.
  - Ensure consistent spacing across all section headings (Summary spacing done).

### Mid‑term (product value, moderate scope)
- "Similar tool" enrichment
  - If JD mentions a library close to existing skills (embedding similarity), suggest as addition (configurable threshold), mark as suggested-not-claimed in analysis for user confirmation.

- Critical skill weighting
  - Allow certain JD hard skills to be marked “critical” (by relevance score or rule), boost their selection weight and highlight in FE checklist.

- Frontend diff and guidance
  - Use `jd_added_skills_by_category` for an “Added Skills” panel; show one-tap copy into base resume.
  - Display a critical-skills checklist (present/missing) with links to the sections where we applied changes.

- Friendly PDF naming (optional)
  - Extract `target_company`/`target_role` at optimize time and include a friendly filename suggestion (Company - Role - Candidate.pdf) in response metadata.

### Longer‑term (quality, confidence, trust)
- Evaluation harness
  - Role-specific gold sets to regression-test selection/renderer; threshold tuning with metrics (precision/recall on hard skills, false-highlight rate).

- Confidence and transparency
  - Confidence scores on each added skill (embedding margin + JD relevance) and rationale snippet.
  - Public settings to toggle external AI usage; in-product model cards.

- Inline preview editing
  - FE inline edits to Summary/Skills with instant re-render; write-back to `enhanced_resume_parsed` and diffs in analysis.

### Operational/Infra
- Caching & normalization registry
  - Cache extracted JD keywords keyed by JD hash; maintain alias/denylist maps in versioned JSON.

- Deprecate legacy summaries
  - Remove or migrate any edge function that writes long-form `analysis_data.fit_summary`; rely on backend’s one-liner + narrative (now mirrored).

### Implemented (recent)
- Skills
  - Lower relevance threshold (0.35) and raise overall skill limit (25).
  - Append genuine JD additions into visible top-level categories with de-duplication.
  - Strip categorizer prefixes ("Existing Category:") and drop generic JD items at selection.
  - Prefer JD wording on close duplicates.
  - Persist `jd_added_skills_by_category` for clean FE new-only view.

- Fit analysis
  - Monotonic scoring; display clamp (+15–50%, ≤90).
  - Scenario-aware numeric one-liner and narrative (2–3 sentences, paragraph break, no numbers), mirrored to DB.

