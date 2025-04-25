#!/bin/bash
# Deployment script for Resume Optimizer

# Show help if requested
if [ "$1" == "-h" ] || [ "$1" == "--help" ]; then
  echo "Usage: ./deploy.sh [options]"
  echo "Options:"
  echo "  --render       Deploy to Render using render CLI"
  echo "  --heroku       Deploy to Heroku using Heroku CLI"
  echo "  --docker       Build and run Docker image locally"
  echo "  --test         Run tests before deployment"
  echo "  --check        Check deployment prerequisites"
  exit 0
fi

# Check if render CLI is installed
check_render_cli() {
  if ! command -v render &> /dev/null; then
    echo "Render CLI not found. Please install it:"
    echo "npm install -g @render/cli"
    return 1
  fi
  return 0
}

# Check environment variables
check_env() {
  echo "Checking environment variables..."
  if [ -z "$OPENAI_API_KEY" ]; then
    echo "Warning: OPENAI_API_KEY is not set. You should set this in Render environment variables."
  fi
  
  if [ -z "$SUPABASE_URL" ] || [ -z "$SUPABASE_KEY" ]; then
    echo "Warning: SUPABASE credentials are not set. Using fallback in-memory database."
  fi
}

# Run tests
run_tests() {
  echo "Running tests..."
  python test_pipeline.py
  if [ $? -ne 0 ]; then
    echo "Tests failed. Fix issues before deploying."
    exit 1
  fi
}

# Deploy to Render
deploy_to_render() {
  echo "Deploying to Render..."
  
  # Check if render CLI is installed
  if ! check_render_cli; then
    echo "Please install Render CLI first."
    exit 1
  fi
  
  # Validate render.yaml
  if [ ! -f "render.yaml" ]; then
    echo "render.yaml not found. Please create it first."
    exit 1
  fi
  
  # Deploy using render CLI
  render deploy
}

# Main execution
if [ "$1" == "--check" ]; then
  check_env
elif [ "$1" == "--test" ]; then
  run_tests
elif [ "$1" == "--render" ]; then
  check_env
  deploy_to_render
elif [ "$1" == "--docker" ]; then
  docker-compose up --build
else
  echo "Please specify deployment target. Use --help for options."
  exit 1
fi

echo "Deployment script completed." 