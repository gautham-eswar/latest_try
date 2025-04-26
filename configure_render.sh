#!/bin/bash
# Script to configure Render with environment variables from .env.render

# Color settings
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}Configuring Render environment variables${NC}"
echo "This script will help you set up environment variables in Render's dashboard"

# Check if render CLI is installed
if ! command -v render &> /dev/null; then
    echo -e "${YELLOW}Note: Render CLI is not installed.${NC}"
    echo "You will need to set these variables manually in the Render dashboard."
    MANUAL_MODE=true
else 
    MANUAL_MODE=false
    echo -e "${GREEN}Render CLI detected.${NC}"
    echo "Would you like to set variables via CLI or manually in dashboard?"
    read -p "Use CLI? (y/n): " USE_CLI
    if [[ $USE_CLI != "y" && $USE_CLI != "Y" ]]; then
        MANUAL_MODE=true
    fi
fi

# Find the .env.render file
ENV_FILE=".env.render"
if [ ! -f "$ENV_FILE" ]; then
    echo -e "${RED}Error: $ENV_FILE not found!${NC}"
    exit 1
fi

# Parse variables from .env.render
echo -e "${GREEN}Reading environment variables from $ENV_FILE${NC}"
VARS=()
SECURED=()

while IFS= read -r line; do
    # Skip comments and empty lines
    if [[ $line =~ ^#.* || -z $line ]]; then
        continue
    fi
    
    VAR_NAME=$(echo "$line" | cut -d'=' -f1)
    VAR_VALUE=$(echo "$line" | cut -d'=' -f2-)
    
    # Check if variable should be secured (contains sensitive info)
    if [[ $VAR_NAME == *"KEY"* || $VAR_NAME == *"SECRET"* || $VAR_NAME == *"PASSWORD"* ]]; then
        SECURED+=("$VAR_NAME")
    fi
    
    VARS+=("$VAR_NAME=$VAR_VALUE")
done < "$ENV_FILE"

if [ "$MANUAL_MODE" = true ]; then
    # Display variables for manual setup
    echo -e "\n${GREEN}Please add the following environment variables in Render dashboard:${NC}"
    echo -e "${YELLOW}https://dashboard.render.com/web/srv-xxx/env${NC}"
    echo -e "-------------------------------------------------------"
    
    for var in "${VARS[@]}"; do
        VAR_NAME=$(echo "$var" | cut -d'=' -f1)
        VAR_VALUE=$(echo "$var" | cut -d'=' -f2-)
        
        if [[ " ${SECURED[@]} " =~ " ${VAR_NAME} " ]]; then
            # Show sensitive vars partially masked
            MASKED_VALUE="${VAR_VALUE:0:4}...${VAR_VALUE: -4}"
            echo -e "${YELLOW}$VAR_NAME=${NC}$MASKED_VALUE ${RED}(SENSITIVE)${NC}"
        else
            echo -e "${YELLOW}$VAR_NAME=${NC}$VAR_VALUE"
        fi
    done
    
    echo -e "-------------------------------------------------------"
    echo -e "${GREEN}Remember to click 'Save Changes' after adding all variables.${NC}"
else
    # Use Render CLI to set variables
    echo -e "\n${GREEN}Setting environment variables using Render CLI${NC}"
    echo -e "Please enter your Render service ID:"
    read -p "Service ID (e.g., srv-xxxx): " SERVICE_ID
    
    for var in "${VARS[@]}"; do
        VAR_NAME=$(echo "$var" | cut -d'=' -f1)
        VAR_VALUE=$(echo "$var" | cut -d'=' -f2-)
        
        if [[ " ${SECURED[@]} " =~ " ${VAR_NAME} " ]]; then
            echo -e "Setting ${YELLOW}$VAR_NAME${NC} (sensitive value)"
        else
            echo -e "Setting ${YELLOW}$VAR_NAME${NC}=$VAR_VALUE"
        fi
        
        render env set --service "$SERVICE_ID" "$VAR_NAME=$VAR_VALUE"
    done
    
    echo -e "\n${GREEN}Environment variables set successfully!${NC}"
    echo "Your service will automatically redeploy with the new environment variables."
fi

echo -e "\n${GREEN}Configuration complete!${NC}" 