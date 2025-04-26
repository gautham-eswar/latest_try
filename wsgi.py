"""
WSGI entry point for the Resume Optimizer application.
This file is used by Gunicorn to run the application.
"""

import os
from working_app import create_app

# Create the Flask application
app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port) 