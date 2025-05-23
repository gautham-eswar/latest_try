# Dockerizing the Resume Optimizer Application

## 1. Objective

The primary goal of Dockerizing the Resume Optimizer Flask application is to ensure consistent and reliable deployment across different environments (development, testing, production). Docker containers encapsulate the application and its dependencies, providing environment isolation, simplifying setup, and promoting scalability.

## 2. `Dockerfile` Components

This section outlines the essential components of the `Dockerfile` needed to containerize the application.

### Base Image
A Python base image is required. Consider using a slim variant to reduce the final image size.
*   **Recommendation:** `python:3.9-slim` or `python:3.10-slim` (choose based on project's Python version).
    ```dockerfile
    FROM python:3.9-slim
    ```

### Working Directory
Set a working directory within the container for the application code.
*   **Example:**
    ```dockerfile
    WORKDIR /app
    ```

### Copy Application Code
Copy the application source code into the container.
*   **Example:**
    ```dockerfile
    COPY . /app
    ```
    *(Consider using a `.dockerignore` file to exclude unnecessary files/directories).*

### Install Python Dependencies
Copy the `requirements.txt` file and install the Python packages.
*   **Example:**
    ```dockerfile
    COPY requirements.txt .
    RUN pip install --no-cache-dir -r requirements.txt
    ```

### Install System Dependencies
The application requires LaTeX (for PDF generation) and `pdfinfo` (from `poppler-utils` for checking PDF page counts). These need to be installed using the system's package manager.
*   **Explanation:** LaTeX is used by the `Pipeline/latex_generation.py` module to convert structured resume data into `.tex` files and then compile them into PDFs. `pdfinfo` is used to determine the number of pages in a generated PDF, which can be part of the adaptive page sizing logic.
*   **Example (`apt-get` for Debian-based images like `python:*-slim`):**
    ```dockerfile
    RUN apt-get update && apt-get install -y --no-install-recommends \
        texlive-latex-base \
        texlive-fonts-recommended \
        texlive-latex-extra \
        # texlive-fonts-extra # Consider if specific fonts are needed by templates
        # texlive-xetex       # Consider if XeTeX/LuaTeX specific features are used
        # Add any other specific texlive packages if known to be needed by the resume templates
        poppler-utils \
        && apt-get clean \
        && rm -rf /var/lib/apt/lists/*
    ```
    *   **Note:** `texlive-full` is a comprehensive option but is very large (several GBs). It's highly recommended to start by installing specific `texlive` packages like `texlive-latex-base`, `texlive-fonts-recommended`, and `texlive-latex-extra`. If PDF generation fails due to missing LaTeX components, identify the missing packages from the LaTeX error logs and add them explicitly.

### Environment Variables
Configure environment variables required by the application. Some are essential for runtime, while others are for Flask configuration.
*   **Required Runtime Variables:**
    *   `OPENAI_API_KEY`: Your API key for OpenAI services.
    *   `SUPABASE_URL`: The URL for your Supabase project.
    *   `SUPABASE_KEY`: The public `anon` key for your Supabase project.
*   **Optional/Build-time or Runtime Variables for Flask:**
    *   `FLASK_APP`: Specifies the entry point of the Flask application (e.g., `working_app.py` or `your_app_module:create_app_function`).
    *   `FLASK_ENV`: Sets the environment (e.g., `production`, `development`).
    *   `PORT` or `FLASK_RUN_PORT`: Defines the port the application will listen on (e.g., `8080`). Gunicorn uses the port specified in its bind address.
*   **Setting in Dockerfile (for defaults, can be overridden at runtime):**
    ```dockerfile
    ENV FLASK_APP=working_app.py
    ENV FLASK_ENV=production
    ENV PORT=8080 
    # Note: OPENAI_API_KEY, SUPABASE_URL, SUPABASE_KEY should NOT be hardcoded here.
    # They should be passed during 'docker run' or via orchestration tools.
    ```

### Expose Port
Inform Docker that the container listens on a specific network port at runtime.
*   **Example (if the app runs on port 8080 internally):**
    ```dockerfile
    EXPOSE 8080
    ```
    *(This port should match the port used in the `CMD` instruction, e.g., for Gunicorn).*

### Entrypoint/CMD
Define the command to run the application when the container starts.
*   **Production (recommended using Gunicorn):**
    Assumes your Flask app instance is created by a function `create_app()` in `working_app.py`.
    ```dockerfile
    # Example: CMD ["gunicorn", "--bind", "0.0.0.0:8080", "working_app:create_app()"]
    # Adjust "working_app:create_app()" to match your actual Flask app factory or instance.
    # If 'create_app' is not a factory, it might be 'working_app:app'.
    CMD ["gunicorn", "--workers", "2", "--threads", "4", "--worker-class", "gthread", "--bind", "0.0.0.0:8080", "working_app:create_app()"]
    ```
*   **Development (using Flask's built-in server):**
    ```dockerfile
    # CMD ["flask", "run", "--host=0.0.0.0", "--port=8080"]
    ```
    *(Gunicorn is preferred for production due to its robustness and performance).*

## 3. `.dockerignore` File

A `.dockerignore` file is crucial for specifying files and directories that should be excluded from the build context sent to the Docker daemon. This helps reduce the image size, speed up the build process, and avoid inadvertently copying sensitive files.

*   **Purpose:**
    *   Exclude version control directories (e.g., `.git/`).
    *   Exclude Python virtual environments (e.g., `env/`, `venv/`).
    *   Exclude Python bytecode files (e.g., `__pycache__/`, `*.pyc`).
    *   Exclude local development artifacts, instance folders, or temporary output.
    *   Exclude test files or directories not needed in the production image.
*   **Sample `.dockerignore` Content:**
    ```dockerignore
    # Git and version control
    .git/
    .gitignore
    .gitattributes

    # Python specific
    __pycache__/
    *.pyc
    *.pyo
    *.pyd
    *.egg-info/
    .Python
    env/
    venv/
    pip-log.txt
    pip-delete-this-directory.txt
    .pytest_cache/
    .tox/
    
    # IDE and editor files
    .vscode/
    .idea/
    *.swp
    *.swo

    # Local development artifacts
    local_dev_data/
    instance/ # If used for local Flask instance configuration
    test_files/output_local/ # Example local output
    Pipeline/output/ # Local output from pipeline runs
    *.log # General log files if not needed in image

    # Documentation / OS specific
    docs/
    .DS_Store
    Thumbs.db

    # Secrets / Config (if any accidentally exist outside env vars)
    *.env # Ensure .env files are not copied
    secrets.ini 
    config.local.py

    # Add other project-specific files/directories to ignore
    # e.g., large data files, test datasets, specific local scripts
    ```

## 4. Build Command Example

Command to build the Docker image from the `Dockerfile`.
```bash
docker build -t resume-optimizer-app .
```
*   `-t resume-optimizer-app`: Tags the image with the name `resume-optimizer-app`.

## 5. Run Command Example

Command to run the Docker container from the built image.
```bash
docker run -p 8080:8080 \
    -e OPENAI_API_KEY="your_actual_openai_api_key" \
    -e SUPABASE_URL="your_actual_supabase_url" \
    -e SUPABASE_KEY="your_actual_supabase_key" \
    # -e FLASK_APP="working_app.py" # Optional if set in Dockerfile
    # -e FLASK_ENV="production"   # Optional if set in Dockerfile
    # -e PORT="8080"              # Gunicorn binds to port specified in CMD
    resume-optimizer-app
```
*   `-p 8080:8080`: Maps port 8080 of the host to port 8080 of the container.
*   `-e VARIABLE_NAME="value"`: Sets environment variables required by the application. **Replace placeholder values with your actual secrets and configuration.**

## 6. Important Considerations

### Image Size
*   The `texlive` packages required for LaTeX PDF generation can significantly increase the image size.
*   **Strategies to minimize size:**
    *   **Carefully select `texlive` packages:** Start with minimal packages (`texlive-latex-base`, `texlive-fonts-recommended`, `texlive-latex-extra`) and add specific ones only as identified by LaTeX compilation errors. Avoid `texlive-full`.
    *   **Multi-stage builds:** (More advanced) Use one stage to compile LaTeX documents or install dependencies, and then copy only the necessary artifacts to a smaller final image. This is complex for this application as LaTeX is a runtime dependency.
    *   Ensure `apt-get clean` and `rm -rf /var/lib/apt/lists/*` are used after `apt-get install` to remove cached package lists.
    *   Utilize a comprehensive `.dockerignore` file.

### Security
*   **Do NOT hardcode secrets** (like `OPENAI_API_KEY`, `SUPABASE_KEY`) directly in the `Dockerfile`.
*   Pass secrets as environment variables at runtime using `docker run -e`, Docker Compose, Kubernetes secrets, or other secure configuration management tools.
*   Regularly update the base image (`FROM python:3.9-slim`) and dependencies to patch security vulnerabilities. Consider using tools that scan images for vulnerabilities.
*   Run the container with a non-root user if possible (requires additional `Dockerfile` instructions).
```
