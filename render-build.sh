#!/usr/bin/env bash
# This script runs during the build process on Render.com

# Exit on error
set -o errexit

# Install LaTeX (minimal texlive distribution with necessary packages)
echo "Cleaning apt cache and updating package lists..."
apt-get clean
apt-get update -o Acquire::BrokenProxy="true" -o Acquire::http::Fix-Broken-Cookies="true"

echo "Installing LaTeX packages..."
apt-get install -y --no-install-recommends \
    texlive-base \
    texlive-latex-base \
    texlive-fonts-recommended \
    texlive-latex-recommended \
    texlive-latex-extra

# Install pip packages
echo "Installing Python dependencies..."
pip install -r requirements.txt

# Print some debug info
echo "LaTeX installation completed. Checking pdflatex version:"
pdflatex --version

echo "Build script completed successfully!" 