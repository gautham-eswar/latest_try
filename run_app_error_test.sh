#!/bin/bash
# Script to run the application error format tests

# Configure colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[0;33m'
NC='\033[0m' # No Color

VENV_DIR="error_test_venv"

echo -e "${YELLOW}=== Resume Optimizer App Error Format Test Runner ===${NC}"
echo "This script tests the error format of the Resume Optimizer application."

# Function to clean up and exit
cleanup() {
  echo -e "\n${YELLOW}Cleaning up...${NC}"
  echo -e "${GREEN}Done!${NC}"
  exit ${1:-0}
}

# Set up trap to handle script interruption
trap 'cleanup' INT TERM EXIT

# Check if Python 3 is installed
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Error: Python 3 is required but not installed.${NC}"
    exit 1
fi

# Create and activate virtual environment
if [ ! -d "$VENV_DIR" ]; then
    echo -e "\n${YELLOW}Creating virtual environment in $VENV_DIR${NC}"
    python3 -m venv $VENV_DIR
    if [ $? -ne 0 ]; then
        echo -e "${RED}Failed to create virtual environment${NC}"
        exit 1
    fi
    echo -e "${GREEN}Virtual environment created${NC}"
else
    echo -e "\n${YELLOW}Using existing virtual environment in $VENV_DIR${NC}"
fi

# Activate virtual environment
echo -e "${YELLOW}Activating virtual environment${NC}"
source $VENV_DIR/bin/activate
if [ $? -ne 0 ]; then
    echo -e "${RED}Failed to activate virtual environment${NC}"
    exit 1
fi

# Install dependencies in the virtual environment
echo -e "\n${YELLOW}Installing dependencies in virtual environment...${NC}"
pip install -q flask requests jsonschema
if [ $? -ne 0 ]; then
    echo -e "${RED}Failed to install dependencies${NC}"
    exit 1
fi
echo -e "${GREEN}Dependencies installed successfully${NC}"

# Check if the application server is running
echo -e "\n${YELLOW}Checking if application server is running...${NC}"
curl -s http://localhost:8080/api/health > /dev/null
if [ $? -ne 0 ]; then
    echo -e "${YELLOW}Application server doesn't seem to be running.${NC}"
    
    # Ask user if they want to continue with a different URL
    read -p "Do you want to specify a different URL? (y/n) " choice
    case "$choice" in 
      y|Y ) 
        read -p "Enter server URL (e.g., http://localhost:5000): " server_url
        ;;
      * ) 
        echo -e "${YELLOW}Using default URL of http://localhost:8080${NC}"
        server_url="http://localhost:8080"
        ;;
    esac
else
    echo -e "${GREEN}Application server is running at http://localhost:8080${NC}"
    server_url="http://localhost:8080"
fi

# Run the test
echo -e "\n${YELLOW}Running app error format tests...${NC}"
python app_error_test.py --url "$server_url"
TEST_RESULT=$?

# Report results
if [ $TEST_RESULT -eq 0 ]; then
    echo -e "\n${GREEN}Tests completed successfully!${NC}"
else
    echo -e "\n${RED}Some tests failed with exit code: $TEST_RESULT${NC}"
fi

# Display log files if they exist
if [ -f "app_error_test_results.json" ]; then
    echo -e "\n${YELLOW}Test Results JSON:${NC}"
    cat app_error_test_results.json
fi

# Deactivate virtual environment
deactivate

# Cleanup is handled by the trap
echo -e "\n${YELLOW}Test run complete!${NC}" 