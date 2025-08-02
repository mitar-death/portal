#!/bin/bash
# filepath: /Users/mazibuckler/apps/tgportal/deploy_backend.sh
# This script deploys the TG Portal backend to a GCP Compute Engine instance
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

# Load environment variables from .env file if it exists
if [ -f ".env" ]; then
  # Create a temporary file for sourcing
  ENV_TEMP=$(mktemp)
  echo "#!/bin/bash" > "$ENV_TEMP"
  
  # Parse .env file with better error handling, fixing common issues
  grep -v '^#' .env | grep -v '^$' | sed -e 's/\r$//' | sed -e 's/^[[:space:]]*//g' | sed -e 's/[[:space:]]*=[[:space:]]*/=/g' | while IFS= read -r line; do
    # Skip lines that don't contain an equals sign
    if [[ "$line" != *"="* ]]; then
      continue
    fi
    
    # Extract variable name and value
    var_name=$(echo "$line" | cut -d '=' -f 1)
    var_value=$(echo "$line" | cut -d '=' -f 2-)
    
    # Clean up the variable name and value
    var_name=$(echo "$var_name" | tr -d '[:space:]')
    
    # Export the variable
    echo "export $var_name=\"$var_value\"" >> "$ENV_TEMP"
  done
  
  source "$ENV_TEMP"
  rm "$ENV_TEMP"
  echo -e "${GREEN}Loaded environment variables from .env file${NC}"
fi

# Check if gcloud is installed
if ! command -v gcloud &> /dev/null; then
  echo -e "${RED}Google Cloud SDK (gcloud) is not installed. Please install it first:${NC}"
  echo "https://cloud.google.com/sdk/docs/install"
  exit 1
fi

# Check if gcloud is authenticated
# echo -e "${YELLOW}You need to authenticate with Google Cloud.${NC}"
# gcloud auth login


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
    --image-family=debian-11 \
    --image-project=debian-cloud \
    --boot-disk-size=200GB \
    --tags=http-server,https-server \
    --metadata=startup-script='#! /bin/bash
      apt-get update
      apt-get install -y python3-pip python3-venv git supervisor nginx certbot python3-certbot-nginx
      apt-get install -y postgresql postgresql-contrib
    '
  
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
rsync -av \
  --exclude 'node_modules' \
  --exclude '.venv' \
  --exclude '.git' \
  --exclude 'dist' \
  --exclude '__pycache__' \
  --exclude '*.pyc' \
  --exclude '*.pyo' \
  --exclude '.pytest_cache' \
  --exclude 'storage/logs' \
  --exclude 'storage/logs/*' \
  --exclude 'server/messages' \
  --exclude 'server/messages/*' \
  --exclude 'brew_venv' \
  --exclude '.vscode' \
  --exclude '.idea' \
  . "$TEMP_DIR/"

# Create production environment file
cat > "$TEMP_DIR/.env.prod" << EOL
# Telegram API credentials
TELEGRAM_API_ID=${TELEGRAM_API_ID:-"your_telegram_api_id"}
TELEGRAM_API_HASH=${TELEGRAM_API_HASH:-"your_telegram_api_hash"}

ENV =production
# Database settings
DB_TYPE=postgres
DB_PORT=5432
DB_USERNAME=tgportal
DB_PASSWORD=tgportal_password
DB_HOST=localhost
DB_DATABASE=tgportal

# FastAPI settings
DEBUG=false
HOST=0.0.0.0
PORT=8030
SERVER_PORT=8030

# Backend URL for the frontend
BACKEND_URL=http://${EXTERNAL_IP}

# Firebase settings
FIREBASE_PROJECT_ID=${FIREBASE_PROJECT_ID:-"your_firebase_project_id"}
FIREBASE_PROJECT_NUMBER=${FIREBASE_PROJECT_NUMBER:-"your_firebase_project_number"}

# AI model settings
GOOGLE_STUDIO_API_KEY=${GOOGLE_STUDIO_API_KEY:-"your_google_studio_api_key"}
EOL

# Create supervisor configuration
cat > "$TEMP_DIR/tgportal.conf" << EOL
[program:tgportal]
command=/home/${VM_USERNAME}/.local/bin/poetry run app
directory=${APP_DIR}
user=${VM_USERNAME}
autostart=true
autorestart=true
stopasgroup=true
killasgroup=true
stderr_logfile=/var/log/tgportal/tgportal.err.log
stdout_logfile=/var/log/tgportal/tgportal.out.log
environment=PYTHONPATH="${APP_DIR}",PATH="/home/${VM_USERNAME}/.local/bin:/usr/local/bin:/usr/bin:/bin"
EOL

