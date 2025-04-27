#!/bin/bash
# Script to run the simple error demo server and test

# Configure colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[0;33m'
NC='\033[0m' # No Color

VENV_DIR="error_test_venv"

echo -e "${YELLOW}=== Resume Optimizer Error Format Test Runner ===${NC}"
echo "This script starts the error demo server and runs the error format test against it."

# Function to clean up and exit
cleanup() {
  echo -e "\n${YELLOW}Cleaning up...${NC}"
  if [ ! -z "$SERVER_PID" ]; then
    echo "Stopping server (PID: $SERVER_PID)"
    kill $SERVER_PID 2>/dev/null
    wait $SERVER_PID 2>/dev/null
  fi
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

# Check if the required scripts exist
if [ ! -f "simple_error_demo.py" ]; then
    echo -e "${RED}Error: simple_error_demo.py not found${NC}"
    exit 1
fi

if [ ! -f "simple_error_test.py" ]; then
    echo -e "${RED}Error: simple_error_test.py not found${NC}"
    exit 1
fi

# Start the server in the background
echo -e "\n${YELLOW}Starting simple error demo server...${NC}"
python simple_error_demo.py &
SERVER_PID=$!

# Give the server a moment to start up
echo "Waiting for server to start..."
sleep 3

# Check if server is running
if ! ps -p $SERVER_PID > /dev/null; then
    echo -e "${RED}Error: Server failed to start${NC}"
    cleanup 1
fi

echo -e "${GREEN}Server started with PID: $SERVER_PID${NC}"

# Run the test
echo -e "\n${YELLOW}Running error format test...${NC}"
python simple_error_test.py --url "http://localhost:5001"
TEST_RESULT=$?

# Report results
if [ $TEST_RESULT -eq 0 ]; then
    echo -e "\n${GREEN}Test completed successfully!${NC}"
else
    echo -e "\n${RED}Test failed with exit code: $TEST_RESULT${NC}"
fi

# Display log files if they exist
if [ -f "simple_error_test_result.json" ]; then
    echo -e "\n${YELLOW}Test Results:${NC}"
    cat simple_error_test_result.json
fi

# Deactivate virtual environment
deactivate

# Cleanup is handled by the trap
echo -e "\n${YELLOW}Test run complete!${NC}" 