## TEA: Our Core Product Philosophy

### Transparency
- What we do with your data:
  - We parse your resume locally, extract hard/soft skills and structured sections, and generate a LaTeX PDF. We store the original and enhanced resumes in your account and upload your final PDF to secure storage under your user scope. Logs include only operational metadata.
  - Third-party AI usage is limited to narrow, auditable tasks (parsing, keyword extraction, bullet refinement). We minimize prompts and redact sensitive content where possible.
- How our process works (high level):
  - Upload → Parse → Extract JD hard skills → Semantic match → Enhance bullets + skills → Generate PDF → Return analysis and assets.
  - Analysis now includes a concise fit score (before/after) and a one-line rationale built deterministically from the overlap with the job’s hard skills.
- Why it matters to us:
  - Hiring is personal and high-stakes. You deserve clarity on how your materials are processed and why specific changes are made.
  - We favor deterministic post-processing and clear logs over opaque “magic.”
- Future steps (Transparency):
  - User-facing data retention controls (per-job purge, redact sections).
  - Downloadable audit trail of what changed and why.
  - Explicit toggles for external AI calls and in-product model cards.

### Efficiency
- Our non-negotiable: minimal steps to value.
  - Single upload and one job description field get you a tailored, enhanced resume + PDF.
  - Parallelized internals (extraction, matching, enhancement) reduce waiting time.
  - Auto-generated PDF and direct-link retrieval avoid manual downloads.
- Product decisions that keep it simple:
  - We avoid unnecessary settings; smart defaults + sensible constraints.
  - Robust LaTeX templates handle diverse inputs (skills with subcategories, variable education fields, multi-bullet projects) without breaking formatting.
- Future steps (Efficiency):
  - Inline editing in the final preview with instant re-render.
  - One-click re-targeting to a new job description.
  - Smart caching for repeated users and similar roles.

### Accuracy
- The bar is high, because stakes are high.
  - We prioritize hard-skill coverage and semantic relevance for the role.
  - Monotonic fit scoring: enhancements never reduce coverage; scores are computed consistently from the same JD hard skills set.
  - Deterministic summaries avoid hallucinated claims and keep feedback crisp.
  - Unicode and LaTeX normalization eliminate formatting artifacts that could distract recruiters/ATS.
- Guardrails against black-box drift:
  - Soft skills are excluded from highlighting logic.
  - Merging logic preserves user-defined skill categories and appends additions safely.
  - Defensive rendering turns unrecognized education fields into bullets rather than failing.
- Future steps (Accuracy):
  - Side-by-side diff of bullets with reason codes tied to JD keywords.
  - Evaluation harness with role-specific gold sets to detect regressions.
  - Optional human-in-the-loop pass for critical applications.

### Posting on LinkedIn: what to highlight
- Start with the problem: tailoring resumes is slow, error-prone, and opaque.
- How we solve it with TEA:
  - Transparency: clear pipeline, minimal external calls, deterministic outputs for key user-facing messages.
  - Efficiency: upload → optimize → PDF, with resilient formatting and multi-bullet support.
  - Accuracy: focus on hard skills, consistent scoring, and strong guardrails against AI noise.
- Show, don’t tell:
  - Include a quick before/after score visual (e.g., 72% → 86%) and one joined line of the deterministic summary.
  - Mention multi-bullet projects support and improved skills rendering (categories + subcategories, without flattening).
- Close with trust:
  - Emphasize data handling transparency and opt-outs coming soon.
  - Invite feedback from hiring managers and candidates; link to a live demo or waitlist.

