#!/bin/bash
# filepath: /Users/mazibuckler/apps/tgportal/deploy_backend.sh
# This script deploys the TG Portal backend to a GCP Compute Engine instance
# Uses GitHub-based deployment for improved cross-platform compatibility
# It is designed to be idempotent (can be run multiple times safely)

set -e  # Exit on any error

# Colors for terminal output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Configuration variables - edit these as needed
PROJECT_ID=${FIREBASE_PROJECT_ID:-"gen-lang-client-0560055117"}
INSTANCE_NAME="tgportal-backend"
ZONE="us-central1-a"
MACHINE_TYPE="e2-medium"
VM_USERNAME="$USER"
APP_DIR="/home/$VM_USERNAME/tgportal"

# Cloud SQL PostgreSQL configuration
DB_INSTANCE_NAME="tgportal-db"
DB_TIER="db-g1-small"  # Smallest general-purpose instance
DB_USERNAME="tgportal"
DB_PASSWORD="tgportal-$(date +%s | head -c 8)" # Generate a simple unique password
DB_DATABASE="tgportal"
DB_REGION=$(echo "$ZONE" | sed 's/-.$//')  # Extract region from zone (e.g., us-central1-a -> us-central1)

REDIS_HOST=${REDIS_HOST:-"localhost"}
REDIS_PORT=${REDIS_PORT:-6379}
REDIS_PASSWORD=${REDIS_PASSWORD:-""}
REDIS_DB=${REDIS_DB:-0}

# GitHub configuration - update these with your repository details
GITHUB_REPO=${GITHUB_REPO:-"https://github.com/mitar-death/portal"}
GITHUB_BRANCH=${GITHUB_BRANCH:-"stable-without-redis"}
GITHUB_TOKEN=${GITHUB_TOKEN:-"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"}
TELEGRAM_SESSION_FOLDER_DIR="/storage/sessions/main_user"
TELEGRAM_SESSION_NAME=$"user_session"

# Load environment variables from .env file if it exists
if [ -f ".env" ]; then
  # Create a temporary file for sourcing
  ENV_TEMP=$(mktemp)
  echo "#!/bin/bash" > "$ENV_TEMP"
  
  # Parse .env file and export variables
  grep -v '^#' .env | grep -v '^$' | sed -e 's/\r$//' | \
  sed -e 's/^[[:space:]]*//g' | sed -e 's/[[:space:]]*=[[:space:]]*/=/g' | \
  while IFS= read -r line; do
    # Skip lines that don't contain an equals sign
    if [[ "$line" == *"="* ]]; then
      var_name=$(echo "$line" | cut -d '=' -f 1 | tr -d '[:space:]')
      var_value=$(echo "$line" | cut -d '=' -f 2-)
      echo "export $var_name=\"$var_value\"" >> "$ENV_TEMP"
    fi
  done
  
  source "$ENV_TEMP"
  rm "$ENV_TEMP"
  echo -e "${GREEN}Loaded environment variables from .env file${NC}"
fi

# Get env vars
PUSHER_APP_ID=$PUSHER_APP_ID
PUSHER_APP_KEY=$PUSHER_APP_KEY
PUSHER_APP_SECRET=$PUSHER_APP_SECRET
PUSHER_APP_CLUSTER=$PUSHER_APP_CLUSTER
PUSHER_USE_TLS=${PUSHER_USE_TLS:-"true"}

# Get custom domain from environment or prompt user
CUSTOM_DOMAIN=${CUSTOM_DOMAIN:-""}
if [ -z "$CUSTOM_DOMAIN" ]; then
  read -p "Enter custom domain (leave empty to use IP address only): " CUSTOM_DOMAIN
fi

# Set USE_HTTPS based on whether a domain is provided
USE_HTTPS=false
if [ -n "$CUSTOM_DOMAIN" ]; then
  USE_HTTPS=true
  echo -e "${GREEN}Custom domain set to: $CUSTOM_DOMAIN${NC}"
  echo -e "${GREEN}HTTPS will be enabled${NC}"
else
  echo -e "${YELLOW}No custom domain provided. Will use IP address only with HTTP.${NC}"
fi

