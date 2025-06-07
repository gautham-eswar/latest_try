# Deploying Resume Optimizer to Render

This guide provides step-by-step instructions for deploying the Resume Optimizer application to Render using either a **Native Python Runtime** or **Docker**.

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

### 2. Choose Your Deployment Method

You can deploy this application on Render in two ways:

- **As a Python Web Service:** Render manages the Python environment. This is simpler for standard Python applications.
- **As a Docker Container:** You provide a `Dockerfile`, and Render runs it. This offers maximum control and consistency.

---

### Method 1: Deploying as a Python Web Service

Follow these steps if you want Render to handle the Python environment for you.

**1. Create a New Web Service on Render**
- Log in to your Render dashboard.
- Click **New** and select **Web Service**.
- Connect your repository.

**2. Configure the Service**
- **Name**: resume-optimizer (or your preferred name)
- **Runtime**: `Python 3`
- **Build Command**: `pip install -r requirements.txt`
- **Start Command**: `gunicorn working_app:app`

**3. Configure Environment Variables**
- Add your `OPENAI_API_KEY`, `SUPABASE_URL`, `SUPABASE_KEY`, etc.

**4. Deploy**
- Click **Create Web Service**.

---

### Method 2: Deploying as a Docker Container

Follow these steps to deploy the application using the provided `Dockerfile`. This is the recommended method for consistency.

**1. Create a New Web Service on Render**
- Log in to your Render dashboard.
- Click **New** and select **Web Service**.
- Connect your repository.

**2. Configure the Service**
- **Name**: resume-optimizer-docker (or your preferred name)
- **Runtime**: `Docker`
- Render will automatically detect and use your `Dockerfile`. You do **not** need to specify a Build or Start command in the Render UI.

**3. Configure Environment Variables**
- Add your `OPENAI_API_KEY`, `SUPABASE_URL`, `SUPABASE_KEY`, etc.
- The `Dockerfile` exposes port 8080, which Render will use automatically.

**4. Deploy**
- Click **Create Web Service**.

---

## Post-Deployment

### Updating the Deployment

To update your deployment:
1. Push changes to your Git repository
2. Render will automatically deploy the latest version if auto-deploy is enabled
3. You can also manually trigger a deploy from the Render dashboard

### Monitoring

- Monitor application performance via the Render dashboard
- Check application logs for errors
- Use the `/diagnostic/diagnostics` endpoint for detailed system status

## Using Docker (Alternative)

You can also deploy the application using Docker:

```