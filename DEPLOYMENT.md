# Deployment Guide for Resume-O on Render

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

- **Git**: For version control and deployment to Render
- **GitHub Account**: To host your repository that Render will deploy from
- **LaTeX** (optional): Required for PDF generation functionality on your local machine for testing

### Required Permissions and Access

- Admin access to your Render account
- Owner or developer role on the GitHub repository
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
3. Connect to your GitHub repository containing the Resume-O application
4. Configure the service with the following settings:
   - **Name**: resume-optimization-service (or your preferred name)
   - **Environment**: Python
   - **Region**: Choose the region closest to your user base
   - **Branch**: main (or your production branch)
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `python app.py` (Render automatically sets the PORT environment variable)
   - **Instance Type**: Start with Standard (512 MB) or higher based on expected load

### 2. Environment Variable Configuration

Configure the following environment variables in the Render dashboard under the "Environment" tab:

| Variable | Description | Example |
|----------|-------------|---------|
| `OPENAI_API_KEY` | Your OpenAI API key | sk-... |
| `SUPABASE_URL` | URL of your Supabase project | https://[project-id].supabase.co |
| `SUPABASE_KEY` | Supabase service role API key | eyJ... |
| `DEBUG` | Enable/disable debug mode | false |
| `ENVIRONMENT` | Deployment environment | production |
| `PDF_GENERATION_MODE` | PDF generation method | cloud_latex |
| `LOG_LEVEL` | Logging verbosity | INFO |
| `MAX_UPLOAD_SIZE_MB` | Maximum upload size in MB | 10 |

Note: Render automatically sets `PORT` environment variable, so you don't need to specify it.

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

3. Copy the Supabase URL and API key from your project settings to use in Render environment variables

### 4. Build and Deployment Process

1. After configuring all settings, click "Create Web Service"
2. Render will automatically:
   - Clone your repository
   - Install dependencies from requirements.txt
   - Build the application
   - Start the service on the specified port

