# Resume Optimizer

A web application that optimizes resumes based on job descriptions using AI.

## Features

- Resume parsing (PDF, DOCX, TXT)
- Keyword extraction from job descriptions
- Semantic matching between resume skills and job requirements
- Resume enhancement suggestions
- Enhanced resume generation in multiple formats

## Setup

### Local Development

1. Clone the repository
2. Create a virtual environment:
   ```
   python -m venv simple-venv
   source simple-venv/bin/activate  # On Windows: simple-venv\Scripts\activate
   ```
3. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
4. Set up environment variables:
   ```
   export OPENAI_API_KEY=your_openai_api_key
   export FLASK_ENV=development
   ```
5. Run the application:
   ```
   python working_app.py
   ```

### Docker

1. Build and run using Docker:
   ```
   docker build -t resume-optimizer .
   docker run -p 8080:8080 -e OPENAI_API_KEY=your_openai_api_key resume-optimizer
   ```

2. Or use Docker Compose:
   ```
   export OPENAI_API_KEY=your_openai_api_key
   docker-compose up
   ```

## API Endpoints

- `POST /api/upload`: Upload a resume file (PDF, DOCX, TXT). Returns parsed JSON and `resume_id`.
- `POST /api/optimize`: Takes `resume_id` and `job_description` text. Triggers the full analysis and enhancement pipeline. Returns enhanced resume JSON and analysis results.
- `GET /api/download/:resume_id/:format`: Download the enhanced resume in the specified format (`json`, `pdf`, `latex`). `:resume_id` is obtained from the `/api/upload` response.
- `GET /api/health`: Health check endpoint (JSON). Returns 200 even on partial failures for monitoring services.
- `GET /diagnostic/diagnostics`: HTML diagnostics dashboard.

**Note:** The API endpoints described here reflect the *intended* functionality for the frontend. See the 'Backend Considerations' section below.

## Frontend Development (Lovable)

A detailed prompt for fixing the frontend functionality using Lovable has been created in `Lovable.md`. This prompt outlines the required UI components, user workflow, API interactions, and display logic, adhering to the existing visual theme.

## Backend Considerations & Recent Changes

*   **OpenAI API Issue:** The previous `TypeError: Client.__init__() got an unexpected keyword argument 'proxies'` has been **resolved**. This was likely due to implicit proxy handling in the Render environment conflicting with the OpenAI library. The fix involved explicitly disabling environment proxy detection via `httpx.Client(trust_env=False)`.
*   **Dependencies:** OpenAI library version aligned to `1.6.1` across `requirements.txt` and `requirements-render.txt`.
*   **Backend Refactoring Needed:**
    *   The current `/api/optimize` endpoint in `working_app.py` uses a simpler OpenAI-based flow for parsing and keyword extraction. It does **not** yet utilize the more advanced `SemanticMatcher` (`embeddings.py`) and `ResumeEnhancer` (`enhancer.py`) classes.
    *   The backend needs to be refactored to integrate this advanced workflow into the `/api/optimize` endpoint to fully support the functionality described in the `Lovable.md` prompt.
    *   **Persistence:** The current implementation relies heavily on local file storage (`./uploads`, `./output`). For scalability and proper state management, this should be refactored to use a database like Supabase. Intended tables might include `resumes` (parsed), `job_descriptions`, `keywords`, `matches`, `enhanced_resumes`.
*   **Diagnostics:** The diagnostics system (`diagnostic_system.py`) has been enhanced with more detailed logging, especially around OpenAI client initialization and dependency checking.

## Testing

Run the test suite:
```
python test_resume_processing.py
```

Performance testing with large inputs:
```
python large_input_test.py
```

## Diagnostics

Access the diagnostics dashboard at `/diagnostics` to monitor system performance and pipeline status.

# Environment Variables

This application requires the following environment variables:

- `OPENAI_API_KEY`: Your OpenAI API key (required)
- `PORT`: The port the application will run on (default: 8080)
- `FLASK_ENV`: The environment to run Flask in (development or production)
- `PDF_GENERATION_MODE`: PDF generation mode (default: fallback)

You can set these variables in a `.env` file in the root directory or in your deployment platform's environment settings. For local development:

```bash
# Create a .env file
cat << EOF > .env
OPENAI_API_KEY=your_api_key_here
PORT=8080
FLASK_ENV=development
PDF_GENERATION_MODE=fallback
EOF
```

For Render deployment, set these variables in the Render dashboard or in your `render.yaml` file.