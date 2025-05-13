# Use an official Python runtime as a parent image
FROM python:3.11-slim-buster

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Install system dependencies including LaTeX
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    texlive-base \
    texlive-latex-base \
    texlive-fonts-recommended \
    texlive-latex-recommended \
    texlive-latex-extra \
    # Clean up apt caches to reduce image size
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container at /app
COPY requirements.txt /app/

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Add a build argument that changes with each build to bust the cache for subsequent layers
ARG CACHE_BUST=$(date +%s)
RUN echo "Cache bust: $CACHE_BUST"

# Copy the rest of the application code into the container at /app
COPY . /app/

# Dump the working_app.py file to console for debugging
RUN echo "Content of working_app.py:" && cat working_app.py | head -50

# Check if pdflatex is installed correctly
RUN which pdflatex || echo "pdflatex NOT FOUND in PATH"

# Expose port 8080 to the outside world
EXPOSE 8080

# Define the command to run the application
# This replaces the Procfile for Docker deployments on Render
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "working_app:app"] 