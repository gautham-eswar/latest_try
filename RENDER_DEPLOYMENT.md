# Resume Optimizer - Render Deployment Guide

This document provides step-by-step instructions for deploying the Resume Optimizer application to [Render](https://render.com/).

## Prerequisites

- A [Render account](https://render.com/signup)
- Git repository with your Resume Optimizer code
- OpenAI API key (required)

## Deployment Steps

### 1. Push Code to Git

First, ensure your code is pushed to a Git repository (GitHub, GitLab, etc.):

```bash
# Initialize a Git repository if not already done
git init

# Add all files to Git
git add .

# Commit changes
git commit -m "Prepare for Render deployment"

# Add your remote repository
git remote add origin <your-git-repo-url>

# Push to your repository
git push -u origin main
```

### 2. Connect to Render

1. Log in to your [Render Dashboard](https://dashboard.render.com/)
2. Click **New** and select **Web Service**
3. Connect your Git repository
4. Follow the prompts to authorize Render to access your repository

### 3. Configure Deployment Settings

Render will automatically detect the `render.yaml` file in your repository and pre-configure your service settings. Review and adjust as needed:

- **Name**: `resume-optimizer` (or your preferred name)
- **Environment**: `Python`
- **Region**: Choose the region closest to your users
- **Branch**: `main` (or your deployment branch)
- **Build Command**: `pip install -r requirements.txt`
- **Start Command**: `gunicorn wsgi:app --log-level info`

### 4. Set Environment Variables

Add the following environment variables in the Render dashboard:

- `OPENAI_API_KEY`: Your OpenAI API key (required)
- `FLASK_ENV`: `production`
- `PORT`: `8080`
- `PDF_GENERATION_MODE`: `fallback`
- `SECRET_KEY`: A secure random string for Flask's session encryption
- `FLASK_APP`: `wsgi.py`

### 5. Deploy Your Service

1. Click **Create Web Service**
2. Render will begin the deployment process
3. Monitor the build logs for any errors
4. Once completed, your service will be available at `https://<service-name>.onrender.com`

## Troubleshooting

### Common Issues

1. **ImportError for werkzeug.contrib.ProxyFix**
   - This is caused by using an outdated version of Werkzeug
   - **Fix**: Update the import in app.py to use `from werkzeug.middleware.proxy_fix import ProxyFix` 

2. **SyntaxError in database.py**
   - Caused by malformed docstring or comment in database.py
   - **Fix**: Edit database.py to ensure all docstrings are properly formatted

3. **API Key Issues**
   - **Fix**: Verify your OPENAI_API_KEY is correctly set in environment variables
   - You can use the configure_render.sh script to set all environment variables

4. **PDF Generation Fails**
   - **Fix**: Set PDF_GENERATION_MODE to fallback to use simpler PDF generation

5. **Database Connection Issues**
   - The application will automatically fall back to an in-memory database
   - For persistent storage, configure Supabase credentials properly

### Checking Deployment Status

To verify the deployment is working correctly:

1. Visit `https://<service-name>.onrender.com/api/health`
2. Check the /status endpoint for more detailed diagnostics
3. Run test_deployment.py to verify all endpoints

## Using Docker (Alternative)

You can also deploy the application using Docker:

```bash
# Build the Docker image
docker build -t resume-optimizer .

# Run the container
docker run -p 8080:8080 -e OPENAI_API_KEY=your_key_here resume-optimizer
```

## Performance and Scaling

Render's free tier has limitations. For production use, consider:
- Upgrading to a paid plan
- Setting up autoscaling for handling traffic spikes
- Configuring additional disk space for uploads 