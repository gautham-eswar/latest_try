#!/bin/bash

# This script sets up the local environment for testing the Resume Optimizer

# Create a virtual environment if it doesn't exist
if [ ! -d "render-test-env" ]; then
    echo "Creating virtual environment..."
    python3 -m venv render-test-env
fi

# Activate the virtual environment
source render-test-env/bin/activate

# Install requirements for Render deployment
echo "Installing requirements from requirements-render.txt..."
pip install -r requirements-render.txt

# Set environment variables for testing
export OPENAI_API_KEY="your-api-key-here"
export PORT=8085
export FLASK_ENV=development
export RENDER=true  # Simulate running on Render

# Run the application
echo "Starting application on port $PORT..."
python wsgi.py

# Note: The server will continue running after this script completes
# Press Ctrl+C to stop the server 