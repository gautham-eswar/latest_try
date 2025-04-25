#!/bin/bash
# Script to push all changes to Git

# Check if Git is installed
if ! command -v git &> /dev/null; then
    echo "Git is not installed. Please install Git first."
    exit 1
fi

# Add all files
echo "Adding all files to Git..."
git add .

# Commit changes
echo "Committing changes..."
git commit -m "Prepare for Render deployment"

# Check if there's a remote repository
if ! git remote | grep -q "origin"; then
    echo "No remote repository found. Please add one with:"
    echo "git remote add origin <your-git-repo-url>"
    exit 1
fi

# Push to the repository
echo "Pushing to remote repository..."
git push

echo "Done! Your code has been pushed to Git." 