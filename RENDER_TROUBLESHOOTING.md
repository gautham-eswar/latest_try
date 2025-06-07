# Render Deployment Troubleshooting

This guide helps resolve common issues when deploying the Resume Optimizer to Render, covering both **Native Python Runtime** and **Docker** deployments.

## Common Deployment Issues

### Dependency Conflicts (Python Runtime)

**Issue**: Build fails with dependency conflict errors when using the Python runtime.

**Solution**:
1. Ensure `requirements.txt` has properly pinned and compatible versions.
2. Check the build logs on Render for the specific packages causing the conflict.
3. For the `httpx`/`supabase` conflict, ensure a compatible range is used, e.g., `httpx>=0.24.0,<0.26.0`.

### Build Failures (Docker)

**Issue**: The Docker build fails on Render.

**Solution**:
1. **Test the build locally first**: `docker build .`
2. Check Render build logs for the specific `RUN` command in your `Dockerfile` that is failing.
3. Ensure your `Dockerfile` is in the root of your repository.
4. Verify that all necessary system dependencies (like `texlive-latex-base`) are installed via `apt-get` in the `Dockerfile`.

### Missing API Key or Environment Variables

**Issue**: Application deploys but returns errors due to missing environment variables like `OPENAI_API_KEY`.

**Solution**:
1. In the Render dashboard, go to the **Environment** tab for your service.
2. Ensure `OPENAI_API_KEY`, `SUPABASE_URL`, and `SUPABASE_KEY` are all set correctly.
3. For Docker deployments, these variables are injected into the container at runtime.
4. For Python runtime deployments, they are set in the shell environment.
5. Redeploy the service after adding or updating variables to ensure they are applied.

### Port and Startup Issues

**Issue**: Application fails to start, often with `502 Bad Gateway` errors.

**Solution**:
- **For Python Runtime**:
  1. Ensure your **Start Command** is `gunicorn working_app:app`.
  2. Verify that `working_app.py` is set to run on `0.0.0.0` and uses the `$PORT` environment variable provided by Render.

- **For Docker Runtime**:
  1. Ensure your `Dockerfile` uses `EXPOSE 8080` (or another port) and that your `CMD` instruction binds your application to `0.0.0.0:8080`.
  2. The `CMD` in the `Dockerfile` (`gunicorn --bind 0.0.0.0:8080 ...`) should handle this. Render automatically detects the exposed port.
  3. Check startup logs for any application-level errors preventing Gunicorn from starting.

### Memory Limits

**Issue**: Application crashes with out-of-memory errors

**Solution**:
1. Upgrade to a higher-tier Render plan with more memory
2. Reduce memory usage in your application
3. Add the `MALLOC_ARENA_MAX=2` environment variable

### Supabase Connection Issues

**Issue**: Application fails to connect to Supabase

**Solution**:
1. Verify both `SUPABASE_URL` and `SUPABASE_KEY` are set correctly
2. Check network rules to ensure Render can access your Supabase instance
3. Manually initialize the database in your application

## Debugging

### Viewing Logs

1. In the Render dashboard, go to your service
2. Click on "Logs" in the left sidebar
3. Set the log level to "Debug" for more detailed information

### Testing Locally

Test your application in a Render-like environment before deploying.

- **For Python Runtime**:
  ```bash
  export RENDER=true
  export PORT=8080
  export FLASK_ENV=production
  pip install -r requirements.txt
  python working_app.py
  ```

- **For Docker Runtime**:
  ```bash
  docker build -t resume-optimizer-local .
  docker run -p 8080:8080 \
    -e OPENAI_API_KEY=your_key \
    -e SUPABASE_URL=your_url \
    -e SUPABASE_KEY=your_key \
    resume-optimizer-local
  ```

### HTTP 502 Bad Gateway

If you see 502 errors immediately after deployment:

1. Check startup logs for errors
2. Ensure your app is listening on 0.0.0.0 and the correct port
3. Verify your app responds to the health check endpoint

## Getting Support

If you still face issues:

1. Check [Render's Documentation](https://render.com/docs)
2. Search the [Render Community Forum](https://community.render.com/)
3. Contact Render support at [support@render.com](mailto:support@render.com) 