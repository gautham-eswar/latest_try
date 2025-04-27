#!/bin/bash

# Run API server script with proper environment

set -e  # Exit on error

# Color settings
GREEN='\033[0;32m'
RED='\033[0;31m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Default port
PORT=${1:-8080}

echo -e "${BLUE}=== Starting Resume Optimizer API Server (Port: ${PORT}) ===${NC}"

# Check if we're in the right directory
if [ ! -f "working_app.py" ]; then
    echo -e "${RED}Error: working_app.py not found. Please run this script from the project root directory.${NC}"
    exit 1
fi

# Check if virtual environment exists and activate it
if [ -d "venv" ]; then
    echo -e "${BLUE}Activating virtual environment...${NC}"
    source venv/bin/activate
fi

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo -e "${YELLOW}Warning: .env file not found. Creating a basic one...${NC}"
    cat > .env << EOF
FLASK_ENV=development
DEBUG=true
PORT=${PORT}
PDF_GENERATION_MODE=basic
EOF
fi

# Ensure the PYTHONPATH includes the current directory
export PYTHONPATH=$PYTHONPATH:$(pwd)

# Make sure the port environment variable is set
export PORT=${PORT}

# Check dependencies
echo -e "${BLUE}Checking dependencies...${NC}"
if ! command -v pip &> /dev/null; then
    echo -e "${RED}Error: pip not found. Please install Python and pip first.${NC}"
    exit 1
fi

if [ ! -f "requirements.txt" ]; then
    echo -e "${YELLOW}Warning: requirements.txt not found. Dependencies may be missing.${NC}"
else
    echo -e "${BLUE}Installing required dependencies...${NC}"
    pip install -r requirements.txt
fi

# Ensure the templates and static directories exist
mkdir -p templates static

# Create a simple health check template if it doesn't exist
if [ ! -f "templates/status.html" ]; then
    echo -e "${BLUE}Creating basic status template...${NC}"
    cat > templates/status.html << EOF
<!DOCTYPE html>
<html>
<head>
    <title>Resume Optimizer - System Status</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 0; padding: 20px; color: #333; }
        .container { max-width: 1200px; margin: 0 auto; }
        .header { background-color: #2c3e50; color: white; padding: 15px; border-radius: 5px; }
        .status-card { background-color: #fff; border-radius: 5px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); padding: 20px; margin-bottom: 20px; }
        .status-item { margin-bottom: 10px; }
        .status-healthy { color: #27ae60; }
        .status-warning { color: #f39c12; }
        .status-error { color: #e74c3c; }
        .status-badge { display: inline-block; padding: 3px 10px; border-radius: 3px; font-size: 14px; }
        .badge-healthy { background-color: #27ae60; color: white; }
        .badge-warning { background-color: #f39c12; color: white; }
        .badge-error { background-color: #e74c3c; color: white; }
        table { width: 100%; border-collapse: collapse; }
        th, td { text-align: left; padding: 12px; }
        tr { border-bottom: 1px solid #ddd; }
        th { background-color: #f2f2f2; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Resume Optimizer System Status</h1>
            <p>Current time: {{ timestamp }}</p>
        </div>
        
        <div class="status-card">
            <h2>System Health</h2>
            <div class="status-item">
                <strong>Database:</strong> 
                {% if database_status == "healthy" %}
                    <span class="status-badge badge-healthy">Healthy</span>
                {% elif database_status == "warning" %}
                    <span class="status-badge badge-warning">Warning</span>
                {% else %}
                    <span class="status-badge badge-error">{{ database_status }}</span>
                {% endif %}
                <p>Type: {{ database_type }}</p>
            </div>
            
            <div class="status-item">
                <strong>System Metrics:</strong>
                <ul>
                    <li>CPU Usage: {{ cpu_usage }}%</li>
                    <li>Memory Usage: {{ memory_usage }}%</li>
                    <li>Uptime: {{ uptime.days }} days, {{ uptime.hours }} hours, {{ uptime.minutes }} minutes</li>
                </ul>
            </div>
        </div>
        
        <div class="status-card">
            <h2>Database Tables</h2>
            <table>
                <tr>
                    <th>Table Name</th>
                    <th>Status</th>
                    <th>Record Count</th>
                </tr>
                {% for table_name, table_info in tables.items() %}
                <tr>
                    <td>{{ table_name }}</td>
                    <td>
                        {% if table_info.status == "exists" %}
                            <span class="status-badge badge-healthy">Exists</span>
                        {% else %}
                            <span class="status-badge badge-error">Missing</span>
                        {% endif %}
                    </td>
                    <td>{{ table_info.count }}</td>
                </tr>
                {% endfor %}
            </table>
        </div>
        
        <div class="status-card">
            <h2>Recent Transactions</h2>
            <table>
                <tr>
                    <th>ID</th>
                    <th>Type</th>
                    <th>Time</th>
                    <th>Status</th>
                </tr>
                {% for tx in transactions %}
                <tr>
                    <td>{{ tx.id }}</td>
                    <td>{{ tx.type }}</td>
                    <td>{{ tx.time }}</td>
                    <td>
                        {% if tx.status == "success" %}
                            <span class="status-badge badge-healthy">Success</span>
                        {% else %}
                            <span class="status-badge badge-error">Error</span>
                        {% endif %}
                    </td>
                </tr>
                {% endfor %}
            </table>
        </div>
    </div>
</body>
</html>
EOF
fi

# Create a favicon to prevent 404 errors
if [ ! -f "static/favicon.ico" ]; then
    echo -e "${BLUE}Creating a simple favicon...${NC}"
    # Generate a 1x1 pixel favicon (minimal ICO format)
    echo -e "\x00\x00\x01\x00\x01\x00\x01\x01\x00\x00\x01\x00\x18\x00\x30\x00\x00\x00\x16\x00\x00\x00\x28\x00\x00\x00\x01\x00\x00\x00\x01\x00\x00\x00\x01\x00\x18\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00" > static/favicon.ico
fi

# Run Supabase connection check
echo -e "${BLUE}Checking Supabase connection...${NC}"
if [ -f "supabase_check.py" ]; then
    python supabase_check.py
else
    echo -e "${YELLOW}Warning: supabase_check.py not found. Skipping Supabase connection check.${NC}"
fi

# Run the server
echo -e "${GREEN}Starting server on port ${PORT}...${NC}"
python working_app.py --host 0.0.0.0 --port ${PORT} --debug

# Deactivate virtual environment on exit
if [ -d "venv" ]; then
    deactivate
fi 