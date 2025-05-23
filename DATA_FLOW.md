# Data Flow and Outputs: Resume Optimizer

## 1. Overall Application Purpose

The Resume Optimizer application processes uploaded resumes, enhances them based on a provided job description using AI, and allows users to download the original or enhanced versions in various formats (JSON, LaTeX, PDF). It also supports proactive generation of PDFs for enhanced resumes and stores them in Supabase Storage.

## 2. Data Ingestion (`/api/upload`)

*   **Endpoint:** `POST /api/upload`
*   **Inputs:**
    *   Resume file (TXT, PDF, DOCX) via form data (`file`).
    *   User ID via form data (`user_id`).
*   **Process (`Pipeline/resume_uploader.py::parse_and_upload_resume`):**
    1.  A unique `resume_id` is generated (e.g., `resume_<timestamp>_<uuid_short>`).
    2.  The uploaded file is temporarily saved to the local filesystem (e.g., `Pipeline/uploads/<resume_id>.<ext>`).
    3.  Text is extracted from the saved file (`extract_text_from_file`).
    4.  The extracted raw text is parsed into a structured JSON format using an OpenAI API call (`parse_resume` with prompt from `Pipeline/prompts/parse_resume.txt`).
    5.  The parsed resume JSON, along with metadata, is saved to the Supabase `resumes` table.
*   **Supabase `resumes` Table Record (Initial Upload):**
    *   `id`: The generated `resume_id`.
    *   `user_id`: The provided `user_id`.
    *   `data`: The structured JSON of the parsed resume.
    *   `file_name`: Original filename of the uploaded resume.
    *   `enhancement_id`: `null`
    *   `original_resume_id`: `null`
    *   `created_at`, `updated_at`: Timestamps.
*   **Output (to you):** JSON response with `status`, `message`, `resume_id`, `file_name`, and the `parsed_resume` JSON.

## 3. Resume Optimization Process (`/api/optimize`)

This process is orchestrated by `Pipeline/optimizer.py::enhance_resume`.

*   **Endpoint:** `POST /api/optimize`
*   **Inputs:**
    *   `resume_id` (ID of the original resume to enhance) via form data.
    *   `user_id` via form data.
    *   `job_description` (text of the job description) via form data.
*   **Initial Step (`Pipeline/job_tracking.py::create_optimization_job`):**
    *   A unique `job_id` (UUID) is generated.
    *   A new record is inserted into the Supabase `optimization_jobs` table with `user_id`, `resume_id` (original), `job_description`, and initial status (e.g., "Processing Keywords").

*   **A. Keyword Extraction (`Pipeline/keyword_extraction.py::extract_keywords`):**
    *   Input: `job_description` text.
    *   Process: OpenAI API call (using prompt from `Pipeline/prompts/extract_keywords.txt`) to identify keywords, their context, relevance score, and skill type (hard/soft).
    *   Output: `keywords_data` (JSON object like `{"keywords": [...]}`).
    *   The `optimization_jobs` table is updated with status "Semantic Matching" and `keywords_extracted: keywords_data`.

*   **B. Semantic Matching (`Pipeline/embeddings.py::SemanticMatcher`):**
    *   Inputs: `keywords_data`, original parsed resume JSON (fetched from `resumes` table using `resume_id`).
    *   Process:
        1.  Generate embeddings (OpenAI `text-embedding-ada-002`) for JD keywords (keyword + context).
        2.  Deduplicate JD keywords based on embedding similarity.
        3.  Extract bullet points from the "Experience" section of the resume.
        4.  Generate embeddings for each resume bullet point.
        5.  Calculate cosine similarity between JD keyword embeddings and resume bullet embeddings.
        6.  Filter matches above a similarity threshold and group them by resume bullet (`matches_by_bullet`).
        7.  Extract existing technical skills from the resume's "Skills" section (handling categories and flat lists, generating embeddings).
        8.  Filter JD keywords for relevant "hard skills".
        9.  Categorize these JD hard skills against existing resume skill categories (using an OpenAI call).
        10. Select `final_technical_skills` by consolidating resume and JD skills, deduplicating, and applying an overall limit using a round-robin approach across categories.
    *   Outputs:
        *   `matches_by_bullet`: Dictionary mapping bullet text to a list of suggested keywords.
        *   `final_technical_skills`: Dictionary structuring the new technical skills section (e.g., `{"Category": ["Skill1", "Skill2"]}`).
    *   The `optimization_jobs` table is updated with status "Resume Enhancement", `match_details: matches_by_bullet`, and `new_skills_section: final_technical_skills`.

*   **C. Resume Enhancement (`Pipeline/enhancer.py::ResumeEnhancer`):**
    *   Inputs: Original parsed resume JSON, `matches_by_bullet`, `final_technical_skills`.
    *   Process:
        1.  Deep copies the original resume data.
        2.  Filters `matches_by_bullet` to limit keyword usage across all bullets.
        3.  For each bullet with filtered matches, uses an OpenAI API call (`gpt-3.5-turbo`) to rewrite the bullet, incorporating keywords naturally while preserving metrics and meaning.
        4.  Replaces the "Technical Skills" part of the resume's "Skills" section with the `final_technical_skills` structure.
    *   Output: `enhanced_resume_parsed` (the complete, modified resume JSON) and `modifications` (a log of changes).
    *   The `optimization_jobs` table is updated with status "Enhanced resume Upload" and `modifications: modifications_log`.

