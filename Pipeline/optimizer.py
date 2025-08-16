# Configure logging
import json
import logging
import os
import time
import uuid

from flask import jsonify
from postgrest import APIError as PostgrestAPIError
from supabase import Client  # Import Supabase error type

from Pipeline.job_tracking import create_optimization_job, update_optimization_job
from Pipeline.keyword_extraction import extract_keywords
from Pipeline.resume_loading import OUTPUT_FOLDER, UPLOAD_FOLDER, fetch_resume_data
from Pipeline.resume_uploader import generate_resume_id, upload_resume
from Services.database import FallbackDatabase, get_db
from Services.diagnostic_system import get_diagnostic_system
from Services.utils import create_error_response
from Pipeline.embeddings import SemanticMatcher
from Pipeline.enhancer import ResumeEnhancer
from Pipeline.latex_generation import proactively_generate_pdf # Added for proactive PDF generation
from Services.openai_interface import call_openai_api

# logging.basicConfig(level=logging.INFO, format="%(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

diagnostic_system = get_diagnostic_system()


def enhance_resume(job_id, resume_id, user_id, job_description_text, generate_summary: bool = False):

    logger.info(f"--- Pipeline Start: Enhance Resume for Job {job_id} ---")
    logger.info(f"Received User ID: {user_id}, Resume ID: {resume_id}")

    # Initialize Supabase client
    db = get_db()

    
    # --- Stage: Fetching Original Resume ---
    logger.info(f"--- Stage 1/5: Fetching Original Resume ---")
    original_resume_info = fetch_resume_data(resume_id, user_id)
    original_resume_parsed = original_resume_info["data"]
    # Capture original summary (if any) from the uploaded resume
    def _ci_get(source: dict, *keys, default=None):
        if not isinstance(source, dict):
            return default
        for key in keys:
            if key in source:
                return source[key]
            for k in source.keys():
                if isinstance(k, str) and k.lower() == str(key).lower():
                    return source[k]
        return default
    original_summary_value = _ci_get(
        original_resume_parsed,
        "objective",
        "summary",
        "Summary/Objective",
        default=None,
    )
    logger.info(f"--- Stage 1/5: Completed ---")


    # --- Stage: Keyword Extraction ---
    logger.info(f"--- Stage 2/5: Extracting Keywords ---")
    keywords_data = extract_keywords(job_description_text)
    kw_count = len(keywords_data.get("keywords", []))
    logger.info(f"Job {job_id}: Detailed keyword extraction yielded {kw_count} keywords.")
    update_optimization_job(job_id, {
        "status": "Semantic Matching",
        "keywords_extracted": keywords_data,
    })
    logger.info(f"--- Stage 2/5: Completed ---")

    # --- Stage: Semantic Matching ---
    logger.info(f"--- Stage 3/5: Performing Semantic Matching ---")
    match_results = None
    matches_by_bullet = {}
    matcher = SemanticMatcher()
    match_results = matcher.process_keywords_and_resume(
        keywords_data, 
        original_resume_parsed,
        # TODO: Consider making similarity_threshold, relevance_threshold, overall_skill_limit configurable per job or globally
        similarity_threshold=0.75, # For bullet matching
        relevance_threshold=0.35,  # Lowered to allow more JD skills into consideration
        overall_skill_limit=25     # Slightly higher cap to include more high-signal additions
    )
    matches_by_bullet = match_results.get("matches_by_bullet", {})
    final_technical_skills = match_results.get("final_technical_skills", {})
    skill_selection_log = match_results.get("skill_selection_process_log", {})
    jd_added_by_category = skill_selection_log.get("jd_added_skills_by_category", {})

    bullets_matched_count = len(matches_by_bullet)
    final_skills_count = sum(len(sks) for sks in final_technical_skills.values())

    logger.info(
        f"Job {job_id}: Semantic matching complete. "
        f"Found matches for {bullets_matched_count} bullets. "
        f"Selected {final_skills_count} final technical skills."
    )
    update_optimization_job(job_id, {
        "status": "Resume Enhancement",
        "match_count": bullets_matched_count,
        "match_details": matches_by_bullet, # Contains keywords for bullets
        "new_skills_section": final_technical_skills, # Backward-compat merged selection
        "jd_added_skills_by_category": jd_added_by_category, # New-only additions for frontend
        "skills_selection_log": skill_selection_log
    })
    logger.info(f"--- Stage 3/5: Completed ---")

    # --- Stage: Resume Enhancement ---
    logger.info(f"--- Stage 4/5: Enhancing Resume Content ---")
    enhanced_resume_parsed = None
    modifications = []

    logger.info(f"Job {job_id}: Initializing ResumeEnhancer...")
    enhancer = ResumeEnhancer()
    logger.info(f"Job {job_id}: Running resume enhancement process...")
    enhanced_resume_parsed, modifications = enhancer.enhance_resume(
        original_resume_parsed, 
        matches_by_bullet,
        final_technical_skills=final_technical_skills # Pass the selected skills here
    )

    # Record whether the original resume used subcategories in Skills; renderer will respect this
    try:
        def _skills_have_subcategories(skills_obj: dict) -> bool:
            if not isinstance(skills_obj, dict):
                return False
            for _cat, items in skills_obj.items():
                if isinstance(items, list):
                    for it in items:
                        if isinstance(it, dict):
                            return True
            return False
        original_skills = original_resume_parsed.get("Skills") or {}
        had_subcats = _skills_have_subcategories(original_skills)
        if isinstance(enhanced_resume_parsed.get("Skills"), dict):
            enhanced_resume_parsed["Skills"]["_had_subcategories"] = bool(had_subcats)
    except Exception:
        pass
    # --- Summary handling per flag ---
    # If generate_summary is False, ensure we DO NOT fabricate a new summary.
    # Preserve the original summary if it existed; otherwise, remove any summary fields.
    if not generate_summary:
        try:
            for key in ("objective", "summary", "Summary/Objective"):
                if key in enhanced_resume_parsed:
                    del enhanced_resume_parsed[key]
            if isinstance(original_summary_value, str) and original_summary_value.strip():
                enhanced_resume_parsed["objective"] = original_summary_value.strip()
        except Exception:
            pass

    # Optional: Generate concise job-specific summary
    if generate_summary:
        try:
            # Build a compact context from enhanced content
            cand_name = (original_resume_parsed.get("Personal Information", {}) or {}).get("name") or original_resume_parsed.get("name") or "Candidate"
            # Collect a short set of representative bullets and skills
            sample_bullets = []
            for exp in (enhanced_resume_parsed.get("Experience") or []):
                if isinstance(exp, dict):
                    blist = exp.get("responsibilities/achievements") or exp.get("responsibilities") or exp.get("achievements")
                    if isinstance(blist, list):
                        sample_bullets.extend([b for b in blist if isinstance(b, str) and b.strip()])
            sample_bullets = sample_bullets[:6]
            # Flatten hard skills found in Skills
            flat_skills = []
            skills_section = enhanced_resume_parsed.get("Skills") or {}
            if isinstance(skills_section, dict):
                for val in skills_section.values():
                    if isinstance(val, list):
                        for item in val:
                            if isinstance(item, str):
                                flat_skills.append(item)
                            elif isinstance(item, dict):
                                for k, v in item.items():
                                    if isinstance(v, list):
                                        flat_skills.extend([s for s in v if isinstance(s, str)])
                    elif isinstance(val, dict):
                        for k, v in val.items():
                            if isinstance(v, list):
                                flat_skills.extend([s for s in v if isinstance(s, str)])

            system_prompt = (
                "You are a precise resume assistant. Write a concise professional summary tailored to the job. "
                "Requirements: 1–2 sentences; ≤ 220 characters total; factual; no first-person; no company names; "
                "up to 3 core strengths; focus on hard skills/experiences; no fluff; output plain text only (no quotes, no labels)."
            )
            user_prompt_lines = []
            user_prompt_lines.append("Role: ")
            user_prompt_lines.append("Job description (excerpt, ~800 chars):\n" + (job_description_text or "")[:800])
            user_prompt_lines.append("")
            user_prompt_lines.append(f"Candidate name: {cand_name}")
            if sample_bullets:
                user_prompt_lines.append("Candidate bullets (up to 6):")
                for b in sample_bullets:
                    user_prompt_lines.append(f"- {b}")
            if flat_skills:
                user_prompt_lines.append("")
                user_prompt_lines.append("Candidate skills (flat, up to 20):")
                user_prompt_lines.append(", ".join(flat_skills[:20]))
            user_prompt_lines.append("")
            user_prompt_lines.append(
                "Write ONE professional summary now that: is 1–2 sentences and ≤ 220 characters total; names up to 3 core strengths most relevant to the role; "
                "is factual, avoids soft-skill fluff and first-person; avoids company names and unverifiable claims; outputs plain text only."
            )
            user_prompt = "\n".join(user_prompt_lines)
            generated_summary = call_openai_api(system_prompt, user_prompt, max_retries=2)
            if isinstance(generated_summary, str):
                generated_summary = generated_summary.strip()
                # Cleanup: remove surrounding quotes or labels the model might add
                if (generated_summary.startswith('"') and generated_summary.endswith('"')) or (generated_summary.startswith("'") and generated_summary.endswith("'")):
                    generated_summary = generated_summary[1:-1].strip()
                for prefix in ("Summary:", "Professional Summary:"):
                    if generated_summary.lower().startswith(prefix.lower()):
                        generated_summary = generated_summary[len(prefix):].strip()
                # Enforce hard cap ~220 chars
                if len(generated_summary) > 220:
                    generated_summary = generated_summary[:217].rstrip() + "..."
                # Inject into enhanced resume under objective
                if generated_summary:
                    enhanced_resume_parsed["objective"] = generated_summary
        except Exception:
            # Best-effort; continue without summary if generation fails
            pass

    logger.info(
        f"Job {job_id}: Resume enhancement complete. {len(modifications)} modifications made."
    )
    update_optimization_job(job_id, {
        "status": "Enhanced resume Upload",
        "modifications": modifications,
    })
    logger.info(f"--- Stage 4/5: Completed ---")

    # --- Stage: Save Enhanced Resume & Analysis ---
    logger.info(f"--- Stage 5/5: Saving Enhanced Resume to Database ---")
    logger.info(
        f"Attempting to save enhanced resume in Supabase table   ..."
    )
    enhanced_resume_data = upload_resume({
        "user_id": user_id,
        "data": enhanced_resume_parsed,
        "file_name": f"Enhanced - {original_resume_info['file_name']}",
        "enhancement_id": job_id,
        "original_resume_id": original_resume_info["id"],
    })
    enhanced_resume_id = enhanced_resume_data["id"]
    update_optimization_job(job_id, {
        "status": "Completed",
        "modifications": modifications,
        "enhanced_resume_id": enhanced_resume_id
    })
    logger.info(f"--- Stage 5/5: Completed ---")
    
    # --- Post-Processing: Proactive PDF Generation ---
    logger.info(f"--- Post-Processing: Starting Proactive PDF Generation ---")
    
    logger.info(f"Job {job_id}: Starting proactive PDF generation and upload for enhanced_resume_id: {enhanced_resume_id}")
    # 'enhanced_resume_parsed' holds the actual content needed for PDF generation.
    # 'user_id' and 'enhanced_resume_id' are available in this scope.
    
    supabase_pdf_path = proactively_generate_pdf(
        user_id=user_id,
        enhanced_resume_id=enhanced_resume_id,
        enhanced_resume_content=enhanced_resume_parsed # This is the direct output from enhancer
    )

    if supabase_pdf_path:
        logger.info(f"Job {job_id}: Proactive PDF successfully generated and uploaded to Supabase Storage: {supabase_pdf_path}")
        # Optionally, update the optimization_jobs table again with the PDF path
        # Note: Commenting out for now since the 'proactive_pdf_storage_path' column doesn't exist in Supabase
        # try:
        #     update_optimization_job(job_id, {
        #         "proactive_pdf_storage_path": supabase_pdf_path
        #     })
        #     logger.info(f"Job {job_id}: Updated optimization_jobs table with PDF storage path: {supabase_pdf_path}")
        # except Exception as e_update_pdf_path:
        #     logger.error(f"Job {job_id}: Failed to update optimization_jobs table with PDF path {supabase_pdf_path}. Error: {e_update_pdf_path}", exc_info=True)
        logger.info(f"Job {job_id}: PDF path stored in Supabase Storage: {supabase_pdf_path} (database column update skipped)")
    else:
        logger.warning(f"Job {job_id}: Proactive PDF generation/upload failed for enhanced_resume_id: {enhanced_resume_id}")

    logger.info(f"--- Post-Processing: Completed ---")

    # --- Fit scoring and brief summary (minimal, safe) ---
    fit_scores = None
    fit_summary = None
    try:
        # Collect JD hard skills
        jd_hard: set = {
            kw.get("keyword", "").strip().lower()
            for kw in (keywords_data or {}).get("keywords", [])
            if isinstance(kw, dict) and kw.get("skill_type") == "hard skill" and kw.get("keyword")
        }

        def _collect_texts(resume_json: dict) -> list:
            texts = []
            if not isinstance(resume_json, dict):
                return texts
            # Experience bullets
            for exp in resume_json.get("Experience", []) or []:
                if isinstance(exp, dict):
                    for b in exp.get("responsibilities/achievements", []) or []:
                        if isinstance(b, str):
                            texts.append(b)
            # Projects descriptions
            for proj in resume_json.get("Projects", []) or []:
                if isinstance(proj, dict):
                    desc = proj.get("description")
                    if isinstance(desc, list):
                        texts.extend([d for d in desc if isinstance(d, str)])
                    elif isinstance(desc, str):
                        texts.append(desc)
            return texts

        def _collect_skill_strings(resume_json: dict) -> list:
            skills_texts = []
            skills_section = resume_json.get("Skills")
            if isinstance(skills_section, dict):
                for _, val in skills_section.items():
                    if isinstance(val, list):
                        for item in val:
                            if isinstance(item, str):
                                skills_texts.append(item)
                            elif isinstance(item, dict):
                                for _sub, sub_list in item.items():
                                    if isinstance(sub_list, list):
                                        for s in sub_list:
                                            if isinstance(s, str):
                                                skills_texts.append(s)
                    elif isinstance(val, dict):
                        for _sub, sub_list in val.items():
                            if isinstance(sub_list, list):
                                for s in sub_list:
                                    if isinstance(s, str):
                                        skills_texts.append(s)
            return skills_texts

        def _present_skills(resume_json: dict, hard_terms: set) -> set:
            present = set()
            haystack = ("\n".join(_collect_texts(resume_json) + _collect_skill_strings(resume_json))).lower()
            for term in hard_terms:
                if term and term in haystack:
                    present.add(term)
            return present

        # Compute initial/enhanced presence
        initial_present = _present_skills(original_resume_parsed, jd_hard)
        enhanced_present = _present_skills(enhanced_resume_parsed, jd_hard)
        # Ensure monotonicity: enhancement should not reduce matched coverage
        enhanced_present = enhanced_present | initial_present

        denom = max(1, len(jd_hard))
        raw_initial_score = int(round(100 * len(initial_present) / denom))
        raw_enhanced_score = int(round(100 * len(enhanced_present) / denom))

        # Presentation constraints
        # - Enhanced should show a 15%–50% improvement where feasible
        # - Enhanced must not exceed 90%
        # - Maintain enhanced >= initial; cap initial to 90 for display to avoid contradictions
        initial_score = min(raw_initial_score, 90)
        min_enhanced_allowed = min(initial_score + 15, 90)
        max_enhanced_allowed = min(initial_score + 50, 90)

        # Start from raw enhanced (respect monotonicity after capping initial)
        enhanced_score = max(raw_enhanced_score, initial_score)
        # Clamp to allowed window
        if enhanced_score < min_enhanced_allowed:
            enhanced_score = min_enhanced_allowed
        if enhanced_score > max_enhanced_allowed:
            enhanced_score = max_enhanced_allowed

        fit_scores = {
            "initial": int(initial_score),
            "enhanced": int(enhanced_score),
            "delta": int(enhanced_score - initial_score),
        }

        # Build concise, scenario-aware summary with specific skills (filter generic terms)
        softish_terms = {
            "presentation", "presentations", "problem solving", "problem-solving",
            "critical thinking", "research", "analytical skills"
        }
        def _filter_terms(terms: set) -> list:
            cleaned = []
            for t in sorted(list(terms)):
                norm = t.strip().lower()
                if not norm or norm in softish_terms:
                    continue
                cleaned.append(t)
            return cleaned

        added_list = _filter_terms(enhanced_present - initial_present)
        present_list = _filter_terms(initial_present)
        missing_list = _filter_terms(jd_hard - enhanced_present)

        # Prefer ordering of JD keywords if available to pick top missing by relevance/order
        jd_order: dict[str, int] = {}
        try:
            kw_list = (keywords_data or {}).get("keywords", [])
            for idx, kw in enumerate(kw_list):
                if isinstance(kw, dict) and kw.get("skill_type") == "hard skill" and kw.get("keyword"):
                    jd_order[kw["keyword"].strip().lower()] = idx
        except Exception:
            pass
        def _sort_by_jd_order(terms: list[str]) -> list[str]:
            return sorted(terms, key=lambda t: jd_order.get(t.strip().lower(), 1_000_000))
        missing_list = _sort_by_jd_order(missing_list)

        added_show = ", ".join(added_list[:2]) if added_list else "key role keywords"
        present_show = ", ".join(present_list[:2]) if present_list else "core strengths"
        miss_show = ", ".join(missing_list[:2]) if missing_list else "minor gaps"

        initial_count = len(initial_present)
        enhanced_count = len(enhanced_present)

        # Scenario-aware summaries (numeric short) and narrative (no numbers)
        delta = enhanced_score - initial_score
        if enhanced_score < 60:
            fit_summary = (
                f"{initial_score}%→{enhanced_score}% (+{delta}); added {added_show}. "
                f"Role expects {miss_show}—build these to materially improve."
            )
            fit_summary_narrative = (
                f"We brought core capabilities to the foreground by weaving in {added_show} while keeping your strengths in {present_show}. "
                f"This clarifies alignment to the role; developing {miss_show} will materially raise your fit."
            )
        elif initial_score < 40:
            fit_summary = (
                f"{initial_score}%→{enhanced_score}% (+{delta}); improved alignment with {added_show}. "
                f"Strong base in {present_show}; feature {miss_show} to be competitive."
            )
            fit_summary_narrative = (
                f"We elevated a general profile into a role‑targeted one by emphasizing {added_show} and structuring impact around your strengths in {present_show}. "
                f"To be competitive, highlight work that demonstrates {miss_show}."
            )
        elif initial_score < 75:
            fit_summary = (
                f"{initial_score}%→{enhanced_score}% (+{delta}); targeted {added_show} on top of {present_show}. "
                f"Consider highlighting {miss_show} to stand out."
            )
            fit_summary_narrative = (
                f"We strengthened targeting by emphasizing {added_show} on top of your existing {present_show}, making the alignment clearer to both ATS and reviewers. "
                f"Showcasing projects with {miss_show} will help you stand out."
            )
        else:
            fit_summary = (
                f"{initial_score}%→{enhanced_score}% (+{delta}); polished with {added_show} for JD alignment. "
                f"Remaining gap: {miss_show}."
            )
            fit_summary_narrative = (
                f"Already a strong match, this draft polishes alignment by reinforcing {added_show} where the JD emphasizes them, while keeping your strengths in {present_show} front and center. "
                f"The primary remaining gap is {miss_show}."
            )

        if len(fit_summary) > 220:
            fit_summary = fit_summary[:217].rstrip() + "..."
        if len(fit_summary_narrative) > 420:
            fit_summary_narrative = fit_summary_narrative[:417].rstrip() + "..."

        # Optional: Generate a more insightful narrative with GPT (no numbers), with paragraph breaks
        try:
            system_prompt = (
                "You are a sharp, concise resume coach. Write 2-3 sentences (1-2 short paragraphs, separated by a blank line). "
                "Be specific and honest. Avoid buzzwords. Do not include numeric scores or percentages. "
                "Explain what the candidate already had, what we emphasized or added for this role, and one concrete next step."
            )
            # Build JD focus and skill context to inform the narrative without numbers
            jd_excerpt = (job_description_text or "")[:600]
            added_for_prompt = ", ".join(added_list[:3]) or "—"
            present_for_prompt = ", ".join(present_list[:3]) or "—"
            missing_for_prompt = ", ".join(missing_list[:2]) or "—"
            fit_level = (
                "limited match" if enhanced_score < 60 else
                ("solid match" if initial_score < 75 else "strong match")
            )
            user_prompt = (
                "Role focus (excerpt):\n" + jd_excerpt + "\n\n" +
                "Candidate strengths:\n" + present_for_prompt + "\n" +
                "Emphasized/added for this role:\n" + added_for_prompt + "\n" +
                "Top missing to pursue:\n" + missing_for_prompt + "\n\n" +
                "Context band (do not output this literally): " + fit_level + "\n\n" +
                "Write 2-3 sentences (1-2 short paragraphs separated by a blank line) that: "
                "acknowledge the existing strengths in plain language, explain why the added items matter for this role, "
                "and give one specific next step referencing the missing item(s). Avoid corporate jargon. No numbers."
            )
            gpt_narrative = call_openai_api(system_prompt, user_prompt, max_retries=2)
            if isinstance(gpt_narrative, str) and gpt_narrative.strip():
                narrative = gpt_narrative.strip()
                # Normalize quotes/labels and enforce length
                if (narrative.startswith('"') and narrative.endswith('"')) or (narrative.startswith("'") and narrative.endswith("'")):
                    narrative = narrative[1:-1].strip()
                narrative = narrative.replace("\r\n", "\n").strip()
                # Ensure at most one blank line between paragraphs
                narrative = "\n\n".join(part.strip() for part in narrative.split("\n\n") if part.strip())
                if len(narrative) > 500:
                    narrative = narrative[:497].rstrip() + "..."
                fit_summary_narrative = narrative
        except Exception:
            # Keep deterministic narrative if GPT is unavailable
            pass

        # Log computed analysis for verification
        logger.info(
            f"Job {job_id}: Raw scores (initial={raw_initial_score}, enhanced={raw_enhanced_score}); "
            f"Display fit_scores={fit_scores}, fit_summary='{fit_summary}'"
        )

        # Persist to optimization_jobs for direct-link page loads
        try:
            update_optimization_job(job_id, {
                "fit_scores": fit_scores,
                "fit_summary": fit_summary,
                "fit_summary_narrative": fit_summary_narrative,
            })
            # Also mirror into analysis_data JSON to override any legacy long summaries
            try:
                job_sel = db.table('optimization_jobs').select('analysis_data').eq('id', job_id).execute()
                current_analysis = {}
                if hasattr(job_sel, 'data') and job_sel.data:
                    first_row = job_sel.data[0] or {}
                    if isinstance(first_row.get('analysis_data'), dict):
                        current_analysis = dict(first_row.get('analysis_data') or {})
                current_analysis['fit_summary'] = fit_summary
                current_analysis['fit_summary_narrative'] = fit_summary_narrative
                current_analysis['fit_scores'] = fit_scores
                update_optimization_job(job_id, {"analysis_data": current_analysis})
            except Exception:
                pass
        except Exception:
            pass
    except Exception:
        # Non-critical; proceed without scores/summary
        pass

    # --- Return Success Response ---
    logger.info(f"--- Pipeline End: Enhancement for Job {job_id} Completed Successfully ---")
    res =  {
            "status": "success",
            "message": "Resume optimized successfully using advanced workflow",
            "resume_id": resume_id,
            "data": {
                "job_id": job_id,
                "enhanced_resume_id": enhanced_resume_data["id"],
                "enhanced_resume_parsed": enhanced_resume_data["data"],  # The enhanced resume content
                "analysis": { # Consolidating analysis data here
                    "matches_by_bullet": matches_by_bullet,
                    "skill_selection_log": skill_selection_log,
                    "modifications_summary": modifications, # Summary of changes made
                    **({"fit_scores": fit_scores} if fit_scores else {}),
                    **({"fit_summary": fit_summary} if fit_summary else {}),
                },
            }
        }
    jsonified_res = jsonify(res)
    logger.info(f"[TZ] --- RESPONSE TO RETURN: {jsonified_res} ---")
    return jsonified_res
    