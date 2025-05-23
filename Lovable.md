# Lovable Prompt: Resume Optimizer Frontend Functionality Fix

**Project Goal:** Create a functional and seamless user interface for the Resume Optimizer application. The backend API endpoints are mostly defined, but the current frontend implementation has incorrect functionality.

**Constraint:** Do NOT change the existing visual theme, colors, fonts, or overall aesthetic style. Focus solely on implementing the correct workflow, data flow, and API connections.

**Core Workflow:**

The application allows users to upload their resume, provide a job description, and receive an optimized version of their resume tailored to the job description, along with an analysis of keyword matching.

1.  **Home/Upload View:**
    *   **UI Elements:**
        *   A clear file upload component (accepts `.pdf`, `.docx`, `.txt`).
        *   A text area for pasting the job description.
        *   An "Optimize Resume" button.
        *   Display area for status messages/errors.
        *   Display area for results (appears after optimization).
    *   **Functionality:**
        *   **Resume Upload:** When a user selects a file, **immediately** upload it to the backend via a **POST** request to `/api/upload`.
            *   **API Call:** `POST /api/upload` (Method **MUST** be `POST`, using `multipart/form-data` content type with the file).
            *   **Backend Action:** Saves the file, extracts text, parses with OpenAI, saves parsed JSON to Supabase `resumes` table.
            *   **API Response:** JSON containing `{ status: "success", resume_id: "...", data: {parsed_resume_json} }`.
            *   **Frontend Action:** Store the returned `resume_id`. Show a success message (e.g., "Resume uploaded and parsed."). Optionally display the parsed resume sections (contact, experience, etc.) to the user for confirmation. Handle potential upload/parsing errors returned by the API.
        *   **Job Description Input:** User pastes the full job description into the text area.
        *   **Optimization Trigger:** When the user clicks "Optimize Resume" (this button should only be active *after* a resume has been successfully uploaded and its `resume_id` received):
            *   **Frontend Action:** Show a loading indicator. Send the stored `resume_id` and the raw text from the job description text area to the backend.
            *   **API Call:** `POST /api/optimize`
            *   **Request Body:** JSON `{ "resume_id": "...", "job_description": { "description": "..." } }` (Note: backend might need adjustment to expect raw text directly or structured description). *Backend currently expects `job_description` as an object, let's stick to that for now.*
            *   **Backend Action (Intended Advanced Workflow):**
                1.  Load parsed resume using `resume_id` (from local file or Supabase).
                2.  Extract keywords from `job_description.description` (using advanced keyword extraction).
                3.  Use `SemanticMatcher` to generate embeddings, deduplicate keywords, and match keywords to resume bullets.
                4.  Use `ResumeEnhancer` to rewrite bullets incorporating matched keywords.
                5.  Save the enhanced resume data (locally or in Supabase `enhanced_resumes` table).
                6.  Save match/analysis data (locally or in Supabase `matches` table).
            *   **API Response:** JSON containing `{ status: "success", resume_id: "...", data: {enhanced_resume_json}, analysis: {match_details} }`. Handle potential errors.
            *   **Frontend Action:** Hide loading indicator. Process the response and display the results (see step 2).

2.  **Results View (Displayed on the same page after optimization):**
    *   **UI Elements:**
        *   Side-by-side comparison of original vs. enhanced resume sections (especially "Experience"). Clearly highlight the changes/added keywords in the enhanced version.
        *   A summary section displaying match analysis (e.g., % keyword match, list of matched keywords, list of missing keywords - based on the `analysis` object from the API response).
        *   Download buttons (e.g., "Download PDF", "Download DOCX" - potentially using LaTeX backend conversion).
    *   **Functionality:**
        *   **Display:** Render the `data` (enhanced resume) and `analysis` results clearly. Use visual cues (like background highlighting) for changed text in the side-by-side view. **Conditionally render sections:** If parts of the `data` (e.g., specific resume sections) or `analysis` (e.g., no matches found) are empty or missing, do not show empty placeholder containers for those sections. Display a simple message like "No matching keywords found" or "No enhancements made to this section" if appropriate.
        *   **Download:** When a download button is clicked (e.g., "Download PDF"):
            *   **API Call:** `GET /api/download/{resume_id}/pdf` (replace `{resume_id}` with the stored ID, and `pdf` with the requested format - `json`, `pdf`, `latex`).
            *   **Backend Action:** Retrieves the enhanced resume data, converts it to the requested format (potentially involves LaTeX for PDF).
            *   **API Response:** The file content with appropriate `Content-Type` and `Content-Disposition` headers.
            *   **Frontend Action:** Trigger the browser's file download mechanism with the received file.

**Data Persistence (Backend - Context for Frontend):**

*   The backend ideally uses Supabase to store user data, resumes, job descriptions, keywords, and results. Key tables might include: `users`, `resumes` (original parsed), `job_descriptions`, `keywords`, `enhanced_resumes`, `matches`.
*   The frontend primarily interacts with the backend via `resume_id`. It does **not** need to interact directly with Supabase. It just needs to hold onto the `