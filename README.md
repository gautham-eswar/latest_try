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

## API Endpoints

- `POST /api/upload`: Upload a resume file (PDF, DOCX, TXT). Returns parsed JSON and `resume_id`.
- `POST /api/optimize`: Takes `resume_id` and `job_description` text. Triggers the full analysis and enhancement pipeline. Returns enhanced resume JSON and analysis results.
- `GET /api/download/:resume_id/:format`: Download the enhanced resume in the specified format (`json`, `pdf`, `latex`). `:resume_id` is obtained from the `/api/upload` response.
- `GET /api/health`: Health check endpoint (JSON). Returns 200 even on partial failures for monitoring services.
- `GET /diagnostic/diagnostics`: HTML diagnostics dashboard.

## Frontend Development (Lovable)

A detailed prompt for fixing the frontend functionality using Lovable has been created in `Lovable.md`. This prompt outlines the required UI components, user workflow, API interactions, and display logic, adhering to the existing visual theme.

## Backend Architecture

The application consists of several key components:

### Core Pipeline Components
- **SemanticMatcher** (`Pipeline/embeddings.py`): Handles embedding generation, keyword deduplication, and semantic matching between keywords and resume bullet points. Includes advanced technical skills selection using a round-robin approach.
- **ResumeEnhancer** (`Pipeline/enhancer.py`): Takes matched keywords and enhances resume bullet points using OpenAI while preserving original meaning through semantic validation.
- **Keyword Extraction** (`Pipeline/keyword_extraction.py`): Extracts relevant keywords from job descriptions with context and relevance scoring.

### Data Storage
- **Supabase Integration**: Uses Supabase for persistent storage of resumes, enhanced versions, and analysis results.
- **Local Fallback**: Includes local file storage fallback for development and testing.

### PDF Generation
- **LaTeX-based PDF Generation**: Converts enhanced resumes to professional PDFs using LaTeX templates with adaptive page sizing.

## Deployment

The application is designed for deployment on Render. See `RENDER_DEPLOYMENT.md` for detailed deployment instructions and `RENDER_TROUBLESHOOTING.md` for common deployment issues.

## Environment Variables

This application requires the following environment variables:

- `OPENAI_API_KEY`: Your OpenAI API key (required)
- `PORT`: The port the application will run on (default: 8080)
- `FLASK_ENV`: The environment to run Flask in (development or production)
- `PDF_GENERATION_MODE`: PDF generation mode (default: fallback)
- `SUPABASE_URL`: Supabase project URL (if using Supabase)
- `SUPABASE_KEY`: Supabase API key (if using Supabase)

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

For Render deployment, set these variables in the Render dashboard.

## Testing

Run the diagnostic endpoint to check system status:
```
curl http://localhost:8080/diagnostic/diagnostics
```

## Diagnostics

Access the diagnostics dashboard at `/diagnostic/diagnostics` to monitor system performance and pipeline status.