# Render Deployment Troubleshooting

This guide helps resolve common issues when deploying the Resume Optimizer to Render.

## Common Deployment Issues

### Dependency Conflicts

**Issue**: Build fails with errors like: `ERROR: ResolutionImpossible: for help visit https://pip.pypa.io/en/latest/topics/dependency-resolution/#dealing-with-dependency-conflicts`

**Solution**:
1. Use `requirements-render.txt` with properly pinned versions
2. For httpx/Supabase conflict, use a compatible range: `httpx>=0.24.0,<0.26.0`
3. Update your service build command:
   ```
   pip install -r requirements-render.txt
   ```

### Missing API Key

**Issue**: Application deploys but returns 503 errors because OPENAI_API_KEY is missing

**Solution**:
1. In Render dashboard, go to Environment Variables
2. Add `OPENAI_API_KEY` with your valid OpenAI API key
3. Redeploy the application

### Port Issues

**Issue**: Application fails to start with port-related errors

**Solution**:
1. Ensure `PORT` env variable is set to match the port in your start command
2. Verify your start command is using `gunicorn wsgi:app` without hardcoded ports
3. Check for port conflicts in your code (wsgi.py should use the PORT env variable)

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

Test your application in a Render-like environment before deploying:

```bash
# In your local environment
export RENDER=true
export PORT=8080
export FLASK_ENV=production
python wsgi.py
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