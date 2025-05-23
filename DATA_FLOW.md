# Resume Optimizer Data Flow

## 1. Overall Application Purpose

The Resume Optimizer application helps users improve their resumes by tailoring them to specific job descriptions. It parses uploaded resumes, extracts keywords from job descriptions, matches these keywords to the resume content, and then enhances the resume by incorporating these keywords and suggesting relevant skills.

## 2. Data Ingestion

This section describes how user resumes are initially processed.

*   **Endpoint:** `/api/upload`
*   **Input:**
    *   Resume file (TXT, PDF, DOCX)
    *   User ID
*   **Process:**
    1.  **File Saving:** The uploaded resume file is temporarily saved to the local filesystem.
    2.  **Text Extraction:** The text content is extracted from the saved file. Different parsers are used depending on the file format (TXT, PDF, DOCX).
    3.  **OpenAI Parsing:** A call is made to the OpenAI API to parse the raw extracted text into a structured JSON format representing the resume's content (e.g., sections for experience, education, skills).
*   **Output:**
    *   The parsed resume JSON is stored in the Supabase `resumes` table.
    *   A unique `resume_id` is generated for this entry.

## 3. Resume Optimization Process

This section details how an existing resume is optimized for a specific job description.

*   **Endpoint:** `/api/optimize`
*   **Input:**
    *   `resume_id` (referencing the original parsed resume in Supabase)
    *   User ID
    *   Job Description text
*   **Initial Step:**
    *   A new job tracking record is created in the Supabase `optimization_jobs` table. This record will store the status and intermediate results of the optimization process.

*   **Keyword Extraction:**
    *   **Input:** Job Description text.
    *   **Process:** An OpenAI API call is made, utilizing the prompt defined in `Pipeline/prompts/extract_keywords.txt`. This prompt instructs the AI to identify relevant keywords, their context within the job description, their perceived relevance, and the type of skill they represent (e.g., technical, soft).
    *   **Output:** A structured JSON object containing the extracted keywords and their associated metadata.

*   **Semantic Matching (Orchestrated by `Pipeline/embeddings.py`):**
    *   **Inputs:**
        *   Keyword JSON (from the previous step).
        *   Original parsed resume JSON (fetched from Supabase using `resume_id`).
    *   **Process:**
        1.  **Generate Embeddings:** Vector embeddings are generated for both the keywords from the job description and the bullet points within the experience sections of the resume. These embeddings capture the semantic meaning of the text.
        2.  **Deduplicate JD Keywords:** Keywords extracted from the job description are deduplicated to avoid redundant processing.
        3.  **Calculate Similarity:** The similarity between the embeddings of JD keywords and resume bullet points is calculated (e.g., using cosine similarity). This results in a mapping, `matches_by_bullet`, which indicates which keywords are semantically related to each bullet point in the resume.
        4.  **Skill Processing:**
            *   Technical skills are extracted from the resume.
            *   Hard skills from the job description are categorized using an OpenAI call.
            *   A final list of technical skills, `final_technical_skills`, is selected to be included in the new skills section of the enhanced resume.
    *   **Outputs:**
        *   `matches_by_bullet`: A data structure that suggests relevant keywords for each resume bullet point.
        *   `final_technical_skills`: A structured representation of the skills to be included in the enhanced resume's skills section.

*   **Resume Enhancement (Orchestrated by `Pipeline/enhancer.py`):**
    *   **Inputs:**
        *   Original parsed resume JSON.
        *   `matches_by_bullet` (from the semantic matching step).
        *   `final_technical_skills` (from the semantic matching step).
    *   **Process:**
        1.  **Bullet Point Rewriting:** Each bullet point in the resume's experience sections is processed. Using the `matches_by_bullet` data, an OpenAI API call (via the `_enhance_bullet_with_keywords` function) is made to rewrite the bullet point, aiming to naturally incorporate the semantically matched keywords.
        2.  **Skills Section Replacement:** The original skills section of the resume is replaced with the new `final_technical_skills` structure.
    *   **Output:** `enhanced_resume_parsed` (a JSON object representing the complete, enhanced resume).

*   **Final Step:**
    1.  The `enhanced_resume_parsed` JSON is stored as a new entry in the Supabase `resumes` table. This new entry receives a new `enhanced_resume_id` and is linked to the original `resume_id`.
    2.  The corresponding record in the `optimization_jobs` table is updated to reflect the completion of the optimization and potentially store a reference to the `enhanced_resume_id`.

## 4. Data Retrieval/Download

This section explains how users can access their original or enhanced resumes.

*   **Endpoint:** `/api/download/<resume_id>/<format_type>`
    *   `format_type` can be `json`, `pdf`, or `latex`.
*   **Process:**
    1.  **Fetch Resume Data:** The system attempts to fetch the resume data (JSON) from Supabase. The logic, primarily located in `Pipeline/resume_loading.py`, prioritizes finding an enhanced version of the resume linked to the provided `resume_id`. If no enhanced version exists, it falls back to the original parsed resume.
    2.  **Format-Specific Generation:**
        *   **JSON:** If `json` is requested, the fetched resume JSON data is returned directly.
        *   **LaTeX:** If `latex` is requested, the resume JSON is used to generate LaTeX content. This is handled by `Pipeline/latex_generation.py`, which in turn uses templates from `Pipeline/latex_resume/templates/resume_generator.py`.
        *   **PDF:** If `pdf` is requested, LaTeX content is first generated (as described above). Then, the `pdflatex` command-line tool is used to compile this LaTeX content into a PDF file. `Pipeline/latex_generation.py` includes logic for adaptive page sizing during this compilation.
*   **Output:** The requested file in the specified format (raw JSON, a `.tex` file, or a `.pdf` file).

## 5. Proactive PDF Generation (Conceptual)

This describes a background process for generating PDFs without an explicit user download request.

*   **Function:** `Pipeline/latex_generation.py::proactively_generate_pdf`
*   **Process:**
    1.  This function takes enhanced resume data (JSON) as input.
    2.  It generates a PDF version of the resume using the same LaTeX generation and compilation steps described in the Data Retrieval section.
    3.  The generated PDF is saved locally to the `Pipeline/output/proactive_pdfs/` directory.
*   **Note:** Currently, there is no implemented step to automatically upload these proactively generated PDFs from the local filesystem to Supabase Storage or another persistent cloud storage.

## 6. Key Data Stores

This section summarizes the main locations where data is stored and managed.

*   **Supabase `resumes` Table:**
    *   Stores the structured JSON representation of both original parsed resumes and enhanced resumes.
    *   Links enhanced resumes back to their original versions.
*   **Supabase `optimization_jobs` Table:**
    *   Tracks the status, intermediate results (like extracted keywords), and progress of individual resume optimization tasks.
*   **Local Filesystem:**
    *   **`Pipeline/uploads/`:** Temporarily stores resume files uploaded by users before processing.
    *   **`Pipeline/output/proactive_pdfs/`:** Stores PDF files generated by the proactive PDF generation process.
    *   Used for temporary file storage during LaTeX to PDF compilation.
*   **OpenAI:**
    *   Not a persistent data store in the traditional sense, but it's a key external service used for:
        *   Parsing raw resume text into structured JSON.
        *   Extracting keywords and related metadata from job descriptions.
        *   Categorizing skills.
        *   Enhancing and rewriting resume bullet points.
