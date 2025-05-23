# Deploying Resume Optimizer to Render

This guide provides step-by-step instructions for deploying the Resume Optimizer application to Render.

## Prerequisites

- A Render account
- Your code pushed to a Git repository (GitHub, GitLab, etc.)
- An OpenAI API key

## Deployment Steps

### 1. Push the Latest Code to Git

Ensure the latest code with the optimized dependencies is pushed to your repository:

```bash
git add .
git commit -m "[Gautham] Optimize for Render deployment"
git push origin your-branch-name
```

### 2. Create a New Web Service on Render

1. Log in to your Render dashboard at https://dashboard.render.com/
2. Click **New** and select **Web Service**
3. Connect your repository
4. Configure the service:
   - **Name**: resume-optimizer (or your preferred name)
   - **Runtime**: Python 3
   - **Build Command**: `pip install -r requirements-render.txt`
   - **Start Command**: `gunicorn wsgi:app`

### 3. Configure Environment Variables

Add the following environment variables:
- `OPENAI_API_KEY`: Your OpenAI API key
- `PORT`: 8080
- `FLASK_ENV`: production
- `PDF_GENERATION_MODE`: fallback (or your preferred mode)

### 4. Deploy the Service

Click **Create Web Service** to deploy.

## Troubleshooting

If you encounter build failures:

1. Check the build logs for specific errors
2. Ensure all dependencies are properly specified in `requirements-render.txt`
3. For packages that require compilation, try using pre-built wheels
4. Consider using a more powerful instance if the build is timing out

## Updating the Deployment

To update your deployment:
1. Push changes to your Git repository
2. Render will automatically deploy the latest version if auto-deploy is enabled
3. You can also manually trigger a deploy from the Render dashboard

## Monitoring

- Monitor application performance via the Render dashboard
- Check application logs for errors
- Use the `/diagnostics` endpoint for detailed system status

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