# Check if gcloud is installed
if ! command -v gcloud &> /dev/null; then
  echo -e "${RED}Google Cloud SDK (gcloud) is not installed. Please install it first:${NC}"
  echo "https://cloud.google.com/sdk/docs/install"
  exit 1
fi

# Set the GCP project
echo -e "${YELLOW}Setting GCP project to: $PROJECT_ID${NC}"
gcloud config set project "$PROJECT_ID"

# Check if the instance exists
if gcloud compute instances describe "$INSTANCE_NAME" --zone="$ZONE" &> /dev/null; then
  echo -e "${GREEN}Instance $INSTANCE_NAME already exists.${NC}"
else
  echo -e "${YELLOW}Creating new VM instance: $INSTANCE_NAME${NC}"
  
  # Create the VM instance
  gcloud compute instances create "$INSTANCE_NAME" \
    --zone="$ZONE" \
    --machine-type="$MACHINE_TYPE" \
    --image-family=debian-12 \
    --image-project=debian-cloud \
    --boot-disk-size=200GB \
    --tags=http-server,https-server

  echo -e "${GREEN}Instance created successfully.${NC}"

  # Wait for startup script to complete
  echo -e "${YELLOW}Waiting for VM startup script to complete...${NC}"
  sleep 60
fi

# Create firewall rules if they don't exist
if ! gcloud compute firewall-rules describe allow-http &> /dev/null; then
  echo -e "${YELLOW}Creating firewall rule for HTTP traffic${NC}"
  gcloud compute firewall-rules create allow-http \
    --allow tcp:80 \
    --target-tags=http-server
fi

if ! gcloud compute firewall-rules describe allow-https &> /dev/null; then
  echo -e "${YELLOW}Creating firewall rule for HTTPS traffic${NC}"
  gcloud compute firewall-rules create allow-https \
    --allow tcp:443 \
    --target-tags=https-server
fi

# Get the external IP of the instance
EXTERNAL_IP=$(gcloud compute instances describe "$INSTANCE_NAME" --zone="$ZONE" --format='get(networkInterfaces[0].accessConfigs[0].natIP)')
echo -e "${GREEN}Instance external IP: $EXTERNAL_IP${NC}"

# Check if Cloud SQL instance exists
echo -e "${YELLOW}Checking for Cloud SQL PostgreSQL instance...${NC}"

MAX_SQL_RETRIES=5
SQL_RETRY_COUNT=0

check_sql_instance() {
  if gcloud sql instances describe "$DB_INSTANCE_NAME" &> /dev/null; then
    return 0  # Success
  else
    return 1  # Not found
  fi
}

if check_sql_instance; then
  echo -e "${GREEN}Cloud SQL instance $DB_INSTANCE_NAME already exists.${NC}"
  
  # Get the instance connection name and IP
  DB_CONNECTION_NAME=$(gcloud sql instances describe "$DB_INSTANCE_NAME" --format="value(connectionName)")
  DB_HOST=$(gcloud sql instances describe "$DB_INSTANCE_NAME" --format="value(ipAddresses[0].ipAddress)")
  
  echo -e "${GREEN}Using existing database at $DB_HOST${NC}"
