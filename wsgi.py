"""
WSGI entry point for the Resume Optimizer application.
This file is used by Gunicorn to run the application.
"""

from working_app import create_app

# Create the Flask application
app = create_app()

if __name__ == "__main__":
    app.run() 