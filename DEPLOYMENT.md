# Deployment Guide

This document outlines different deployment options for the Resume Optimizer application.

## Option 1: Heroku Deployment

1. Ensure you have the [Heroku CLI](https://devcenter.heroku.com/articles/heroku-cli) installed
2. Login to Heroku:
   ```
   heroku login
   ```
3. Create a new Heroku app:
   ```
   heroku create resume-optimizer
   ```
4. Push to Heroku:
   ```
   git push heroku main
   ```
5. Configure environment variables:
   ```
   heroku config:set OPENAI_API_KEY=your_api_key
   ```

## Option 2: Docker Deployment

1. Build the Docker image:
   ```
   docker build -t resume-optimizer .
   ```
2. Run the container:
   ```
   docker run -p 8080:8080 -e OPENAI_API_KEY=your_api_key resume-optimizer
   ```

### Docker Compose (optional)

Create a `docker-compose.yml` file:
```yaml
version: '3'
services:
  app:
    build: .
    ports:
      - "8080:8080"
    environment:
      - OPENAI_API_KEY=${OPENAI_API_KEY}
```

Then run:
```
docker-compose up
```

## Option 3: AWS Elastic Beanstalk

1. Install the EB CLI:
   ```
   pip install awsebcli
   ```
2. Initialize EB:
   ```
   eb init
   ```
3. Create an environment:
   ```
   eb create resume-optimizer-env
   ```
4. Configure environment variables:
   ```
   eb setenv OPENAI_API_KEY=your_api_key
   ```
5. Deploy:
   ```
   eb deploy
   ```

## Configuration

The application requires the following environment variables:
- `OPENAI_API_KEY`: Your OpenAI API key
- `PORT`: (Optional) Port to run the server on (defaults to 8080)

## Health Check

The application provides a health check endpoint at `/api/health` that returns the current status of the application and its dependencies. 
 