else
  echo -e "${YELLOW}Creating Cloud SQL PostgreSQL instance: $DB_INSTANCE_NAME${NC}"
  
  # Create the Cloud SQL instance
  gcloud sql instances create "$DB_INSTANCE_NAME" \
    --tier="$DB_TIER" \
    --region="$DB_REGION" \
    --database-version=POSTGRES_13 \
    --storage-size=10GB \
    --storage-type=SSD \
    --backup-start-time="23:00" \
    --availability-type=ZONAL \
    --root-password="$DB_PASSWORD" \
    --authorized-networks="0.0.0.0/0"
  
  # Wait for the instance to be fully provisioned with retries
  echo -e "${YELLOW}Waiting for Cloud SQL instance to be ready...${NC}"
  while [ $SQL_RETRY_COUNT -lt $MAX_SQL_RETRIES ]; do
    if check_sql_instance && \
       DB_CONNECTION_NAME=$(gcloud sql instances describe "$DB_INSTANCE_NAME" --format="value(connectionName)" 2>/dev/null) && \
       DB_HOST=$(gcloud sql instances describe "$DB_INSTANCE_NAME" --format="value(ipAddresses[0].ipAddress)" 2>/dev/null) && \
       [ -n "$DB_CONNECTION_NAME" ] && [ -n "$DB_HOST" ]; then
      echo -e "${GREEN}Cloud SQL instance is ready.${NC}"
      break
    else
      SQL_RETRY_COUNT=$((SQL_RETRY_COUNT+1))
      if [ $SQL_RETRY_COUNT -eq $MAX_SQL_RETRIES ]; then
        echo -e "${RED}Failed to create Cloud SQL instance after $MAX_SQL_RETRIES attempts.${NC}"
        echo -e "${RED}You may need to manually check the instance in the Google Cloud Console.${NC}"
        echo -e "${RED}Continuing with deployment, but database connection may fail.${NC}"
      else
        echo -e "${YELLOW}Cloud SQL instance not ready yet. Waiting 30 seconds (Attempt $SQL_RETRY_COUNT of $MAX_SQL_RETRIES)...${NC}"
        sleep 30
      fi
    fi
  done
  
  echo -e "${GREEN}Created Cloud SQL instance with IP: $DB_HOST${NC}"
  
  # Create database and user with retries
  echo -e "${YELLOW}Creating database and user...${NC}"
  MAX_DB_RETRIES=3
  DB_RETRY_COUNT=0
  
  while [ $DB_RETRY_COUNT -lt $MAX_DB_RETRIES ]; do
    if gcloud sql databases create "$DB_DATABASE" --instance="$DB_INSTANCE_NAME" 2>/dev/null; then
      echo -e "${GREEN}Database created successfully.${NC}"
      break
    else
      DB_RETRY_COUNT=$((DB_RETRY_COUNT+1))
      if [ $DB_RETRY_COUNT -eq $MAX_DB_RETRIES ]; then
        echo -e "${RED}Failed to create database after $MAX_DB_RETRIES attempts.${NC}"
      else
        echo -e "${YELLOW}Failed to create database. Retrying in 10 seconds...${NC}"
        sleep 10
      fi
    fi
  done
  
  # Create database user with retries
  MAX_USER_RETRIES=3
  USER_RETRY_COUNT=0
  
  while [ $USER_RETRY_COUNT -lt $MAX_USER_RETRIES ]; do
    if gcloud sql users create "$DB_USERNAME" --instance="$DB_INSTANCE_NAME" --password="$DB_PASSWORD" 2>/dev/null; then
      echo -e "${GREEN}Database user created successfully.${NC}"
      break
    else
      USER_RETRY_COUNT=$((USER_RETRY_COUNT+1))
      if [ $USER_RETRY_COUNT -eq $MAX_USER_RETRIES ]; then
        echo -e "${RED}Failed to create database user after $MAX_USER_RETRIES attempts.${NC}"
      else
        echo -e "${YELLOW}Failed to create database user. Retrying in 10 seconds...${NC}"
        sleep 10
      fi
    fi
  done
fi

# Check if SSH connection to the VM works
echo -e "${YELLOW}Checking SSH connection to the VM...${NC}"
MAX_RETRIES=5
RETRY_COUNT=0

while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
  if gcloud compute ssh "$INSTANCE_NAME" --zone="$ZONE" --command="echo SSH connection successful" --quiet; then
    echo -e "${GREEN}SSH connection established.${NC}"
    break
  else
    RETRY_COUNT=$((RETRY_COUNT+1))
    if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
      echo -e "${RED}Failed to establish SSH connection after $MAX_RETRIES attempts.${NC}"
      echo -e "${YELLOW}Attempting to set up SSH keys manually...${NC}"
      gcloud compute config-ssh --force
      sleep 10
      if ! gcloud compute ssh "$INSTANCE_NAME" --zone="$ZONE" --command="echo SSH connection successful" --quiet; then
        echo -e "${RED}Failed to establish SSH connection. Please check your GCP setup and try again.${NC}"
        exit 1
      fi
    else
      echo -e "${YELLOW}SSH connection failed. Retrying in 10 seconds (Attempt $RETRY_COUNT of $MAX_RETRIES)...${NC}"
      gcloud compute config-ssh --force
      sleep 10
    fi
  fi