3. Monitor the build logs for any errors
4. Once completed, Render will provide a URL for your deployed application (typically https://your-service-name.onrender.com)

### 5. Post-Deployment Verification

1. Access the `/api/health` endpoint to verify the service is running:
   ```
   curl https://your-service-name.onrender.com/api/health
   ```

2. Check the diagnostic dashboard:
   ```
   https://your-service-name.onrender.com/diagnostic/diagnostics
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
1. Check build logs in Render dashboard for Python errors
2. Verify all required environment variables are set
3. Ensure requirements.txt includes all dependencies with specific versions
4. Confirm the start command is correct
5. Check if you need to increase the memory allocation for your service

#### Database Connection Issues

**Symptoms:**
- Application starts but returns 500 errors
- Log messages show database connection failures

**Possible Causes:**
- Incorrect Supabase credentials
- Network restrictions between Render and Supabase
- Missing database tables

**Resolution Steps:**
1. Verify Supabase URL and API key in Render environment variables
2. Check if Supabase project is active
3. Ensure database tables are properly created
4. Check the Database Network settings in Supabase to allow connections

#### OpenAI API Errors

**Symptoms:**
- Resume processing fails
- Logs show OpenAI API authentication errors

**Common Error Messages:**
```
"OpenAI API authentication failed: { "error": { "message": "Incorrect API key provided" } }"
"Reached OpenAI API rate limit, please try again later"
```

**Resolution Steps:**
1. Verify your OpenAI API key is valid and properly set in Render environment variables
2. Check your OpenAI account for usage limits or billing issues
3. Implement rate limiting or retry logic in your application
4. Consider upgrading your OpenAI plan for higher rate limits

### Error Interpretation Guide

| Log Message | Meaning | Resolution |
|-------------|---------|------------|
| `ModuleNotFoundError: No module named 'X'` | Missing dependency | Add dependency to requirements.txt |
| `OpenAI API authentication failed` | Invalid API key | Update OpenAI API key in environment variables |
| `Supabase client not available` | Database connection issue | Check Supabase credentials and network settings |
| `Address already in use` | Port conflict | This shouldn't happen on Render as they manage ports |
| `Failed to import PDF generator` | PDF generation setup issue | Check if LaTeX is installed or use a fallback mode |

### Support Information

- **Render Support**: Submit a ticket at [render.com/support](https://render.com/support)
- **Supabase Support**: [supabase.com/support](https://supabase.com/support)
- **OpenAI API Support**: [help.openai.com](https://help.openai.com)

## Monitoring

### Accessing Monitoring Dashboards

1. **Render Dashboard**:
   - Log in to [dashboard.render.com](https://dashboard.render.com)
   - Navigate to your service
   - View metrics, logs, and events under respective tabs

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
- **Memory Usage**: Should remain below instance limits (monitor for potential upgrades)
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
     - Disk usage

2. **Custom Application Alerts**:
   - Implement the monitoring.py module in your application
   - Configure threshold values in environment variables on Render:
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
   - Restart the service using the "Manual Deploy" button in Render dashboard
   - Roll back to previous deployment if recent changes caused issues
   - Scale up resources if performance-related (increase memory/CPU)
   - Rotate API keys if authentication issues persist

## Maintenance

### Routine Maintenance Tasks

1. **Weekly Tasks**:
   - Review error logs in Render dashboard
   - Monitor API usage and costs
   - Check component health on diagnostic dashboard

2. **Monthly Tasks**:
   - Update dependencies to latest compatible versions
   - Review and optimize database queries
   - Analyze performance metrics for optimization opportunities
   - Verify backup procedures

### Update Procedures

1. **Deploying Code Updates**:
   1. Push changes to your GitHub repository
   2. Render will automatically detect changes and rebuild (if auto-deploy is enabled)
   3. Monitor the build and deployment process in Render dashboard
   4. Verify functionality after deployment

2. **Manual Deployment**:
   - In the Render dashboard, navigate to your service
   - Click "Manual Deploy" > "Deploy latest commit"

### Backup and Restore Processes

1. **Database Backups**:
   - Supabase provides automatic daily backups
   - For additional manual backups, use Supabase dashboard or API

2. **Restore Process**:
   - Restore from backup using Supabase dashboard
   - If necessary, create a new Render service pointing to the restored database

3. **Application State**:
   - All critical state is stored in the database
   - Temporary files on Render are ephemeral and will be lost on restarts

### Scaling Guidance

1. **Vertical Scaling** (Recommended first approach):
   - In Render dashboard, navigate to your service
   - Click "Change Plan"
   - Select a plan with more resources (RAM/CPU)

2. **Horizontal Scaling** (For high-traffic scenarios):
   - Consider using Render's automatic scaling options
   - Ensure database can handle increased connections
   - Implement caching strategies if needed

## Security

### Security Best Practices

1. **API Security**:
   - Use Render's HTTPS endpoints for all communications
   - Implement rate limiting for API endpoints
   - Validate all input data using validation strategies

2. **Data Security**:
   - Encrypt sensitive data at rest in Supabase
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
   - Implement two-factor authentication for Render account

2. **Database Access**:
   - Use service accounts with minimal permissions
   - Rotate database credentials regularly
   - Audit database access logs in Supabase

### Secret Rotation Procedures

1. **API Keys**:
   - Rotate OpenAI API keys quarterly
   - Update Render environment variables after rotation
   - Verify application functionality after key rotation

2. **Database Credentials**:
   - Generate new Supabase API keys
   - Update environment variables in Render
   - Revoke old credentials after confirming new ones work

### Vulnerability Management

1. **Dependency Scanning**:
   - Use Render's vulnerability scanning if available
   - Regularly update Python dependencies to secure versions
   - Consider implementing automated dependency scanning in CI/CD

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
| `PORT` | No | Set by Render | Port the app listens on |
| `OPENAI_API_KEY` | Yes | None | OpenAI API key |
| `SUPABASE_URL` | Yes | None | Supabase project URL |
| `SUPABASE_KEY` | Yes | None | Supabase service role key |
| `DEBUG` | No | false | Enable debug mode |
| `LOG_LEVEL` | No | INFO | Logging verbosity |
| `PDF_GENERATION_MODE` | No | cloud_latex | PDF generation method |
| `MAX_UPLOAD_SIZE_MB` | No | 10 | Maximum upload size in MB |
| `API_RATE_LIMIT` | No | 60 | Rate limit per minute |
| `TIMEOUT_SECONDS` | No | 30 | API timeout in seconds |

### Render-Specific Configuration

The repository includes a `render.yaml` file that can be used for Infrastructure as Code deployment:

```yaml
services:
  - type: web
    name: resume-optimization
    env: python
    buildCommand: pip install -r requirements.txt
    startCommand: python app.py
    plan: standard
    branch: main
    envVars:
      - key: OPENAI_API_KEY
        sync: false
      - key: SUPABASE_URL
        sync: false
      - key: SUPABASE_KEY
        sync: false
      - key: DEBUG
        value: false
      - key: ENVIRONMENT
        value: production
      - key: PDF_GENERATION_MODE
        value: cloud_latex
```

### Performance Tuning Guidance

1. **API Performance**:
   - Increase Render instance size for more CPU/memory
   - Adjust `TIMEOUT_SECONDS` based on expected processing time
   - Consider `BATCH_SIZE` for bulk operations

2. **Memory Optimization**:
   - Configure `MAX_MEMORY_MB` to prevent crashes
   - Set `CACHE_TTL_SECONDS` to control cache expiration
   - Use `CLEANUP_INTERVAL_MINUTES` for temporary file cleanup

3. **Database Performance**:
   - Implement the `DB_POOL_SIZE` setting based on concurrency
   - Use `DB_STATEMENT_TIMEOUT_MS` to prevent long-running queries
   - Configure `DB_MAX_CONNECTIONS` based on Supabase service tier

## Developer Onboarding

### Local Development Setup

1. **Clone the repository**:
   ```bash
   git clone https://github.com/your-org/resume-o.git
   cd resume-o
   ```

2. **Create a virtual environment**:
   ```bash
   python3 -m venv simple-venv
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
   PORT=8085
   DEBUG=true
   ```

5. **Run the application**:
   ```bash
   python3 working_app.py --port 8085 --debug
   ```

6. **Access the application**:
   Open `http://localhost:8085/api/health` to verify it's running

### Testing Procedures

1. **Run automated tests**:
   ```bash
   python3 -m pytest tests/
   ```

2. **Run the test pipeline**:
   ```bash
   python3 test_pipeline.py --resume test_files/sample_resume.pdf --job test_files/sample_job.txt
   ```

3. **Test individual components**:
   ```bash
   # Test resume parsing
   python3 test_resume_processing.py --test parse
   
   # Test optimization
   python3 test_resume_processing.py --test optimize
   
   # Test PDF generation
   python3 test_resume_processing.py --test pdf
   ```

4. **Performance testing**:
   ```bash
   python3 large_input_test.py --iterations 10 --output-dir test_results
   ```

### Preparing for Render Deployment

1. **Verify the render.yaml file**:
   Ensure the render.yaml file contains the correct configuration

2. **Run production checklist**:
   ```bash
   python3 production_checklist.py --verify
   ```

3. **Test with production settings**:
   ```bash
   DEBUG=false ENVIRONMENT=production python3 app.py --port 8085
   ```

4. **Commit and push changes**:
   ```bash
   git add .
   git commit -m "Prepare for Render deployment"
   git push origin main
   ```

5. **Deploy to Render**:
   Follow the deployment steps in the first section of this document

---

This deployment guide provides a comprehensive reference for deploying, monitoring, maintaining, and securing the Resume-O application on Render. For additional assistance, contact the development team. 
 