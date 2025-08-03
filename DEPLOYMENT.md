# Deployment Instructions for TG Portal

## Overview

The TG Portal application uses a GitHub-based deployment system for improved cross-platform compatibility. This document provides instructions for deploying both the backend and frontend components.

## Backend Deployment

### Prerequisites

- Google Cloud SDK (`gcloud`) installed and configured
- GitHub repository with your code
- Personal Access Token for GitHub (if using a private repository)

### Environment Variables

Set these variables before running the deployment script:

```bash
# Required
export GITHUB_REPO="https://github.com/your-username/your-repo"
export GITHUB_BRANCH="main"  # or your preferred branch
export GITHUB_TOKEN="your_github_token"  # only needed for private repos

# Optional (will use defaults if not set)
export FIREBASE_PROJECT_ID="your-firebase-project"
export FIREBASE_PROJECT_NUMBER="your-firebase-project-number"
export TELEGRAM_API_ID="your-telegram-api-id"
export TELEGRAM_API_HASH="your-telegram-api-hash"
export GOOGLE_STUDIO_API_KEY="your-google-studio-api-key"
```

### Deployment Steps

1. Set the environment variables as needed
2. Run the deployment script:
   ```bash
   ./deploy_backend.sh
   ```
3. The script will:
   - Create or use an existing VM in Google Cloud
   - Create a Cloud SQL PostgreSQL instance
   - Set up all necessary dependencies
   - Clone your repository from GitHub
   - Configure the application using the `setup.sh` script
   - Start the application with Supervisor
   - Configure Nginx as a reverse proxy

### Cloud SQL PostgreSQL

The deployment script now creates and configures a Cloud SQL PostgreSQL instance instead of using a local PostgreSQL installation. This provides several benefits:

- Improved reliability and availability
- Automated backups and maintenance
- Better security and access control
- Scalability for growing workloads

The PostgreSQL connection details are automatically configured in the application's environment variables.

## Frontend Deployment

After deploying the backend, run the frontend deployment script:

```bash
./deploy_frontend.sh
```

## Troubleshooting

If the deployment fails:

1. Check the error messages in the terminal
2. View server logs:
   ```bash
   gcloud compute ssh tgportal-backend --zone=us-central1-a --command="sudo tail -f /var/log/tgportal/tgportal.err.log"
   ```
3. Check application logs:
   ```bash
   gcloud compute ssh tgportal-backend --zone=us-central1-a --command="sudo tail -f /var/log/tgportal/tgportal.out.log"
   ```

## Redeployment

To redeploy the application after making changes:

1. Push your changes to GitHub
2. Run the deployment script again
   ```bash
   ./deploy_backend.sh
   ```
