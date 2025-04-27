#!/bin/bash

# Colors for terminal output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;36m'
NC='\033[0m' # No Color

# Default values
BASE_URL="http://localhost:8080"
TIMEOUT=10
OUTPUT_FILE="error_simulation_results.json"
SPECIFIC_SCENARIO=""

# Print banner
echo -e "${BLUE}==========================================${NC}"
echo -e "${BLUE}       Resume Optimizer Error Tests      ${NC}"
echo -e "${BLUE}==========================================${NC}"

# Parse command line arguments
while [[ $# -gt 0 ]]; do
  case $1 in
    --url=*)
      BASE_URL="${1#*=}"
      shift
      ;;
    --timeout=*)
      TIMEOUT="${1#*=}"
      shift
      ;;
    --output=*)
      OUTPUT_FILE="${1#*=}"
      shift
      ;;
    --scenario=*)
      SPECIFIC_SCENARIO="${1#*=}"
      shift
      ;;
    --help)
      echo -e "Usage: $0 [options]"
      echo -e "Options:"
      echo -e "  --url=URL          Base URL of the API to test (default: http://localhost:8080)"
      echo -e "  --timeout=SECONDS  Request timeout in seconds (default: 10)"
      echo -e "  --output=FILE      Output file for test results (default: error_simulation_results.json)"
      echo -e "  --scenario=NAME    Run only a specific test scenario"
      echo -e "  --help             Display this help message"
      exit 0
      ;;
    *)
      echo -e "${RED}Unknown option: $1${NC}"
      echo -e "Use --help for usage information"
      exit 1
      ;;
  esac
done

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Error: Python 3 is not installed or not in the PATH${NC}"
    exit 1
fi

# Check if the error_test_runner.py file exists
if [ ! -f "error_test_runner.py" ]; then
    echo -e "${RED}Error: error_test_runner.py not found in the current directory${NC}"
    exit 1
fi

# Check if required Python packages are installed
echo -e "${BLUE}Checking required Python packages...${NC}"
python3 -c "import requests" 2>/dev/null || { echo -e "${YELLOW}Installing requests package...${NC}"; pip install requests; }
python3 -c "import jsonschema" 2>/dev/null || { echo -e "${YELLOW}Installing jsonschema package...${NC}"; pip install jsonschema; }

# Check if the API is running
echo -e "${BLUE}Checking if the API is running at ${BASE_URL}...${NC}"
if curl --output /dev/null --silent --head --fail "${BASE_URL}/api/health"; then
    echo -e "${GREEN}API is running!${NC}"
else
    echo -e "${YELLOW}Warning: Could not reach the API at ${BASE_URL}.${NC}"
    read -p "Do you want to continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo -e "${RED}Aborting test run.${NC}"
        exit 1
    fi
fi

# Build the command
CMD="python3 error_test_runner.py --url=${BASE_URL} --timeout=${TIMEOUT} --output=${OUTPUT_FILE}"
if [ -n "$SPECIFIC_SCENARIO" ]; then
    CMD="${CMD} --scenario=${SPECIFIC_SCENARIO}"
    echo -e "${BLUE}Running only the '${SPECIFIC_SCENARIO}' test scenario...${NC}"
else
    echo -e "${BLUE}Running all error test scenarios...${NC}"
fi

# Run the tests
echo -e "${BLUE}Executing: ${CMD}${NC}"
eval $CMD
EXIT_CODE=$?

# Process the results
if [ $EXIT_CODE -eq 0 ]; then
    echo -e "${GREEN}All tests passed successfully!${NC}"
else
    echo -e "${YELLOW}Some tests failed. Check ${OUTPUT_FILE} for details.${NC}"
fi

echo -e "${BLUE}Results saved to: ${OUTPUT_FILE}${NC}"

# Offer to view results
read -p "Would you like to view the test results now? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    if command -v jq &> /dev/null; then
        echo -e "${BLUE}Displaying formatted results:${NC}"
        jq . "${OUTPUT_FILE}"
    else
        echo -e "${BLUE}Results:${NC}"
        cat "${OUTPUT_FILE}"
    fi
fi

exit $EXIT_CODE 