# Create Nginx configuration
cat > "$TEMP_DIR/tgportal_nginx.conf" << EOL
server {
    listen 80;
    server_name ${EXTERNAL_IP};

    location / {
        proxy_pass http://localhost:8030;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
EOL

# Create setup script to run on the remote machine
cat > "$TEMP_DIR/setup.sh" << 'EOL'
#!/bin/bash
set -e  # Exit on any error

# Display progress
echo "==============================================="
echo "Starting TG Portal backend setup"
echo "==============================================="

# Define app directory explicitly to avoid empty path issues
APP_DIR="$APP_DIR"
[ -z "$APP_DIR" ] && { echo "ERROR: APP_DIR is not set"; exit 1; }

# Setup database
echo "[1/6] Setting up PostgreSQL database..."
if ! sudo -u postgres psql -lqt | cut -d \| -f 1 | grep -qw tgportal; then
  echo "Creating PostgreSQL database and user..."
  sudo -u postgres psql -c "CREATE DATABASE tgportal;"
  sudo -u postgres psql -c "CREATE USER tgportal WITH PASSWORD 'tgportal_password';"
  sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE tgportal TO tgportal;"
  echo "PostgreSQL database and user created successfully."
else
  echo "PostgreSQL database already exists. Ensuring user has proper permissions..."
  sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE tgportal TO tgportal;" || true
fi

# Setup application directory
echo "[2/6] Setting up application directory..."
mkdir -p "$APP_DIR"
echo "Application directory created/verified at $APP_DIR"

# Create necessary directories first
echo "Creating necessary directories..."
mkdir -p "$APP_DIR/storage/logs"
mkdir -p "$APP_DIR/storage/sessions"
mkdir -p "$APP_DIR/server/messages"

# Copy application files
echo "[3/6] Copying application files..."
echo "Using rsync to copy files from /tmp/tgportal_deploy to $APP_DIR"
rsync -a /tmp/tgportal_deploy/ "$APP_DIR/"
cd "$APP_DIR"

# Create necessary directories for logs and sessions
mkdir -p storage/logs
mkdir -p storage/sessions
mkdir -p server/messages

# Make sure PYTHONPATH is set for the current session too
export PYTHONPATH="$APP_DIR"

# Setup Python environment and dependencies
echo "[4/6] Setting up Python environment and dependencies..."
echo "Installing Poetry..."
curl -sSL https://install.python-poetry.org | python3 -
export PATH="/root/.local/bin:$HOME/.local/bin:$PATH"
echo 'export PATH="/root/.local/bin:$HOME/.local/bin:$PATH"' >> ~/.bashrc
echo 'export PATH="/root/.local/bin:$HOME/.local/bin:$PATH"' >> ~/.profile

# Verify Poetry is installed correctly
if ! command -v poetry &> /dev/null; then
  echo "Poetry installation failed. Installing with pip..."
  pip3 install poetry
fi

# Configure Poetry settings
echo "Configuring Poetry..."
poetry config virtualenvs.create false
poetry config experimental.new-installer false

# Install dependencies using Poetry
echo "Installing dependencies with Poetry..."
poetry install --no-dev --no-interaction || {
  echo "Poetry install failed. Trying with explicit installation..."
  # Check if pyproject.toml exists
  if [ -f "pyproject.toml" ]; then
    echo "Installing from pyproject.toml..."
    pip3 install .
  else
    echo "No pyproject.toml found. Trying requirements.txt..."
    if [ -f "requirements.txt" ]; then
      pip3 install -r requirements.txt
    else
      echo "Generating requirements.txt from pyproject.toml..."
      poetry export -f requirements.txt --output requirements.txt --without-hashes
      pip3 install -r requirements.txt
    fi
  fi
}

# Copy environment file
cp .env.prod .env
echo "Production environment file copied."

# Setup supervisor
echo "[5/6] Setting up Supervisor..."
sudo mkdir -p /var/log/tgportal
sudo chown $USER:$USER /var/log/tgportal
sudo cp tgportal.conf /etc/supervisor/conf.d/
sudo supervisorctl reread
sudo supervisorctl update
if sudo supervisorctl status tgportal | grep -q RUNNING; then
  echo "Restarting tgportal service..."
  sudo supervisorctl restart tgportal
else
  echo "Starting tgportal service..."
  sudo supervisorctl start tgportal
fi

# Setup Nginx
echo "[6/6] Setting up Nginx..."
sudo cp tgportal_nginx.conf /etc/nginx/sites-available/tgportal
sudo ln -sf /etc/nginx/sites-available/tgportal /etc/nginx/sites-enabled/
if sudo nginx -t; then
  echo "Nginx configuration is valid."
  sudo systemctl reload nginx
else
  echo "WARNING: Nginx configuration is invalid. Please check manually."
fi

# Run migrations if needed
echo "Running database migrations..."
export PYTHONPATH="$APP_DIR"
echo "Running migrations with Poetry..."
poetry run alembic upgrade head || {
  echo "WARNING: Poetry migration failed. Trying direct alembic command..."
  if command -v alembic &> /dev/null; then
    alembic upgrade head || echo "WARNING: Alembic migrations failed. You may need to run them manually."
  else
    echo "WARNING: Alembic not found. You may need to run migrations manually."
  fi
}

echo "==============================================="
echo "Setup completed successfully!"
echo "==============================================="
EOL

# Replace APP_DIR in the setup script
if [[ "$OSTYPE" == "darwin"* ]]; then
  # macOS version of sed
  sed -i '' "s|\\$APP_DIR|$APP_DIR|g" "$TEMP_DIR/setup.sh"
else
  # Linux/GNU version of sed
  sed -i "s|\\$APP_DIR|$APP_DIR|g" "$TEMP_DIR/setup.sh"
fi
chmod +x "$TEMP_DIR/setup.sh"

# Deploy to the VM instance
echo -e "${YELLOW}Deploying to VM instance...${NC}"

# Create setup script for GitHub-based deployment
cat > "$TEMP_DIR/github_setup.sh" << EOL
#!/bin/bash
set -e  # Exit on any error

# Install Git if not already available
if ! command -v git &> /dev/null; then
  echo "Installing Git..."
  sudo apt-get update
  sudo apt-get install -y git
fi

# Clone the repository (replace with your actual GitHub repo)
echo "Cloning repository from GitHub..."
GITHUB_REPO="https://\${GITHUB_TOKEN}@github.com/your-username/tgportal.git"
BRANCH="main"  # or your default branch

# Clean up any previous deployment
rm -rf /tmp/tgportal_deploy
mkdir -p /tmp/tgportal_deploy

# Clone the repository
git clone --depth 1 --branch \$BRANCH \$GITHUB_REPO /tmp/tgportal_deploy || {
  echo "Failed to clone repository. Check your GitHub token and repository URL."
  exit 1
}

# Copy the configuration files
cp /tmp/config/.env.prod /tmp/tgportal_deploy/
cp /tmp/config/tgportal.conf /tmp/tgportal_deploy/
cp /tmp/config/tgportal_nginx.conf /tmp/tgportal_deploy/

# Run the setup script
cd /tmp/tgportal_deploy
bash setup.sh
EOL
chmod +x "$TEMP_DIR/github_setup.sh"

# Create a temporary config directory to hold the configuration files
mkdir -p "$TEMP_DIR/config"
cp "$TEMP_DIR/.env.prod" "$TEMP_DIR/config/"
cp "$TEMP_DIR/tgportal.conf" "$TEMP_DIR/config/"
cp "$TEMP_DIR/tgportal_nginx.conf" "$TEMP_DIR/config/"

# Copy the config files and setup script to the VM
echo -e "${YELLOW}Copying setup script and configuration files to the VM...${NC}"
if ! gcloud compute ssh "$INSTANCE_NAME" --zone="$ZONE" --command="mkdir -p /tmp/config"; then
  echo -e "${RED}Failed to create config directory on VM. Aborting.${NC}"
  exit 1
fi

if ! gcloud compute scp "$TEMP_DIR/github_setup.sh" "$INSTANCE_NAME:~/github_setup.sh" --zone="$ZONE"; then
  echo -e "${RED}Failed to copy setup script to VM. Aborting.${NC}"
  exit 1
fi

if ! gcloud compute scp "$TEMP_DIR/config/.env.prod" "$INSTANCE_NAME:/tmp/config/.env.prod" --zone="$ZONE"; then
  echo -e "${RED}Failed to copy .env.prod to VM. Aborting.${NC}"
  exit 1
fi

if ! gcloud compute scp "$TEMP_DIR/config/tgportal.conf" "$INSTANCE_NAME:/tmp/config/tgportal.conf" --zone="$ZONE"; then
  echo -e "${RED}Failed to copy tgportal.conf to VM. Aborting.${NC}"
  exit 1
fi

if ! gcloud compute scp "$TEMP_DIR/config/tgportal_nginx.conf" "$INSTANCE_NAME:/tmp/config/tgportal_nginx.conf" --zone="$ZONE"; then
  echo -e "${RED}Failed to copy tgportal_nginx.conf to VM. Aborting.${NC}"
  exit 1
fi

# Extract and run the setup script with progress monitoring
echo -e "${YELLOW}Setting up the application on the VM...${NC}"
echo -e "${YELLOW}This may take several minutes. Please be patient.${NC}"
echo -e "${YELLOW}Enter your GitHub Personal Access Token when prompted...${NC}"

# Prompt for GitHub token
read -sp "Enter GitHub Personal Access Token: " GITHUB_TOKEN
echo

gcloud compute ssh "$INSTANCE_NAME" --zone="$ZONE" --command="
export GITHUB_TOKEN='$GITHUB_TOKEN'
bash ~/github_setup.sh
" || {
  echo -e "${RED}Deployment failed. Please check the logs for more information.${NC}"
  exit 1
}

# Clean up temporary files
echo -e "${YELLOW}Cleaning up local temporary files...${NC}"
rm -rf "$TEMP_DIR"

echo -e "${GREEN}Deployment complete!${NC}"

# Verify application is running
echo -e "${YELLOW}Verifying application status...${NC}"
APP_STATUS=$(gcloud compute ssh "$INSTANCE_NAME" --zone="$ZONE" --command="sudo supervisorctl status tgportal" 2>/dev/null || echo "FAILED")

if [[ "$APP_STATUS" == *"RUNNING"* ]]; then
  echo -e "${GREEN}✓ TG Portal backend is running successfully!${NC}"
else
  echo -e "${RED}⚠ TG Portal backend might not be running correctly. Status: $APP_STATUS${NC}"
  echo -e "${YELLOW}Checking supervisor logs...${NC}"
  gcloud compute ssh "$INSTANCE_NAME" --zone="$ZONE" --command="sudo cat /var/log/tgportal/tgportal.err.log | tail -n 20"
  echo -e "${YELLOW}You may need to manually check the logs with:${NC}"
  echo -e "${YELLOW}gcloud compute ssh $INSTANCE_NAME --zone=$ZONE --command=\"sudo supervisorctl status tgportal; sudo cat /var/log/tgportal/tgportal.err.log\"${NC}"
fi

echo -e "${GREEN}Your FastAPI application should be accessible at: http://$EXTERNAL_IP${NC}"

# Test the API endpoint
echo -e "${YELLOW}Testing API endpoint...${NC}"
if curl -s --max-time 5 "http://$EXTERNAL_IP/api/health" | grep -q "status"; then
  echo -e "${GREEN}✓ API health endpoint is responding!${NC}"
else
  echo -e "${YELLOW}⚠ API health endpoint may not be responding. This could be normal if your app doesn't have a /api/health endpoint.${NC}"
fi

echo -e "${YELLOW}To SSH into the VM: gcloud compute ssh $INSTANCE_NAME --zone=$ZONE${NC}"

# Update the frontend .env file with the new backend URL if needed
if [ -f ".env" ]; then
  if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS version of sed
    sed -i '' "s|BACKEND_URL=.*|BACKEND_URL=http://$EXTERNAL_IP|g" .env
  else
    # Linux/GNU version of sed
    sed -i "s|BACKEND_URL=.*|BACKEND_URL=http://$EXTERNAL_IP|g" .env
  fi
  echo -e "${GREEN}Updated BACKEND_URL in .env file to point to the new server: http://$EXTERNAL_IP${NC}"
fi

echo -e "${GREEN}==================================================================${NC}"
echo -e "${GREEN}Deployment Summary:${NC}"
echo -e "${GREEN}==================================================================${NC}"
echo -e "${YELLOW}Backend URL:${NC} http://$EXTERNAL_IP"
echo -e "${YELLOW}VM Instance:${NC} $INSTANCE_NAME (Zone: $ZONE)"
echo -e "${YELLOW}Machine Type:${NC} $MACHINE_TYPE"
echo -e "${YELLOW}==================================================================${NC}"
echo -e "${GREEN}Next steps:${NC}"
echo -e "1. Update your Firebase configuration to allow requests from this domain"
echo -e "2. If you have a domain name, configure it to point to $EXTERNAL_IP"
echo -e "3. Run './deploy_frontend.sh' to deploy your frontend to Firebase"
echo -e "4. Monitor your application logs with: gcloud compute ssh $INSTANCE_NAME --zone=$ZONE --command=\"sudo tail -f /var/log/tgportal/tgportal.out.log\""
echo -e "${YELLOW}==================================================================${NC}"
