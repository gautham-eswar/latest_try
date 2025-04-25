# Resume-O: Resume Optimization System

An AI-powered resume optimization system that helps users tailor their resumes to specific job descriptions for improved matching and higher chances of interview selection.

## Table of Contents

- [System Overview](#system-overview)
- [Architecture](#architecture)
- [Key Components](#key-components)
- [API Documentation](#api-documentation)
- [Data Flow](#data-flow)
- [Development Setup](#development-setup)
- [Testing](#testing)
- [Deployment](#deployment)
- [Contributing](#contributing)

## System Overview

Resume-O is a comprehensive resume processing pipeline that leverages AI to optimize resumes for specific job opportunities. The system:

1. Parses resumes from various formats (PDF, DOCX, TXT)
2. Extracts structured data including skills, experience, and education
3. Analyzes job descriptions to identify key requirements and qualifications
4. Performs semantic matching between resume content and job requirements
5. Enhances resumes by highlighting relevant experience and skills
6. Generates optimized resumes in multiple formats (JSON, LaTeX, PDF)

The entire system is built as a modular Flask application with RESTful APIs, diagnostic capabilities, and extensive validation mechanisms.

## Architecture

The system follows a layered architecture:

1. **Web Layer**: Flask application providing REST API endpoints
2. **Service Layer**: Core business logic and pipeline orchestration
3. **Data Layer**: Database access and in-memory fallback storage
4. **Integration Layer**: OpenAI API integration for NLP processing

### System Design Diagram

```
┌───────────────┐     ┌───────────────┐     ┌───────────────┐
│ Client        │     │ Flask App     │     │ Database      │
│ (Web Browser/ │────▶│ (API          │────▶│ (Supabase/    │
│  API Client)  │     │  Endpoints)   │     │  In-Memory)   │
└───────────────┘     └───────┬───────┘     └───────────────┘
                              │
                              ▼
┌───────────────┐     ┌───────────────┐     ┌───────────────┐
│ PDF Generator │◀────│ Core Pipeline │────▶│ OpenAI API    │
│ (LaTeX/PDF    │     │ (Processing   │     │ (NLP/AI       │
│  Output)      │     │  Logic)       │     │  Processing)  │
└───────────────┘     └───────────────┘     └───────────────┘
```

## Key Components

### 1. Resume Parser (`resume_parser.py`)

The resume parser is responsible for extracting structured data from various resume formats. It:
- Processes PDF, DOCX, and TXT formats
- Extracts personal information, education, work experience, and skills
- Normalizes data into a consistent JSON structure
- Handles various resume layouts and formatting styles

### 2. Semantic Matcher (`semantic_matcher.py`)

The semantic matcher analyzes the relationship between resume content and job requirements:
- Extracts key requirements from job descriptions
- Calculates relevance scores for each section of the resume
- Identifies gaps in skills or experience
- Suggests optimization strategies

### 3. API Adapter (`api_adapter.py`)

This component orchestrates the entire resume optimization pipeline:
- Manages the sequence of processing steps
- Handles error recovery and fallback strategies
- Provides transaction tracking for diagnostics
- Implements retry logic for external API calls

### 4. PDF Generator (`pdf_generator.py`)

Responsible for creating output documents in various formats:
- Generates LaTeX files for professional formatting
- Converts optimized resume data to PDF format
- Implements fallback mechanisms when LaTeX is unavailable
- Supports customizable templates

### 5. Validation Strategy (`validation_strategy.py`)

Implements a comprehensive validation framework:
- Validates input files for format and content
- Ensures resume and job description data meets quality standards
- Provides detailed validation reports with errors and warnings
- Supports validation chains for complex validation sequences

### 6. Diagnostic System (`diagnostic_system.py`)

Monitors system health and performance:
- Tracks API request/response metrics
- Monitors component status and performance
- Provides a diagnostic dashboard for system monitoring
- Logs detailed information for troubleshooting

### 7. Database Interface (`database.py` and `in_memory_db.py`)

Manages data persistence:
- Stores resume data, job descriptions, and optimization results
- Implements an in-memory fallback for development or when Supabase is unavailable
- Tracks transaction history and processing status
- Provides simple CRUD operations for application data

## API Documentation

### Resume Upload

```
POST /api/upload
Content-Type: multipart/form-data

file=@resume.pdf
```

Response:
```json
{
  "resume_id": "resume_1745215385_ba8f615c",
  "original_filename": "resume.pdf",
  "status": "success",
  "message": "Resume uploaded and parsed successfully"
}
```

### Resume Optimization

```
POST /api/optimize
Content-Type: application/json

{
  "resume_id": "resume_1745215385_ba8f615c",
  "job_description": "Looking for a software engineer with 5+ years of experience in Python and web development..."
}
```

Response:
```json
{
  "resume_id": "resume_1745215385_ba8f615c",
  "status": "success",
  "message": "Resume optimized successfully",
  "match_score": 0.85,
  "optimization_summary": {
    "highlighted_skills": ["Python", "Web Development"],
    "suggested_improvements": ["Add more detail about database experience"]
  }
}
```

### Resume Download

```
GET /api/download/{resume_id}/{format}
```

Supported formats: `json`, `latex`, `pdf`

Response: The optimized resume in the requested format.

### Health Check

```
GET /api/health
```

Response:
```json
{
  "status": "healthy",
  "uptime": "12h 5m 30s",
  "components": {
    "database": "connected",
    "openai_api": "available",
    "pdf_generator": "available"
  },
  "timestamp": "2025-04-23T05:20:09.166Z"
}
```

### Diagnostics Dashboard

```
GET /diagnostic/diagnostics
```

Response: HTML page with system diagnostics and performance metrics.

## Data Flow

1. **Upload Flow**:
   - Client uploads resume file
   - System validates file format and content
   - Resume parser extracts structured data
   - Structured data is stored in database
   - Resume ID is returned to client

2. **Optimization Flow**:
   - Client sends resume ID and job description
   - System retrieves resume data from database
   - Semantic matcher analyzes job requirements
   - Optimization algorithms enhance resume content
   - Enhanced resume is stored in database
   - Optimization summary is returned to client

3. **Download Flow**:
   - Client requests optimized resume in specific format
   - System retrieves enhanced resume data
   - PDF generator creates requested format
   - Formatted resume is returned to client

## Development Setup

### Prerequisites

- Python 3.8+
- Flask and dependencies
- LaTeX (optional, for PDF generation)
- OpenAI API key
- Supabase account (optional, for database)

### Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/gautham-eswar/latest_try.git
   cd resume-o
   ```

2. Create a virtual environment:
   ```bash
   python -m venv simple-venv
   source simple-venv/bin/activate  # On Windows: simple-venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Set up environment variables:
   ```bash
   export OPENAI_API_KEY="your_openai_api_key"
   export SUPABASE_URL="your_supabase_url"  # Optional
   export SUPABASE_KEY="your_supabase_key"  # Optional
   ```

5. Run the application:
   ```bash
   python working_app.py --port 8085 --debug
   ```

6. Access the application:
   - API: http://localhost:8085/api/health
   - Diagnostics: http://localhost:8085/diagnostic/diagnostics

## Testing

### Test Scripts

- `test_resume_processing.py`: Validates core resume processing functionality
- `test_pipeline.py`: Tests the full optimization pipeline
- `large_input_test.py`: Performance testing with larger inputs

### Running Tests

```bash
# Run basic tests
python test_resume_processing.py

# Test full pipeline with sample resume
python test_pipeline.py --resume test_files/sample_resume.pdf --job test_files/sample_job.txt

# Performance testing
python large_input_test.py --iterations 10
```

### Validation Framework

The system includes a comprehensive validation framework in `validation_strategy.py` that can be used to validate system components:

```python
from validation_strategy import ValidationFactory

# Create and run resume validation
resume_chain = ValidationFactory.create_resume_validation_chain()
is_valid = resume_chain.validate(resume_data)
report = resume_chain.get_report()
```

## Deployment

For detailed deployment instructions, see [DEPLOYMENT.md](DEPLOYMENT.md).

### Quick Deployment Steps:

1. Set up a Render web service
2. Connect to GitHub repository
3. Configure environment variables
4. Set build command: `pip install -r requirements.txt`
5. Set start command: `python app.py --port $PORT`

## File Structure

```
resume-o/
├── app.py                 # Main application entry point
├── working_app.py         # Simplified app for testing
├── api_adapter.py         # API integration logic
├── resume_parser.py       # Resume parsing functionality
├── semantic_matcher.py    # Semantic matching algorithms
├── pdf_generator.py       # PDF generation utilities
├── validation_strategy.py # Data validation strategies
├── diagnostic_system.py   # Monitoring and diagnostics
├── database.py            # Database interface
├── in_memory_db.py        # Fallback database
├── production_checklist.py # Production readiness checks
├── templates/             # HTML templates for UI
│   └── diagnostics.html   # Diagnostics dashboard
├── test_files/            # Sample files for testing
│   ├── resumes/           # Sample resumes
│   └── job_descriptions/  # Sample job descriptions
├── tests/                 # Test scripts
│   ├── test_resume_processing.py
│   ├── test_pipeline.py
│   └── large_input_test.py
├── requirements.txt       # Python dependencies
└── DEPLOYMENT.md          # Deployment guide
```

## Contributing

For collaborative development, we recommend the following workflow:

1. Create a feature branch from main:
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. Make your changes and test locally

3. Verify changes with validation script:
   ```bash
   python production_checklist.py --verify
   ```

4. Commit and push your changes:
   ```bash
   git add .
   git commit -m "Add feature description"
   git push origin feature/your-feature-name
   ```

5. Create a pull request on GitHub

### Collaborative Workflow

Multiple developers can work on the same repository by:
1. Using separate feature branches
2. Regular communication about changes
3. Code reviews through pull requests
4. Resolving merge conflicts promptly

For larger teams, consider:
1. Using a fork-and-pull-request model
2. Setting up CI/CD pipelines for automated testing
3. Regular code freeze periods for integration
4. Detailed documentation of API changes 