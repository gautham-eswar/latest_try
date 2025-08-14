## TEA: Our Product Philosophy (from an AI PM’s desk)

Our bar is simple: ship a product candidates can trust in high‑stakes moments. TEA is how we design, prioritize, and measure that bar.

### Transparency — show your work, own your trade‑offs
- Principles
  - Explainability beats mystery. If a change improves your resume, we can point to the specific job requirement and the specific edit.
  - Data minimalism. We collect only what’s needed to produce the output you asked for, nothing ornamental.
  - Auditable boundaries. External AI use is narrow and declared.
- Operating mechanisms
  - Pipeline is inspectable end‑to‑end: Upload → Parse → Extract JD hard skills → Match → Enhance → PDF → Analysis.
  - Deterministic user‑facing summaries (no hallucinated claims); logs prefer structured facts over prose.
  - Storage paths are scoped to the user; operational logs strip content where possible.
- What we won’t do
  - We won’t hide changes behind generic “AI improved this.” We always name the exact keywords and sections.
- What we measure
  - % of runs with complete analysis artifacts; avg time to analysis.
  - % of users who review the change log before downloading.
- Future steps
  - Per‑job data retention controls and redaction toggles.
  - Downloadable audit trail with before/after deltas and reason codes.
  - In‑product model cards and explicit on/off for external calls.

### Efficiency — shortest path to a credible resume
- Principles
  - Minimize decisions users must make; maximize the quality of defaults.
  - Latency matters: if a step doesn’t move the needle, trim or parallelize it.
- Operating mechanisms
  - One upload + one JD field → enhanced JSON + PDF + analysis.
  - Resilient LaTeX templates: handle nested skills, non‑standard education fields, multi‑bullet projects without manual cleanup.
  - Monitored queues and timeouts; background PDF generation to remove perceived wait.
- What we won’t do
  - We won’t add settings that exist only to showcase configurability.
- What we measure
  - Time‑to‑first‑PDF; end‑to‑end optimize duration (p50/p95).
  - 1‑click success rate (no remediations needed before download).
- Future steps
  - Inline preview edits with instant re‑render.
  - One‑click re‑targeting to new JDs; smart caching across similar roles.
  - Graceful offline recovery and resume of long jobs.

### Accuracy — earn trust with rigorous guardrails
- Principles
  - Bias toward hard skills and verifiable signals; avoid embellishment.
  - Consistency over flash: the same input should produce the same outcome.
- Operating mechanisms
  - Monotonic fit scoring: enhanced ≥ original by construction; both computed on the same JD hard‑skill set and the same presence logic.
  - Highlighting excludes soft‑skills; merging preserves user categories and adds new skills without flattening.
  - Unicode and LaTeX normalization prevents glyph/formatting issues that harm readability and ATS parsing.
- What we won’t do
  - We won’t over‑optimize for a single ATS at the expense of human readability.
- What we measure
  - JD hard‑skill coverage (pre/post), delta magnitude, false‑highlight rate.
  - Render failures per 1k resumes; manual correction rate post‑download.
- Future steps
  - Role‑specific evaluation sets with regression gates in CI.
  - Structured diffs with per‑edit rationales; optional human‑in‑the‑loop for critical applications.
  - Confidence signals on highlights to guide manual review.

### For LinkedIn (what to say and why it’s credible)
- Problem: tailoring resumes is slow, inconsistent, and opaque.
- What we ship:
  - A transparent pipeline with deterministic user‑facing analysis.
  - A one‑step flow to an enhanced PDF that respects your original structure (skills/categories, education nuances, multi‑bullet projects).
  - Guardrails that keep improvements honest: hard‑skill focus and monotonic scoring.
- Proof points:
  - Before/after fit score (e.g., 74% → 86%) and a one‑line rationale naming the actual keywords added.
  - No soft‑skill inflation; no flattened categories.
- Call to action:
  - Try your resume with a role you care about; tell us where it surprised you. We will publish a public roadmap (TEA) and ship against it.