done

# Prepare the deployment files
echo -e "${YELLOW}Preparing deployment files...${NC}"
TEMP_DIR=$(mktemp -d)

# Create a temporary config directory to hold the configuration files
mkdir -p "$TEMP_DIR/config"

# Create production environment file
cat > "$TEMP_DIR/config/.env.prod" << EOL
# Telegram API credentials
TELEGRAM_API_ID=${TELEGRAM_API_ID:-"your_telegram_api_id"}
TELEGRAM_API_HASH=${TELEGRAM_API_HASH:-"your_telegram_api_hash"}
TELEGRAM_SESSION_NAME=${TELEGRAM_SESSION_NAME:-"user_session"}
TELEGRAM_SESSION_FOLDER_DIR=${TELEGRAM_SESSION_FOLDER_DIR:-"storage/sessions"}

ENV=production
# Database settings - Cloud SQL PostgreSQL
DB_TYPE=postgres
DB_PORT=5432
DB_USERNAME=$DB_USERNAME
DB_PASSWORD=$DB_PASSWORD
DB_HOST=$DB_HOST
DB_DATABASE=$DB_DATABASE

REDIS_HOST=$REDIS_HOST
REDIS_PORT=$REDIS_PORT
REDIS_DB=$REDIS_DB
REDIS_PASSWORD=$REDIS_PASSWORD

# Pusher config
PUSHER_APP_CLUSTER=$PUSHER_APP_CLUSTER
PUSHER_APP_ID=$PUSHER_APP_ID
PUSHER_APP_KEY=$PUSHER_APP_KEY
PUSHER_APP_SECRET=$PUSHER_APP_SECRET
PUSHER_USE_TLS=$PUSHER_USE_TLS

# Cloud SQL connection name (for socket connections if needed)
CLOUD_SQL_CONNECTION_NAME=$DB_CONNECTION_NAME

# FastAPI settings
DEBUG=false
HOST=0.0.0.0
PORT=8000

# Custom domain configuration
CUSTOM_DOMAIN=$CUSTOM_DOMAIN
USE_HTTPS=$USE_HTTPS

# AI model settings
GOOGLE_STUDIO_API_KEY=${GOOGLE_STUDIO_API_KEY:-"your_google_studio_api_key"}
EOL

# Create GitHub deployment script
cat > "$TEMP_DIR/github_setup.sh" << EOL
#!/bin/bash
set -e  # Exit on any error

