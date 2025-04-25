# Deployment Guide for Resume-O

This guide provides comprehensive instructions for deploying the Resume-O application to Render, including setup, configuration, troubleshooting, monitoring, maintenance, and security best practices.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Deployment Steps](#deployment-steps)
3. [Troubleshooting](#troubleshooting)
4. [Monitoring](#monitoring)
5. [Maintenance](#maintenance)
6. [Security](#security)
7. [Reference](#reference)
8. [Developer Onboarding](#developer-onboarding)

## Prerequisites

### Required Accounts

- **Render Account**: Sign up at [render.com](https://render.com)
- **Supabase Account**: Create an account at [supabase.com](https://supabase.com)
- **OpenAI Account**: Register at [platform.openai.com](https://platform.openai.com) and generate an API key

### Necessary Tools and Software

- **Git**: For version control
- **Python 3.8+**: The application is built on Python
- **LaTeX** (optional): Required for PDF generation functionality
- **Docker** (optional): For local containerized testing

### Required Permissions and Access

- Admin access to your Render account
- Owner or developer role on the GitHub/GitLab repository
- Access to Supabase project with database creation permissions
- OpenAI API key with sufficient usage quota

### Knowledge Prerequisites

- Basic understanding of web applications and APIs
- Familiarity with Python and Flask applications
- Basic knowledge of environment variables
- Understanding of database concepts
- Comfort with command-line interfaces

## Deployment Steps

### 1. Initial Setup in Render Dashboard

1. Log in to your Render dashboard
2. Click "New" and select "Web Service"
3. Connect to your GitHub/GitLab repository containing the Resume-O application
4. Configure the service with the following settings:
   - **Name**: resume-optimization-service (or your preferred name)
   - **Environment**: Python
   - **Region**: Choose the region closest to your user base
   - **Branch**: main (or your production branch)
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `python app.py --port $PORT`
   - **Instance Type**: Recommend starting with Standard (512 MB)

### 2. Environment Variable Configuration

Configure the following environment variables in the Render dashboard:

| Variable | Description | Example |
|----------|-------------|---------|
| `PORT` | Port the application will listen on | Automatically set by Render |
| `OPENAI_API_KEY` | Your OpenAI API key | sk-... |
| `SUPABASE_URL` | URL of your Supabase project | https://[project-id].supabase.co |
| `SUPABASE_KEY` | Supabase service role API key | eyJ... |
| `DEBUG` | Enable/disable debug mode | false |
| `ENVIRONMENT` | Deployment environment | production |
| `PDF_GENERATION_MODE` | PDF generation method | cloud_latex |
| `LOG_LEVEL` | Logging verbosity | INFO |

### 3. Setting Up Supabase

1. Create a new project in Supabase
2. Set up the required tables:
   ```sql
   CREATE TABLE resumes (
     id TEXT PRIMARY KEY,
     original_filename TEXT NOT NULL,
     content_type TEXT NOT NULL,
     data JSONB NOT NULL,
     enhanced_data JSONB,
     created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
     updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
   );
   
   CREATE TABLE job_descriptions (
     id TEXT PRIMARY KEY,
     title TEXT NOT NULL,
     description TEXT NOT NULL,
     requirements JSONB,
     created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
   );
   
   CREATE TABLE transactions (
     id TEXT PRIMARY KEY,
     status TEXT NOT NULL,
     method TEXT NOT NULL,
     endpoint TEXT NOT NULL,
     duration REAL,
     error TEXT,
     started_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
     completed_at TIMESTAMP WITH TIME ZONE
   );
   ```

3. Copy the Supabase URL and API key from your project settings

### 4. Build and Deployment Process

1. After configuring all settings, click "Create Web Service"
2. Render will automatically:
   - Clone your repository
   - Install dependencies from requirements.txt
   - Build the application
   - Start the service on the specified port

3. Monitor the build logs for any errors
4. Once completed, Render will provide a URL for your deployed application

### 5. Post-Deployment Verification

1. Access the `/api/health` endpoint to verify the service is running:
   ```
   curl https://your-render-url.onrender.com/api/health
   ```

2. Check the diagnostic dashboard:
   ```
   https://your-render-url.onrender.com/diagnostic/diagnostics
   ```

3. Verify all components are functioning:
   - Database connection
   - OpenAI API connection
   - PDF generation capability

## Troubleshooting

### Common Deployment Issues

#### Application Fails to Start

**Symptoms:**
- "Failed to start" message in Render dashboard
- 503 errors when accessing endpoints

**Possible Causes:**
- Missing environment variables
- Dependency installation failures
- Start command errors

**Resolution Steps:**
1. Check build logs for Python errors
2. Verify all required environment variables are set
3. Ensure requirements.txt includes all dependencies
4. Confirm the start command is correct

#### Database Connection Issues

**Symptoms:**
- Application starts but returns 500 errors
- Log messages show database connection failures

**Possible Causes:**
- Incorrect Supabase credentials
- Database network restrictions
- Missing database tables

**Resolution Steps:**
1. Verify Supabase URL and API key in environment variables
2. Check if Supabase project is active
3. Ensure database tables are properly created
4. Confirm firewall settings allow connections

#### OpenAI API Errors

**Symptoms:**
- Resume processing fails
- Logs show OpenAI API authentication errors

**Common Error Messages:**
```
"Failed to import core algorithm modules: No module named 'semantic_matcher'"
"OpenAI API authentication failed: { "error": { "message": "Incorrect API key provided" } }"
```

**Resolution Steps:**
1. Verify your OpenAI API key is valid and properly formatted
2. Check your OpenAI account for usage limits or billing issues
3. Ensure network connectivity to the OpenAI API
4. Check if semantic_matcher and other required modules are installed

### Error Interpretation Guide

| Log Message | Meaning | Resolution |
|-------------|---------|------------|
| `name 'create_database_client' is not defined` | Missing database client | Check database module imports |
| `Failed to import PDF generator` | PDF generation setup issue | Verify LaTeX installation or fallback mode |
| `ModuleNotFoundError: No module named 'httpx'` | Missing dependency | Add dependency to requirements.txt |
| `OpenAI API authentication failed` | Invalid API key | Update OpenAI API key |
| `Port 5000 is in use by another program` | Port conflict | Use a different port or stop competing service |

### Support Information

- **Internal Support**: Contact DevOps team at devops@company.com
- **Render Support**: Submit a ticket at [render.com/support](https://render.com/support)
- **Supabase Support**: [supabase.com/support](https://supabase.com/support)
- **OpenAI API Support**: [help.openai.com](https://help.openai.com)

## Monitoring

### Accessing Monitoring Dashboards

1. **Render Dashboard**:
   - Log in to [dashboard.render.com](https://dashboard.render.com)
   - Navigate to your service
   - View metrics under the "Metrics" tab

2. **Application Diagnostic Dashboard**:
   - Access `/diagnostic/diagnostics` on your deployed application
   - Provides system status, component health, and transaction logs

3. **Supabase Dashboard**:
   - Log in to [app.supabase.com](https://app.supabase.com)
   - Navigate to your project
   - View database metrics and logs

### Interpreting Monitoring Data

#### Service Health Metrics

- **CPU Usage**: Should ideally stay below 70% sustained
- **Memory Usage**: Should remain below instance limits
- **Response Time**: Ideally under 500ms for API endpoints
- **Error Rate**: Should be below 1% of total requests

#### Transaction Metrics

The application tracks detailed transaction metrics available on the diagnostics page:

- **Success Rates**: Percentage of successful API calls
- **Duration**: Processing time for each endpoint
- **Error Types**: Categories of errors encountered
- **Component Status**: Health status of each system component

### Setting Up Alerts

1. **Render Alerts**:
   - In the Render dashboard, navigate to your service
   - Go to "Alerts" and click "Create Alert"
   - Configure alerts for:
     - Service downtime
     - High CPU/memory usage
     - Error rate thresholds

2. **Custom Application Alerts**:
   - Implement the monitoring.py module
   - Configure threshold values in environment variables:
     - `ALERT_CPU_THRESHOLD`: e.g., "80"
     - `ALERT_MEMORY_THRESHOLD`: e.g., "90"
     - `ALERT_ERROR_RATE`: e.g., "5"

### Responding to Incidents

1. **Triage Process**:
   - Check service status in Render dashboard
   - Review application logs for error messages
   - Examine diagnostic dashboard for component failures
   - Verify external dependencies (OpenAI, Supabase)

2. **Common Remediation Steps**:
   - Restart the service for temporary issues
   - Roll back to previous deployment if recent changes caused issues
   - Scale up resources if performance-related
   - Rotate API keys if authentication issues persist

## Maintenance

### Routine Maintenance Tasks

1. **Weekly Tasks**:
   - Review error logs for recurring issues
   - Monitor API usage and costs
   - Check component health on diagnostic dashboard

2. **Monthly Tasks**:
   - Update dependencies to latest compatible versions
   - Review and optimize database queries
   - Analyze performance metrics for optimization opportunities
   - Verify backup procedures

### Update Procedures

1. **Deploying Code Updates**:
   1. Push changes to your repository
   2. Render will automatically detect changes and rebuild
   3. Monitor the build and deployment process
   4. Verify functionality after deployment

2. **Manual Deployment**:
   - In the Render dashboard, navigate to your service
   - Click "Manual Deploy" > "Deploy latest commit"

### Backup and Restore Processes

1. **Database Backups**:
   - Supabase provides automatic daily backups
   - For manual backups:
     ```
     pg_dump -h database.supabase.co -U postgres -d postgres > backup.sql
     ```

2. **Restore Process**:
   - Create a new database if needed
   - Restore from backup:
     ```
     psql -h database.supabase.co -U postgres -d postgres < backup.sql
     ```

3. **Application State**:
   - All critical state is stored in the database
   - Temporary files and caches can be regenerated

### Scaling Guidance

1. **Vertical Scaling** (Recommended first approach):
   - In Render dashboard, navigate to your service
   - Click "Change Plan"
   - Select a plan with more resources

2. **Horizontal Scaling** (For high-traffic scenarios):
   - Implement a load balancer
   - Configure multiple service instances
   - Ensure database can handle increased connections

## Security

### Security Best Practices

1. **API Security**:
   - Use HTTPS for all communications
   - Implement rate limiting for API endpoints
   - Validate all input data using validation strategies

2. **Data Security**:
   - Encrypt sensitive data at rest
   - Implement proper data retention policies
   - Regularly audit data access

3. **Infrastructure Security**:
   - Keep all dependencies updated
   - Use minimal permission services
   - Implement proper network controls

### Access Control Management

1. **Service Access**:
   - Limit Render dashboard access to necessary personnel
   - Use separate accounts for each team member
   - Implement two-factor authentication

2. **Database Access**:
   - Use service accounts with minimal permissions
   - Rotate database credentials regularly
   - Audit database access logs

### Secret Rotation Procedures

1. **API Keys**:
   - Rotate OpenAI API keys quarterly
   - Update Render environment variables after rotation
   - Verify application functionality after key rotation

2. **Database Credentials**:
   - Generate new Supabase API keys
   - Update environment variables
   - Revoke old credentials after confirming new ones work

### Vulnerability Management

1. **Dependency Scanning**:
   - Run `pip-audit` regularly to check for vulnerabilities
   - Update vulnerable dependencies promptly
   - Consider implementing automated dependency scanning

2. **Security Updates**:
   - Apply security patches quickly
   - Test security updates in staging before production
   - Maintain a security incident response plan

## Reference

### API Endpoint Documentation

| Endpoint | Method | Description | Example |
|----------|--------|-------------|---------|
| `/api/health` | GET | Check service health | `curl https://your-service.onrender.com/api/health` |
| `/api/upload` | POST | Upload a resume for processing | `curl -F "file=@resume.pdf" https://your-service.onrender.com/api/upload` |
| `/api/optimize` | POST | Optimize a resume for a job | `curl -X POST -H "Content-Type: application/json" -d '{"resume_id":"123","job_description":"..."}' https://your-service.onrender.com/api/optimize` |
| `/api/download/:id/:format` | GET | Download processed resume | `curl https://your-service.onrender.com/api/download/123/pdf -o enhanced_resume.pdf` |
| `/diagnostic/diagnostics` | GET | View system diagnostics | Browser access |

### Environment Variable Reference

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `PORT` | No | 5000 | Port the app listens on |
| `OPENAI_API_KEY` | Yes | None | OpenAI API key |
| `SUPABASE_URL` | Yes | None | Supabase project URL |
| `SUPABASE_KEY` | Yes | None | Supabase service role key |
| `DEBUG` | No | false | Enable debug mode |
| `LOG_LEVEL` | No | INFO | Logging verbosity |
| `PDF_GENERATION_MODE` | No | cloud_latex | PDF generation method |
| `MAX_UPLOAD_SIZE_MB` | No | 10 | Maximum upload size in MB |
| `API_RATE_LIMIT` | No | 60 | Rate limit per minute |
| `TIMEOUT_SECONDS` | No | 30 | API timeout in seconds |

### Configuration Options

The application can be configured through environment variables or command-line arguments:

**Command-line Arguments**:
- `--port`: Specify the port to run on (e.g., `--port 8080`)
- `--debug`: Enable debug mode (e.g., `--debug`)
- `--log-level`: Set logging level (e.g., `--log-level DEBUG`)

**Configuration File** (optional):
Create a `config.json` file in the application root:
```json
{
  "openai_api_key": "your_key_here",
  "supabase_url": "your_url_here",
  "supabase_key": "your_key_here",
  "pdf_generation_mode": "cloud_latex",
  "max_upload_size_mb": 10
}
```

### Performance Tuning Guidance

1. **API Performance**:
   - Increase `WORKER_PROCESSES` for parallel processing
   - Adjust `TIMEOUT_SECONDS` based on expected processing time
   - Consider `BATCH_SIZE` for bulk operations

2. **Memory Optimization**:
   - Configure `MAX_MEMORY_MB` to prevent crashes
   - Set `CACHE_TTL_SECONDS` to control cache expiration
   - Use `CLEANUP_INTERVAL_MINUTES` for temporary file cleanup

3. **Database Performance**:
   - Implement the `DB_POOL_SIZE` setting based on concurrency
   - Use `DB_STATEMENT_TIMEOUT_MS` to prevent long-running queries
   - Configure `DB_MAX_CONNECTIONS` based on service tier

## Developer Onboarding

### Local Development Setup

1. **Clone the repository**:
   ```bash
   git clone https://github.com/your-org/resume-o.git
   cd resume-o
   ```

2. **Create a virtual environment**:
   ```bash
   python -m venv simple-venv
   source simple-venv/bin/activate   # On Windows: simple-venv\Scripts\activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables**:
   Create a `.env` file:
   ```
   OPENAI_API_KEY=your_key_here
   SUPABASE_URL=your_url_here
   SUPABASE_KEY=your_key_here
   PORT=5001
   DEBUG=true
   ```

5. **Run the application**:
   ```bash
   python working_app.py --port 5001 --debug
   ```

6. **Access the application**:
   Open `http://localhost:5001/api/health` to verify it's running

### Testing Procedures

1. **Run automated tests**:
   ```bash
   python -m pytest tests/
   ```

2. **Run the test pipeline**:
   ```bash
   python test_pipeline.py --resume test_files/sample_resume.pdf --job test_files/sample_job.txt
   ```

3. **Test individual components**:
   ```bash
   # Test resume parsing
   python test_resume_processing.py --test parse
   
   # Test optimization
   python test_resume_processing.py --test optimize
   
   # Test PDF generation
   python test_resume_processing.py --test pdf
   ```

4. **Performance testing**:
   ```bash
   python large_input_test.py --iterations 10 --output-dir test_results
   ```

### Contribution Workflow

1. **Create a feature branch**:
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes and test locally**

3. **Run validation**:
   ```bash
   python production_checklist.py --verify
   ```

4. **Commit your changes**:
   ```bash
   git add .
   git commit -m "Add your feature description"
   ```

5. **Push your branch and create a pull request**:
   ```bash
   git push origin feature/your-feature-name
   ```

6. **CI/CD process will run tests automatically**

### Code Structure Overview

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
├── test_files/            # Sample files for testing
└── tests/                 # Automated tests
```

**Key Components**:

- **API Layer**: Handles HTTP requests and responses
- **Core Processing**: Resume parsing, enhancement and optimization
- **PDF Generation**: Converts enhanced data to documents
- **Validation**: Ensures data integrity
- **Diagnostics**: Monitors system health
- **Database**: Stores resume and job data

---

This deployment guide provides a comprehensive reference for deploying, monitoring, maintaining, and securing the Resume-O application on Render. For additional assistance, contact the development team. 