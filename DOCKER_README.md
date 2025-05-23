# Dockerization Guide for Resume Optimizer

## 1. Objective

Dockerizing this Flask application aims to create a consistent, portable, and reproducible environment for development, testing, and deployment. It encapsulates the application, its Python dependencies, and all necessary system-level dependencies (like LaTeX and pdfinfo) into a Docker image.

## 2. `Dockerfile` Components

The `Dockerfile` is the blueprint for building the Docker image.

*   **Base Image:** Uses a Python slim image (e.g., `python:3.9-slim`) to keep the image size relatively small while providing a Python runtime.
    ```dockerfile
    FROM python:3.9-slim
    ```

*   **Environment Variables (Defaults & Info):**
    ```dockerfile
    ENV PYTHONUNBUFFERED=1
    ENV FLASK_APP=working_app.py
    ENV FLASK_RUN_PORT=8080
    # For production, critical secrets like OPENAI_API_KEY, SUPABASE_URL, SUPABASE_KEY
    # should be set at runtime via the hosting platform (e.g., Render environment variables)
    # rather than being hardcoded in the Dockerfile.
    # Example (DO NOT USE ACTUAL KEYS HERE IN A COMMITTED DOCKERFILE):
    # ENV OPENAI_API_KEY="your_openai_api_key_placeholder"
    ```

*   **Working Directory:** Sets the default directory for subsequent commands.
    ```dockerfile
    WORKDIR /app
    ```

*   **Install System Dependencies:** Installs necessary tools for the application, including LaTeX for PDF generation, `poppler-utils` for `pdfinfo`, and `gcc`/`python3-dev` for building certain Python packages.
    ```dockerfile
    ENV DEBIAN_FRONTEND=noninteractive
    RUN apt-get update && \
        apt-get install -y --no-install-recommends \
        texlive-latex-base \
        texlive-fonts-recommended \
        texlive-latex-extra \
        poppler-utils \
        gcc \
        python3-dev \
        && apt-get clean && \
        rm -rf /var/lib/apt/lists/*
    ```
    *Note: `texlive-full` is an alternative but very large. The selected packages aim for a balance.*

*   **Install Python Dependencies:** Copies `requirements.txt` and installs packages.
    ```dockerfile
    COPY requirements.txt .
    RUN pip install --no-cache-dir -r requirements.txt
    ```

*   **Copy Application Code:** Copies the rest of the application code into the image.
    ```dockerfile
    COPY . .
    ```

*   **Expose Port:** Informs Docker that the application listens on a specific port.
    ```dockerfile
    EXPOSE 8080
    ```

*   **Entrypoint/CMD:** Defines the command to run when the container starts. Gunicorn is recommended for production.
    ```dockerfile
    CMD ["gunicorn", "--bind", "0.0.0.0:8080", "working_app:create_app()"]
    ```
    *For development, you might temporarily use: `CMD ["flask", "run", "--host=0.0.0.0", "--port=8080"]`*

## 3. `.dockerignore` File

This file specifies which files and directories should be excluded when building the Docker image. This helps reduce image size and build time, and avoids including sensitive files.

**Sample `.dockerignore` content:**
```
# Git
.git/
.gitignore

# Python
__pycache__/
*.pyc
*.pyo
*.pyd
.Python
env/
venv/
pip-log.txt
pip-delete-this-directory.txt
*.egg-info/
.pytest_cache/
.mypy_cache/
.nox/

# IDE / Editor specific
.vscode/
.idea/
*.sublime-project
*.sublime-workspace

# OS specific
.DS_Store
Thumbs.db

# Local instance data / sensitive files
instance/
local_dev_data/
test_files/output_local/
.env
.env.*
secrets/
*.pem
*.key

# Docker
Dockerfile
.dockerignore
docker-compose.yml

# Build artifacts
dist/
build/
*.egg
*.whl

# Log files
*.log
logs/

# Temp files from LaTeX compilation if they escape the temp directory
*.aux
*.fls
*.fdb_latexmk
*.synctex.gz
```

## 4. Build Command Example

```bash
docker build -t resume-optimizer-app .
```
(Run from the root of the project where the Dockerfile is located)

## 5. Run Command Example

To run the container (assuming secrets are NOT baked into the Dockerfile):

```bash
docker run -p 8080:8080 \
  -e OPENAI_API_KEY="your_actual_openai_key" \
  -e SUPABASE_URL="your_actual_supabase_url" \
  -e SUPABASE_KEY="your_actual_supabase_key" \
  -e FLASK_APP="working_app.py" \
  resume-optimizer-app
```

If secrets are baked into the Dockerfile (as done for current testing convenience):

```bash
docker run --rm -p 8080:8080 resume-optimizer-app
```
(The `--rm` flag is good for cleaning up containers after they exit during testing)

To run the test script specifically:

```bash
docker run --rm resume-optimizer-app python test_enhancement_to_storage_pipeline.py
```

## 6. Important Considerations

*   **Image Size:** TeX Live can make the image quite large. If this becomes an issue, explore:
    *   Using even more minimal TeX Live package sets if the exact requirements are known.
    *   Multi-stage builds (e.g., build assets in a larger image, copy to a smaller runtime image if applicable, though less so for LaTeX itself).
*   **Security:** For production, DO NOT hardcode secrets (OPENAI_API_KEY, SUPABASE_KEY, etc.) in the Dockerfile. Use runtime environment variables provided by your hosting platform (like Render).

## 7. Render Deployment Notes

*   **Suitability:** This Docker setup is well-suited for deployment on platforms like Render.
*   **Environment Variables:** When deploying to Render:
    *   Create a "Web Service" on Render and point it to your GitHub repository.
    *   Render will build the image using the Dockerfile.
    *   Go to your service's "Environment" settings in Render.
    *   Add the following as environment variables:
        *   `OPENAI_API_KEY`
        *   `SUPABASE_URL`
        *   `SUPABASE_KEY` (use the appropriate one, e.g., `service_role` if needed by the backend, or `anon` if sufficient)
        *   `FLASK_APP` (e.g., `working_app.py`)
        *   `PYTHONUNBUFFERED=1` (good practice, already in Dockerfile)
        *   Optionally, `FLASK_ENV=production`.
*   **Health Checks:**
    *   Render can use HTTP health checks to monitor your service.
    *   Your application has an `/api/health` endpoint. Configure Render to use this path for health checks.
*   **Port:** Render should automatically detect the `EXPOSE 8080` and the Gunicorn command binding to `0.0.0.0:8080`.
