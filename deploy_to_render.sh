#!/bin/bash

# Script to deploy the Resume Optimizer to Render
set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${YELLOW}=== Resume Optimizer Deployment to Render ===${NC}"

# Ensure we're in the correct directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Check if we have uncommitted changes
if [[ -n $(git status -s) ]]; then
  echo -e "${YELLOW}You have uncommitted changes. Committing them now...${NC}"
  
  # Ask for commit message
  read -p "Enter commit message [Deploy to Render]: " COMMIT_MSG
  COMMIT_MSG=${COMMIT_MSG:-"Deploy to Render"}
  
  # Add and commit changes
  git add .
  git commit -m "[Gautham] $COMMIT_MSG"
fi

# Get current branch
CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)

# Push to the remote repository
echo -e "${YELLOW}Pushing to remote repository (branch: $CURRENT_BRANCH)...${NC}"
git push origin $CURRENT_BRANCH

echo -e "${GREEN}✅ Code pushed to GitHub!${NC}"
echo -e "${YELLOW}Render will automatically deploy if auto-deploy is enabled.${NC}"
echo -e "${YELLOW}Check your Render dashboard at: https://dashboard.render.com/${NC}"

# Check for render.yaml
if [[ -f render.yaml ]]; then
  echo -e "${GREEN}✅ render.yaml found. Render should use this configuration.${NC}"
else
  echo -e "${RED}❌ No render.yaml found. Make sure to configure your service in the Render dashboard.${NC}"
fi

# Check for requirements-render.txt
if [[ -f requirements-render.txt ]]; then
  echo -e "${GREEN}✅ requirements-render.txt found.${NC}"
  echo -e "${YELLOW}Make sure your Render service is configured to use 'pip install -r requirements-render.txt' as the build command.${NC}"
else
  echo -e "${RED}❌ No requirements-render.txt found.${NC}"
fi

echo -e "${GREEN}Deployment preparation complete!${NC}"
echo -e "${YELLOW}Logs will be available in the Render dashboard once deployment starts.${NC}" 