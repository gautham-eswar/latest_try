# Resume Optimizer

A web application that optimizes resumes based on job descriptions using AI.

## Features

- Resume parsing (PDF, DOCX, TXT)
- Keyword extraction from job descriptions
- Semantic matching between resume skills and job requirements
- AI-powered resume enhancement using OpenAI
- Enhanced resume generation in multiple formats (JSON, PDF, LaTeX)
- Comprehensive diagnostics and monitoring system
- Proactive PDF generation and Supabase storage integration

## Quick Start

### Prerequisites

- Python 3.9+
- OpenAI API key
- LaTeX distribution (for PDF generation)
  - macOS: Install [MacTeX](https://tug.org/mactex/)
  - Linux: `sudo apt-get install texlive-full`
  - Windows: Install [MiKTeX](https://miktex.org/)

### Local Development Setup

1. **Clone and Setup Environment:**
   ```bash
   git clone <repository-url>
   cd latest_try
   python -m venv simple-venv
   source simple-venv/bin/activate  # On Windows: simple-venv\Scripts\activate
   ```

2. **Install Dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure Environment Variables:**
   ```bash
   # Create .env file
   cat << EOF > .env
   OPENAI_API_KEY=your_openai_api_key_here
   PORT=8080
   FLASK_ENV=development
   PDF_GENERATION_MODE=fallback
   # Optional: Supabase configuration
   SUPABASE_URL=your_supabase_url
   SUPABASE_KEY=your_supabase_key
   EOF
   ```

4. **Run the Application:**
   ```bash
   python working_app.py
   ```

5. **Verify Installation:**
   ```bash
   # Test health endpoint
   curl http://localhost:8080/api/health
   
   # View diagnostics dashboard
   open http://localhost:8080/diagnostic/diagnostics
   ```

### Docker Deployment

```bash
# Build and run with Docker
docker build -t resume-optimizer .
docker run -p 8080:8080 \
  -e OPENAI_API_KEY=your_openai_api_key \
  -e SUPABASE_URL=your_supabase_url \
  -e SUPABASE_KEY=your_supabase_key \
  resume-optimizer
```

## API Endpoints

### Core Functionality
- `GET /`: Root endpoint with API documentation and service information
- `POST /api/upload`: Upload a resume file (PDF, DOCX, TXT). Requires `user_id` and `file` form data. Returns parsed JSON and `resume_id`.
- `POST /api/optimize`: Takes `resume_id` and `job_description` text. Triggers the full analysis and enhancement pipeline. Returns enhanced resume JSON and analysis results.
- `GET /api/download/:resume_id/:format`: Download the enhanced resume in the specified format (`json`, `pdf`, `latex`). `:resume_id` is obtained from the `/api/upload` response.

### Monitoring & Health
- `GET /api/health`: Health check endpoint (JSON). Returns 200 even on partial failures for monitoring services.
- `GET /status`: Application status and system information
- `GET /diagnostic/diagnostics`: HTML diagnostics dashboard with system metrics and pipeline testing

### Logging & Debugging  
- `GET /api/logs`: View application logs (JSON format)
- `GET /api/logs/live`: Live streaming application logs

### Testing (Development)
- `GET /api/test/simulate-failure`: Testing endpoint for failure simulation
- `GET /api/test/custom-error/:error_code`: Testing endpoint for custom error responses

## Testing & Verification

### Manual Testing with Sample Files

The application includes comprehensive testing tools in the `test_files/` directory:

```bash
# Test the complete pipeline
python test_files/test_pipeline.py \
  --resume test_files/sample_resume.txt \
  --job test_files/job_description.txt

# Test with large inputs
python test_files/test_large_inputs.py \
  --server http://localhost:8080 \
  --resume test_files/sample_resume.txt \
  --job test_files/large_tests/large_jd.txt

# Test deployment endpoints
python test_deployment.py --url http://localhost:8080 --verbose
```

### Pipeline Component Testing

```bash
# Test PDF generation directly
python test_pdf_only.py

# Test LaTeX template functionality  
python test_classic_template.py

# Test full pipeline components
python test_full_pipeline.py
```

### System Health Verification

```bash
# Check all system components
curl http://localhost:8080/diagnostic/diagnostics

# Test pipeline functionality
curl http://localhost:8080/diagnostic/test-pipeline

# Monitor logs in real-time
curl http://localhost:8080/api/logs/live
```

### Example Usage Flow

1. **Upload a Resume:**
   ```bash
   curl -X POST -F "user_id=test-user" \
     -F "file=@test_files/sample_resume.txt" \
     http://localhost:8080/api/upload
   ```

2. **Optimize the Resume:**
   ```bash
   curl -X POST -H "Content-Type: application/json" \
     -d '{"resume_id":"<resume_id_from_upload>","job_description":"Software Engineer with Python experience"}' \
     http://localhost:8080/api/optimize
   ```

3. **Download Enhanced Resume:**
   ```bash
   # Download as PDF
   curl http://localhost:8080/api/download/<resume_id>/pdf -o enhanced_resume.pdf
   
   # Download as JSON
   curl http://localhost:8080/api/download/<resume_id>/json -o enhanced_resume.json
   ```

## Architecture & Components

### Backend Pipeline
- **Resume Parser** (`Pipeline/resume_uploader.py`): Extracts text from PDF/DOCX/TXT files and converts to structured JSON using OpenAI
- **Keyword Extractor** (`Pipeline/keyword_extraction.py`): Extracts relevant keywords from job descriptions with context and relevance scoring
- **Semantic Matcher** (`Pipeline/embeddings.py`): Handles embedding generation, keyword deduplication, and semantic matching between keywords and resume bullet points
- **Resume Enhancer** (`Pipeline/enhancer.py`): Enhances resume bullet points using OpenAI while preserving original meaning through semantic validation
- **PDF Generator** (`Pipeline/latex_generation.py`): Converts enhanced resumes to professional PDFs using LaTeX templates with adaptive page sizing

### Data Storage & Integration
- **Supabase Integration**: Persistent storage of resumes, enhanced versions, and analysis results
- **Local Fallback**: File storage fallback for development and testing
- **Storage Service** (`Services/storage.py`): Handles PDF uploads to Supabase Storage with proactive generation

### Monitoring & Diagnostics
- **Diagnostic System** (`Services/diagnostic_system.py`): Comprehensive health monitoring, pipeline testing, and performance metrics
- **Centralized Logging** (`Services/logging_config.py`): Application-wide logging with configurable levels and log buffer management
- **Error Handling** (`Services/errors.py`): Standardized error responses and exception handling

## Environment Variables

### Required
- `OPENAI_API_KEY`: Your OpenAI API key (required for all AI operations)

### Optional
- `PORT`: Application port (default: 8080)
- `FLASK_ENV`: Environment mode (`development`/`production`)
- `PDF_GENERATION_MODE`: PDF generation mode (`fallback`/`single`/`multi`)
- `SUPABASE_URL`: Supabase project URL (for persistent storage)
- `SUPABASE_KEY`: Supabase API key (for persistent storage)
- `MAX_CONTENT_LENGTH`: Maximum upload file size (default: 16MB)

### Development Settings
- `FLASK_DEBUG`: Enable Flask debug mode (`true`/`false`)
- `RENDER`: Set to `true` when deploying on Render platform

## Deployment

### Render Platform
The application is optimized for Render deployment. See `RENDER_DEPLOYMENT.md` for detailed instructions and `RENDER_TROUBLESHOOTING.md` for common issues.

### Docker Production
```bash
# Production deployment with environment variables
docker run -d -p 8080:8080 \
  -e OPENAI_API_KEY=your_key \
  -e SUPABASE_URL=your_url \
  -e SUPABASE_KEY=your_key \
  -e FLASK_ENV=production \
  --name resume-optimizer \
  resume-optimizer
```

## Troubleshooting

### Common Issues

**LaTeX/PDF Generation Problems:**
```bash
# Test LaTeX installation
python minimal_latex_test.py

# Test PDF generation directly
python test_pdf_generation.py
```

**API Connection Issues:**
```bash
# Test basic connectivity
python simple_test.py

# Test full deployment
python test_deployment.py --url <your_deployment_url>
```

**Debugging Pipeline Issues:**
- Check `/diagnostic/diagnostics` for component status
- Review logs at `/api/logs` endpoint
- Test individual components using the test scripts in `test_files/`

### Performance Monitoring
- Access diagnostics dashboard at `/diagnostic/diagnostics`
- Monitor pipeline performance and success rates
- View system resource usage and component health
- Test pipeline functionality with built-in testing tools

## Development & Contributing

### Project Structure
```
├── Pipeline/              # Core processing pipeline
├── Services/             # Shared services and utilities  
├── Endpoints/            # API endpoint handlers
├── test_files/           # Testing utilities and sample files
├── requirements.txt      # Python dependencies
├── Dockerfile           # Container configuration
└── working_app.py       # Main application entry point
```

### Adding Tests
Place new test files in `test_files/` directory. Follow the existing pattern:
- Use descriptive names (`test_<component>_<scenario>.py`)
- Include both positive and negative test cases
- Test with realistic data sizes and edge cases
- Document expected behavior and known limitations