*   **D. Save Enhanced Resume (`Pipeline/resume_uploader.py::upload_resume`):**
    *   Input: `user_id`, `enhanced_resume_parsed`, original file name (prefixed with "Enhanced - "), `job_id` (as `enhancement_id`), `original_resume_id`.
    *   Process: A new record is inserted into the Supabase `resumes` table. A new unique ID (`enhanced_resume_id`) is generated for this record.
    *   **Supabase `resumes` Table Record (Enhanced Version):**
        *   `id`: The new `enhanced_resume_id`.
        *   `user_id`: The `user_id`.
        *   `data`: The `enhanced_resume_parsed` JSON.
        *   `file_name`: e.g., "Enhanced - original_resume.pdf".
        *   `enhancement_id`: The `job_id` from `optimization_jobs`.
        *   `original_resume_id`: The ID of the resume that was enhanced.
*   **E. Final Job Update (`Pipeline/job_tracking.py::update_optimization_job`):**
    *   The `optimization_jobs` table is updated with status "Completed" and the `enhanced_resume_id`.

*   **F. Proactive PDF Generation & Upload (New Integration - in `Pipeline/optimizer.py` after step E):**
    *   Triggered after the enhanced resume is saved and `enhanced_resume_id` is available.
    *   Inputs to `Pipeline/latex_generation.py::proactively_generate_pdf`:
        *   `user_id`
        *   `enhanced_resume_id` (the ID of the newly saved enhanced resume record)
        *   `enhanced_resume_parsed` (the JSON content of the enhanced resume)
    *   Process:
        1.  **Local PDF Generation:** `proactively_generate_pdf` calls `generate_resume_pdf`, which generates LaTeX content from `enhanced_resume_parsed` and compiles it to a PDF using `pdflatex`. The PDF is saved locally (e.g., to `Pipeline/output/proactive_pdfs/<enhanced_resume_id>.pdf`). This involves adaptive page sizing logic.
        2.  **Supabase Storage Upload:** The locally generated PDF is then uploaded by `proactively_generate_pdf` (via `Services/storage.py::upload_pdf_to_supabase`) to the Supabase Storage bucket named `resume-pdfs`.
            *   Storage Path: `{user_id}/{enhanced_resume_id}/enhanced_resume_{enhanced_resume_id}.pdf`
        3.  **Local Cleanup:** The local PDF file in `Pipeline/output/proactive_pdfs/` is deleted after a successful upload.
    *   Output: `supabase_storage_path` (the path of the PDF in Supabase Storage).
    *   The `optimization_jobs` table is optionally updated again with `proactive_pdf_storage_path: supabase_storage_path`.

*   **Output (to you):** JSON response including `job_id`, `enhanced_resume_id`, `enhanced_resume_parsed`, and analysis details.

## 4. Data Retrieval/Download (`/api/download/<resume_id>/<format_type>`)

*   **Endpoint:** `GET /api/download/<resume_id>/<format_type>`
    *   `format_type` can be `json`, `pdf`, `latex`.
*   **Process (`Pipeline/resume_loading.py::download_resume`):**
    1.  **Data Fetching (from Supabase `resumes` table):**
        *   It first attempts to find the latest *enhanced* version linked to the input `resume_id` (treating input `resume_id` as `original_resume_id`), by looking for records where `original_resume_id` matches and `enhancement_id` is not null, ordered by `created_at` descending.
        *   If no such enhanced version is found, it attempts to load the resume directly by matching the input `resume_id` against the `id` column.
        *   The actual resume JSON is fetched from the `data` column.
    2.  **Output Generation:**
        *   **JSON:** The fetched resume JSON data is returned directly.
        *   **LaTeX:** `Pipeline/latex_generation.py::generate_latex_resume` is called with the resume JSON to produce LaTeX content. This is returned as a `.tex` file.
        *   **PDF:** `Pipeline/latex_generation.py::generate_resume_pdf` is called. This generates LaTeX and compiles it on-demand to a PDF using `pdflatex` (with adaptive page sizing). The PDF is returned as a `.pdf` file.
*   **Output (to you):** The requested file (JSON, `.tex`, or `.pdf`).

## 5. Key Data Stores

*   **Supabase `resumes` Table:**
    *   Stores both original parsed resumes and enhanced resumes.
    *   Key columns: `id` (primary key, text), `user_id` (uuid), `data` (jsonb - stores the resume content), `file_name` (text), `enhancement_id` (uuid, links to `optimization_jobs`), `original_resume_id` (text, links to another `resumes` record), `created_at`, `updated_at`.
*   **Supabase `optimization_jobs` Table:**
    *   Tracks the status and intermediate/final results of optimization tasks.
    *   Key columns: `id` (primary key, text/uuid), `user_id` (uuid), `resume_id` (text, foreign key to `resumes.id` for the original resume), `job_description` (text), `status` (text), `keywords_extracted` (jsonb), `match_details` (jsonb), `new_skills_section` (jsonb), `modifications` (jsonb), `enhanced_resume_id` (text, foreign key to `resumes.id` for the enhanced version), `proactive_pdf_storage_path` (text, path in Supabase Storage), `created_at`, `updated_at`.
*   **Supabase Storage (`resume-pdfs` bucket):**
    *   Stores proactively generated PDF files for enhanced resumes.
    *   Path structure: `{user_id}/{enhanced_resume_id}/enhanced_resume_{enhanced_resume_id}.pdf`.
*   **Local Filesystem (Temporary):**
    *   `Pipeline/uploads/`: Temporarily stores uploaded raw files during initial processing.
    *   `Pipeline/output/proactive_pdfs/`: Temporarily stores PDFs generated by `proactively_generate_pdf` before they are uploaded to Supabase Storage (files are deleted after successful upload).
    *   System temporary directories (e.g., `/tmp` or as managed by `tempfile` module) are used during LaTeX compilation.
*   **OpenAI API:**
    *   Used for:
        *   Parsing raw resume text to JSON.
        *   Extracting keywords from job descriptions.
        *   Categorizing JD hard skills against resume skill categories.
        *   Enhancing/rewriting resume bullet points.