# Define colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Define variables
EXTERNAL_IP=\$(curl -s http://checkip.amazonaws.com)
APP_DIR="$APP_DIR"
VM_USERNAME="$VM_USERNAME"
CUSTOM_DOMAIN="$CUSTOM_DOMAIN"
USE_HTTPS="$USE_HTTPS"

# Install packages
echo -e "\${YELLOW}Installing essential packages...\${NC}"
sudo apt-get update -y
sudo apt-get install -y python3-pip python3-venv git supervisor nginx certbot python3-certbot-nginx curl wget build-essential zlib1g-dev libncurses5-dev libgdbm-dev libnss3-dev libssl-dev libsqlite3-dev libreadline-dev libffi-dev libbz2-dev postgresql-client dnsutils netcat-openbsd  redis-server

# Clone the repository
echo -e "\${GREEN}Cloning repository from GitHub...\${NC}"
GITHUB_REPO="\${GITHUB_REPO}"
BRANCH="\${GITHUB_BRANCH}"
GITHUB_TOKEN="\${GITHUB_TOKEN}"

# Format repo URL with token if provided
if [ -n "\$GITHUB_TOKEN" ]; then
  # Extract the repository part after github.com/
  REPO_PART=\$(echo "\$GITHUB_REPO" | sed -e 's|https://github.com/||')
  
  # Make sure to remove any trailing slashes
  REPO_PART=\$(echo "\$REPO_PART" | sed -e 's|/$||')
  
  # Create the URL with the token properly
  GITHUB_URL="https://\${GITHUB_TOKEN}@github.com/\${REPO_PART}"
  
  echo -e "\${GREEN}Using authenticated GitHub URL\${NC}"
else
  GITHUB_URL="\$GITHUB_REPO"
  echo -e "\${GREEN}Using public GitHub URL\${NC}"
fi

# Clean up any previous deployment
rm -rf /tmp/tgportal_deploy
mkdir -p /tmp/tgportal_deploy

# Create a temporary directory for configuration files
mkdir -p /tmp/config

# Copy environment file from parent script if it exists
if [ -f /home/\$VM_USERNAME/.env.prod ]; then
  cp /home/\$VM_USERNAME/.env.prod /tmp/config/.env.prod
fi

# Clone the repository
echo -e "\${GREEN}Cloning from branch: \$BRANCH\${NC}"
git clone --depth 1 --branch "\$BRANCH" "\$GITHUB_URL" /tmp/tgportal_deploy

if [ ! -d "/tmp/tgportal_deploy/.git" ]; then
  echo -e "\${RED}Failed to clone repository. Check your GitHub token and repository URL.\${NC}"
  exit 1
fi

# Export variables for setup script
export EXTERNAL_IP="\$EXTERNAL_IP"
export APP_DIR="\$APP_DIR"
export VM_USERNAME="\$VM_USERNAME"
export CLOUD_SQL_CONNECTION_NAME="\$CLOUD_SQL_CONNECTION_NAME"
export DB_HOST="\$DB_HOST"
export DB_USERNAME="\$DB_USERNAME"
export DB_PASSWORD="\$DB_PASSWORD"
export DB_DATABASE="\$DB_DATABASE"
export CUSTOM_DOMAIN="\$CUSTOM_DOMAIN"
export USE_HTTPS="\$USE_HTTPS"
export DOMAIN_SSL_CERTIFICATE="\$DOMAIN_SSL_CERTIFICATE"
export DOMAIN_SSL_PRIVATE_KEY="\$DOMAIN_SSL_PRIVATE_KEY"
export REDIS_HOST="\$REDIS_HOST"
export REDIS_PORT="\$REDIS_PORT"
export REDIS_DB="\$REDIS_DB"
export REDIS_PASSWORD="\$REDIS_PASSWORD"
export PUSHER_APP_ID="\$PUSHER_APP_ID"
export PUSHER_APP_KEY="\$PUSHER_APP_KEY"
export PUSHER_APP_SECRET="\$PUSHER_APP_SECRET"
export PUSHER_APP_CLUSTER="\$PUSHER_APP_CLUSTER"
export PUSHER_USE_TLS="\$PUSHER_USE_TLS"

# Run the setup script in the background to avoid hanging SSH session
cd /tmp/tgportal_deploy
echo -e "\${GREEN}Running setup script in the background...\${NC}"

bash setup.sh
EOL
chmod +x "$TEMP_DIR/github_setup.sh"

# Copy the GitHub setup script
if ! gcloud compute scp "$TEMP_DIR/github_setup.sh" "$INSTANCE_NAME:~/github_setup.sh" --zone="$ZONE"; then
  echo -e "${RED}Failed to copy setup script to VM. Aborting.${NC}"
  exit 1
fi

# Copy the environment file to the VM
echo -e "${YELLOW}Copying environment file to VM...${NC}"
if ! gcloud compute scp "$TEMP_DIR/config/.env.prod" "$INSTANCE_NAME:~/.env.prod" --zone="$ZONE"; then
  echo -e "${RED}Failed to copy environment file to VM. Continuing anyway...${NC}"
fi


# Run the GitHub deployment script
echo -e "${YELLOW}Setting up the application on the VM using GitHub...${NC}"
echo -e "${YELLOW}This may take several minutes. Please be patient.${NC}"

# Run the GitHub deployment script with proper environment variables
gcloud compute ssh "$INSTANCE_NAME" --zone="$ZONE" --command="
export GITHUB_REPO='$GITHUB_REPO'
export GITHUB_BRANCH='$GITHUB_BRANCH'
export GITHUB_TOKEN='$GITHUB_TOKEN'
export EXTERNAL_IP='$EXTERNAL_IP'
export CLOUD_SQL_CONNECTION_NAME='$DB_CONNECTION_NAME'
export DB_HOST='$DB_HOST'
export DB_USERNAME='$DB_USERNAME'
export DB_PASSWORD='$DB_PASSWORD'
export DB_DATABASE='$DB_DATABASE'
export CUSTOM_DOMAIN='$CUSTOM_DOMAIN'
export USE_HTTPS='$USE_HTTPS'
export DOMAIN_SSL_CERTIFICATE='$DOMAIN_SSL_CERTIFICATE'
export DOMAIN_SSL_PRIVATE_KEY='$DOMAIN_SSL_PRIVATE_KEY'
export REDIS_HOST='$REDIS_HOST'
export REDIS_PORT='$REDIS_PORT'
export REDIS_DB='$REDIS_DB'
export REDIS_PASSWORD='$REDIS_PASSWORD'
export PUSHER_APP_ID='$PUSHER_APP_ID'
export PUSHER_APP_KEY='$PUSHER_APP_KEY'
export PUSHER_APP_SECRET='$PUSHER_APP_SECRET'
export PUSHER_APP_CLUSTER='$PUSHER_APP_CLUSTER'
export PUSHER_USE_TLS='$PUSHER_USE_TLS'
bash ~/github_setup.sh
" || {
  echo -e "${RED}Deployment failed. Please check the logs for more information.${NC}"
  exit 1
}

