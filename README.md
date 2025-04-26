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

- `POST /api/upload`: Upload a resume file
- `POST /api/optimize`: Optimize a resume with a job description
- `GET /api/resume/:id`: Get a resume by ID
- `GET /api/resume/:id/download`: Download an enhanced resume

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