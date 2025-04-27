#!/bin/bash
# Script to push changes to Git and validate endpoints

set -e  # Exit on error

# Configuration
BRANCH_NAME="supabase-connection-fix"

# Color settings
GREEN='\033[0;32m'
RED='\033[0;31m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== Resume Optimizer - Git Push Script ===${NC}"

# Check if we're in the right directory
if [ ! -f "working_app.py" ]; then
    echo -e "${RED}Error: working_app.py not found. Please run this script from the project root directory.${NC}"
    exit 1
fi

# Make sure we have a clean working directory
echo -e "${BLUE}Checking git status...${NC}"
if [ -n "$(git status --porcelain)" ]; then
    echo -e "${YELLOW}⚠️  Warning: Working directory is not clean. Continuing anyway...${NC}"
fi

# Create a new branch for our changes
echo -e "${BLUE}Creating a new branch: ${BRANCH_NAME}${NC}"
git checkout -b ${BRANCH_NAME} || git checkout ${BRANCH_NAME}

# Add all changed files
echo -e "${BLUE}Adding changed files to git...${NC}"
git add .

# Commit the changes
echo -e "${BLUE}Committing changes...${NC}"
git commit -m "Fix Supabase connection and validate API endpoints" || echo -e "${YELLOW}⚠️  No changes to commit${NC}"

# Validate the API before pushing (optional)
echo -e "${BLUE}Validating API endpoints...${NC}"

# Define validation function
validate_endpoint() {
    local endpoint="$1"
    local method="${2:-GET}"
    local expected_code="${3:-200}"
    local description="$4"
    
    echo -e "${BLUE}Testing: ${description} - ${method} ${endpoint}${NC}"
    
    if [ "$method" = "GET" ]; then
        status_code=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8080${endpoint})
    else
        status_code=$(curl -s -o /dev/null -w "%{http_code}" -X ${method} http://localhost:8080${endpoint})
    fi
    
    if [ "$status_code" -eq "$expected_code" ]; then
        echo -e "${GREEN}✅ Success: ${description} (${status_code})${NC}"
        return 0
    else
        echo -e "${RED}❌ Failed: ${description} (Expected: ${expected_code}, Got: ${status_code})${NC}"
        return 1
    fi
}

# Check if the app is running
if curl -s -o /dev/null http://localhost:8080/api/health; then
    echo -e "${GREEN}✅ App is running on port 8080${NC}"
    
    # Test endpoints
    validate_endpoint "/api/health" "GET" 200 "Health Check"
    validate_endpoint "/api/test/custom-error/404" "GET" 404 "Custom Error (404)"
    validate_endpoint "/api/test/custom-error/400" "GET" 400 "Custom Error (400)"
    validate_endpoint "/api/test/custom-error/500" "GET" 500 "Custom Error (500)"
    validate_endpoint "/api/nonexistent" "GET" 404 "Non-existent Endpoint"
    
    echo -e "${BLUE}Endpoint validation complete${NC}"
else
    echo -e "${YELLOW}⚠️  App is not running on port 8080. Skipping API validation.${NC}"
    echo -e "${YELLOW}Start the app with: python3 working_app.py --port 8080${NC}"
fi

# Push the changes (if requested)
read -p "Push changes to remote repository? (y/n) " push_changes

if [ "$push_changes" = "y" ] || [ "$push_changes" = "Y" ]; then
    echo -e "${BLUE}Pushing changes to remote...${NC}"
    git push -u origin ${BRANCH_NAME}
    echo -e "${GREEN}✅ Changes successfully pushed to branch: ${BRANCH_NAME}${NC}"
else
    echo -e "${BLUE}Skipping push to remote.${NC}"
    echo -e "${BLUE}To push later, run: git push -u origin ${BRANCH_NAME}${NC}"
fi

echo -e "${GREEN}Done!${NC}" 