# Clean up temporary files
echo -e "${YELLOW}Cleaning up local temporary files...${NC}"
rm -rf "$TEMP_DIR"

sleep 10

# Verify application is running
echo -e "${YELLOW}Verifying application status...${NC}"
APP_STATUS=$(gcloud compute ssh "$INSTANCE_NAME" --zone="$ZONE" --command="sudo supervisorctl status tgportal" 2>/dev/null || echo "FAILED")

if [[ "$APP_STATUS" == *"RUNNING"* ]]; then
  echo -e "${GREEN}✓ TG Portal backend is running successfully!${NC}"
  echo -e "${GREEN}✓ Application is accessible at: http://$EXTERNAL_IP${NC}"
  

else
  echo -e "${RED}⚠ TG Portal backend might not be running correctly. Status: $APP_STATUS${NC}"
  echo -e "${YELLOW}Checking supervisor logs...${NC}"
  gcloud compute ssh "$INSTANCE_NAME" --zone="$ZONE" --command="sudo cat /var/log/tgportal/tgportal.err.log | tail -n 20"
fi



echo -e "${GREEN}==================================================================${NC}"
echo -e "${GREEN}Deployment Summary:${NC}"
echo -e "${GREEN}==================================================================${NC}"
if [ -n "$CUSTOM_DOMAIN" ] && [ "$USE_HTTPS" = "true" ]; then
  echo -e "${YELLOW}Backend URL:${NC} https://$CUSTOM_DOMAIN"
else
  echo -e "${YELLOW}Backend URL:${NC} http://$EXTERNAL_IP"
fi
echo -e "${YELLOW}VM Instance:${NC} $INSTANCE_NAME (Zone: $ZONE)"
echo -e "${YELLOW}GitHub Repository:${NC} $GITHUB_REPO"
echo -e "${YELLOW}GitHub Branch:${NC} $GITHUB_BRANCH"
if [ -n "$CUSTOM_DOMAIN" ]; then
  echo -e "${YELLOW}Custom Domain:${NC} $CUSTOM_DOMAIN (HTTPS: $USE_HTTPS)"
fi
echo -e "${YELLOW}==================================================================${NC}"
echo -e "${GREEN}Next steps:${NC}"
echo -e "1. Update your Firebase configuration to allow requests from this domain"
if [ -n "$CUSTOM_DOMAIN" ]; then
  echo -e "2. Ensure your DNS is properly configured to point $CUSTOM_DOMAIN to $EXTERNAL_IP"
else
  echo -e "2. If you have a domain name, configure it to point to $EXTERNAL_IP"
fi
echo -e "3. Run './deploy_frontend.sh' to deploy your frontend to Firebase"
echo -e "4. Monitor your application logs with: gcloud compute ssh $INSTANCE_NAME --zone=$ZONE --command=\"sudo tail -f /var/log/tgportal/tgportal.out.log\""
echo -e "${YELLOW}==================================================================${NC}"
