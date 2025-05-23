# 1. Base Image
FROM python:3.9-slim

# 2. Set Environment Variables
ENV PYTHONUNBUFFERED=1
ENV FLASK_APP=working_app.py
ENV FLASK_RUN_PORT=8080
# For production, critical secrets like OPENAI_API_KEY, SUPABASE_URL, SUPABASE_KEY
# should be set at runtime via the hosting platform (e.g., Render environment variables)
# rather than being hardcoded in the Dockerfile.
# Example usage when running the container:
# docker run -e OPENAI_API_KEY="your_key" -e SUPABASE_URL="your_url" -e SUPABASE_KEY="your_key" ...

# 3. Set Working Directory
WORKDIR /app

# 4. Install System Dependencies (LaTeX, pdfinfo, build tools)
# Reduce verbosity of apt-get and ensure non-interactive frontend
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

# 5. Copy requirements.txt and Install Python Dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 6. Copy Application Code
COPY . .

# 7. Expose Port
EXPOSE 8080

# 8. Set Default Command (Using Gunicorn for production)
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "working_app:create_app()"] 