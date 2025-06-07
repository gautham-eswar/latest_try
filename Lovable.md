# Lovable Prompt:  Seamless Resume Optimizer Frontend & Backend Specification

**Project Goal:** Define the precise frontend and backend interactions for a highly responsive and intuitive Resume Optimizer application. The core principle is a single user action ("Make it Better") that triggers the entire enhancement pipeline, from upload to comparison, providing clear user feedback throughout the process.

**Constraint:** The existing visual theme (colors, fonts, etc.) must be maintained. This document focuses exclusively on functionality, data flow, and API contracts to fix the application's workflow.

---

## Part 1: The Core "Make it Better" Workflow

This is the central user journey. It begins with the user on the main page and ends with them seeing a side-by-side comparison of their original and enhanced resume.

### Step 1: The User Interface (Home View)

The user interacts with a simple interface containing:
- A **file input** for their resume (`.pdf`, `.docx`, `.txt`).
- A **textarea** for the job description.
- A single **"Make it Better"** button, which is the primary call to action.

### Step 2: The "Make it Better" On-Click Event

When the user clicks the "Make it Better" button, the frontend executes the following logic:

1.  **Validation:**
    *   Check that a file has been selected in the file input.
    *   Check that the job description textarea is not empty.
    *   If either check fails, show a gentle, non-intrusive error message (e.g., a temporary red border on the empty field) and do not proceed.

2.  **Initiate Loading State:**
    *   Immediately display a **full-page, non-interactive loading overlay**. This assures the user that the system is working.

3.  **Prepare the Data:**
    *   Create a `FormData` object. This is essential for sending a file and text data together.
    *   Append the user's resume file: `formData.append('resume_file', selectedFile);`
    *   Append the job description text: `formData.append('job_description', jobDescriptionText);`
    *   Append the user ID (if available): `formData.append('user_id', userId);`

4.  **Execute the API Call:**
    *   Make a single `POST` request to the unified backend endpoint within a `try...catch` block to handle all outcomes.

### Step 3: The Unified API Endpoint (`/api/process`)

This is the new, all-in-one endpoint that the backend must expose. It replaces the separate upload and optimize calls.

- **Endpoint:** `POST /api/process`
- **Request Type:** `multipart/form-data` (handled automatically by the browser when sending `FormData`).

#### Backend Logic for `/api/process`:

The backend must execute these steps sequentially upon receiving a request:

1.  **Receive and Validate:** Get the `resume_file`, `job_description`, and `user_id` from the multipart request. If any are missing, return a `400 Bad Request` error immediately.

2.  **Upload & Parse Resume (Internal Step A):**
    *   Perform the entire resume upload and parsing logic that was previously in the `/api/upload` endpoint.
    *   This includes saving the raw file, extracting its text, parsing the text into a structured JSON format, and saving that structured data to the database (e.g., in a `resumes` table). This step yields the `original_resume_id` and the `parsed_resume_json`.

3.  **Enhance Resume (Internal Step B):**
    *   Take the `parsed_resume_json` from the previous step and the `job_description` text from the request.
    *   Perform the entire optimization logic that was previously in the `/api/optimize` endpoint.
    *   This includes keyword extraction, semantic matching, content enhancement, and saving the final enhanced resume to the database (e.g., in an `enhanced_resumes` table), yielding the `enhanced_resume_id` and `analysis` data.

4.  **Return the Final Response:**
    *   **On Success:** If all internal steps complete, return a `200 OK` status with the consolidated results.
    *   **On Failure:** If any internal step fails (e.g., file parsing error, enhancement error), the entire operation fails. Return a single, clear error response (`4xx` or `5xx`) with a descriptive message.

#### API Response Contracts:

-   **Success Response (`200 OK`):**
    ```json
    {
      "status": "success",
      "message": "Resume processed and optimized successfully.",
      "data": {
        "job_id": "...",
        "original_resume_id": "...",
        "enhanced_resume_id": "...",
        "analysis": {
          "matches_by_bullet": { ... },
          "skill_selection_log": { ... },
          "modifications_summary": [ ... ]
        }
      }
    }
    ```

-   **Error Response (e.g., `400`, `500`):**
    ```json
    {
      "error": "ProcessingError",
      "message": "Failed to parse the uploaded resume file. Please ensure it is not corrupted and is a supported format.",
      "status_code": 400
    }
    ```

### Step 4: Frontend Response Handling

1.  **On Success (`try` block):**
    *   Check for a `200 OK` status and `response.data.status === 'success'`.
    *   Extract the necessary IDs (`job_id`, `enhanced_resume_id`, etc.) from the response.
    *   **Redirect to the comparison page.** A good URL would be `/compare/{job_id}`.
    *   The loading overlay will vanish automatically as the new page loads.

2.  **On Failure (`catch` block):**
    *   **Hide the loading overlay.**
    *   Display a **red error toaster** at the bottom of the screen.
    *   The content of the toaster should be the `message` from the JSON error response. This provides direct, actionable feedback to the user.

---

## Part 2: The Download Workflow

Once the user is on the comparison page, they need to be able to download the results.

- **Endpoint:** `GET /api/download/{resume_id}/{format}`
- **Example:** `GET /api/download/enh_12345/pdf`

### Frontend Action:

- The comparison page will have download buttons (e.g., "Download PDF").
- Clicking a button makes a simple `GET` request to the download endpoint with the `enhanced_resume_id` (which was received from the `/api/process` call) and the desired format (`pdf`, `docx`, etc.).

### Backend Action:

- Retrieves the specified enhanced resume data.
- Converts it to the requested format (e.g., using the LaTeX generator for PDFs).
- Returns the generated file with the correct `Content-Type` headers to trigger a browser download.