# Resume Optimizer - Render Deployment Guide

This document provides step-by-step instructions for deploying the Resume Optimizer application to [Render](https://render.com/).

## Prerequisites

- A [Render account](https://render.com/signup)
- Git repository with your Resume Optimizer code
- OpenAI API key

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

- `OPENAI_API_KEY`: Your OpenAI API key
- `FLASK_ENV`: `production`
- `PORT`: `8080`
- `PDF_GENERATION_MODE`: `fallback`
- `SECRET_KEY`: A secure random string for Flask's session encryption

Optional variables (if using Supabase):
- `SUPABASE_URL`: Your Supabase project URL
- `SUPABASE_KEY`: Your Supabase anon key

### 5. Deploy Your Service

1. Click **Create Web Service**
2. Render will begin the deployment process
3. Monitor the build logs for any errors
4. Once completed, your service will be available at `https://<service-name>.onrender.com`

### 6. Verify Deployment

Run the test script to verify that all endpoints are working correctly:

```bash
# Install test dependencies
pip install requests

# Run the test deployment script
python test_deployment.py --url https://<service-name>.onrender.com
```

## Troubleshooting

### Common Issues

1. **Application Error (Status 503)**
   - Check application logs in Render dashboard
   - Verify your requirements.txt is complete
   - Ensure gunicorn is installed

2. **API Key Issues**
   - Verify your OPENAI_API_KEY is correct and active
   - Check if your API key has sufficient quota

3. **PDF Generation Fails**
   - Check the buildpack.yml file has correct LaTeX dependencies
   - Set PDF_GENERATION_MODE to fallback for simpler PDF generation

### Viewing Logs

To view application logs and troubleshoot issues:
1. Go to your Web Service in the Render Dashboard
2. Select the **Logs** tab
3. Filter logs as needed to identify issues

## Auto-Deployment

By default, Render automatically deploys when you push to your repository. You can disable this in the Render dashboard if needed.

## Custom Domain (Optional)

To use a custom domain:
1. Go to your Web Service settings
2. Click **Settings** > **Custom Domain**
3. Follow the instructions to verify and set up your domain

## Performance and Scaling

Render's free tier has limitations. For production use, consider:
- Upgrading to a paid plan
- Setting up autoscaling for handling traffic spikes
- Configuring additional disk space for uploads 