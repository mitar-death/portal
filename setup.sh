#!/bin/bash
set -e  # Exit on any error

# Colors for terminal output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Display progress
echo -e "${GREEN}===============================================${NC}"
echo -e "${GREEN}Starting TG Portal backend setup${NC}"
echo -e "${GREEN}===============================================${NC}"

# Define app directory explicitly to avoid empty path issues
APP_DIR=${APP_DIR:-"/home/$USER/tgportal"}
[ -z "$APP_DIR" ] && { echo -e "${RED}ERROR: APP_DIR is not set${NC}"; exit 1; }

# Get external IP for Nginx configuration if not provided
EXTERNAL_IP=${EXTERNAL_IP:-$(curl -s http://checkip.amazonaws.com)}
CLOUD_SQL_CONNECTION_NAME=${CLOUD_SQL_CONNECTION_NAME:-""}

# Check if we're using Cloud SQL (preferred) or local PostgreSQL
if [ -n "$CLOUD_SQL_CONNECTION_NAME" ] || grep -q "CLOUD_SQL_CONNECTION_NAME" .env 2>/dev/null; then
  echo -e "${GREEN}[1/6] Using Cloud SQL PostgreSQL database${NC}"
  echo -e "${GREEN}Connection name: $CLOUD_SQL_CONNECTION_NAME${NC}"
  echo -e "${GREEN}Database host: $DB_HOST${NC}"
  
  # Test database connection
  echo -e "${YELLOW}Testing database connection...${NC}"
  if command -v pg_isready &> /dev/null; then
    if pg_isready -h "$DB_HOST" -p 5432 -U "$DB_USERNAME"; then
      echo -e "${GREEN}Database connection successful!${NC}"
    else
      echo -e "${RED}Failed to connect to database. Error code: $?${NC}"
      echo -e "${YELLOW}This might be due to:${NC}"
      echo -e "${YELLOW}1. Cloud SQL firewall not allowing connections from this VM${NC}"
      echo -e "${YELLOW}2. Database credentials being incorrect${NC}"
      echo -e "${YELLOW}3. Database service not running${NC}"
      echo -e "${YELLOW}Continuing anyway, but application might not work correctly.${NC}"
    fi
  fi
  
  echo -e "${GREEN}No local PostgreSQL setup needed${NC}"
else
  # Fallback to local PostgreSQL setup if needed
  echo -e "${YELLOW}[1/6] Cloud SQL not detected, setting up local PostgreSQL database...${NC}"
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



# Copy files from the cloned repository to the application directory
echo "Copying files from repository to $APP_DIR"
rsync -a . "$APP_DIR/" --exclude '.git' --exclude '__pycache__' --exclude '*.pyc'
cd "$APP_DIR"

# Ensure supervisor and nginx directories exist
echo "Setting up system directories..."
sudo mkdir -p /etc/supervisor/conf.d
sudo mkdir -p /etc/nginx/sites-available
sudo mkdir -p /etc/nginx/sites-enabled

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
echo "Configuring Poetry to use virtual environments..."
poetry config virtualenvs.create true
poetry config virtualenvs.in-project true

# Create and activate the virtual environment
echo "Creating Poetry virtual environment..."
cd "$APP_DIR"
poetry env use python3
VENV_PATH=$(poetry env info --path 2>/dev/null || echo "")

if [ -z "$VENV_PATH" ]; then
  echo "Failed to get virtual environment path from Poetry. Creating manually..."
  python3 -m venv "$APP_DIR/.venv"
  VENV_PATH="$APP_DIR/.venv"
fi

echo "Virtual environment created at: $VENV_PATH"

# Activate the virtual environment
echo "Activating virtual environment..."
if [ -f "$VENV_PATH/bin/activate" ]; then
  source "$VENV_PATH/bin/activate" || {
    echo "Failed to activate virtual environment with source. Trying with dot operator..."
    . "$VENV_PATH/bin/activate" || {
      echo "WARNING: Could not activate virtual environment. Will continue with system Python."
    }
  }
else
  echo "WARNING: Virtual environment activation script not found at $VENV_PATH/bin/activate"
fi


# Install dependencies using Poetry
echo "Installing dependencies with Poetry..."
poetry install --no-interaction || {
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


# Copy environment file from config directory if it exists
if [ -f "/tmp/config/.env.prod" ]; then
  cp /tmp/config/.env.prod .env
  echo -e "${GREEN}Production environment file copied from /tmp/config/.env.prod.${NC}"
elif [ -f ".env.prod" ]; then
  cp .env.prod .env
  echo -e "${GREEN}Production environment file copied from local .env.prod.${NC}"
else
  echo -e "${YELLOW}WARNING: No production environment file found. Creating a basic one...${NC}"
  cat > .env << EOL
    # Telegram API credentials
    TELEGRAM_API_ID=${TELEGRAM_API_ID:-"your_telegram_api_id"}
    TELEGRAM_API_HASH=${TELEGRAM_API_HASH:-"your_telegram_api_hash"}

    ENV=production
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
fi

# Setup supervisor
echo -e "${GREEN}[5/6] Setting up Supervisor...${NC}"


# Check if supervisor config exists in /tmp/config or was created during deployment
if [ -f "/tmp/config/tgportal.conf" ]; then
  echo -e "${GREEN}Using supervisor configuration from deployment...${NC}"
  sudo cp "/tmp/config/tgportal.conf" /etc/supervisor/conf.d/
elif [ -f "$APP_DIR/tgportal.conf" ]; then
  echo -e "${GREEN}Copying supervisor configuration from app directory...${NC}"
  sudo cp "$APP_DIR/tgportal.conf" /etc/supervisor/conf.d/
else
  echo -e "${YELLOW}Creating supervisor configuration file...${NC}"

  # Find Python path
  PYTHON_PATH=$(which python3)
  sudo tee /etc/supervisor/conf.d/tgportal.conf > /dev/null << EOL
    [program:tgportal]
    command=$PYTHON_PATH -m uvicorn server.app.main:app --host=0.0.0.0 --port=8030 --workers 4
    directory=$APP_DIR
    user=$USER
    autostart=true
    autorestart=true
    stopasgroup=true
    killasgroup=true
    stderr_logfile=/var/log/tgportal/tgportal.err.log
    stdout_logfile=/var/log/tgportal/tgportal.out.log
    environment=PYTHONPATH="$APP_DIR",PORT="8030"
EOL
fi

sudo mkdir -p /var/log/tgportal
sudo chown $USER:$USER /var/log/tgportal

# Reload supervisor configuration
echo -e "${YELLOW}Updating supervisor configuration...${NC}"
sudo supervisorctl reread
sudo supervisorctl update

# Check if the app is already running
if sudo supervisorctl status tgportal | grep -q RUNNING; then
  echo -e "${GREEN}Restarting tgportal service...${NC}"
  sudo supervisorctl restart tgportal
else
  echo -e "${GREEN}Starting tgportal service...${NC}"
  sudo supervisorctl start tgportal
fi

# Give supervisor a moment to start the application
sleep 5
echo -e "${YELLOW}Supervisor status after start/restart:${NC}"
sudo supervisorctl status tgportal

# Setup Nginx
echo -e "${GREEN}[6/6] Setting up Nginx...${NC}"

# Check if a custom domain is configured
if [ -n "$CUSTOM_DOMAIN" ] && [ "$USE_HTTPS" = "true" ]; then
  echo -e "${GREEN}Custom domain detected: $CUSTOM_DOMAIN${NC}"
  echo -e "${GREEN}Setting up HTTPS with Let's Encrypt...${NC}"
  
# Create symbolic link if it doesn't exist
sudo ln -sf /etc/nginx/sites-available/tgportal /etc/nginx/sites-enabled/

# Remove default site if it exists
if [ -f /etc/nginx/sites-enabled/default ]; then
  sudo rm /etc/nginx/sites-enabled/default
fi

# Validate and reload Nginx configuration
if sudo nginx -t; then
  echo -e "${GREEN}Nginx configuration is valid.${NC}"
  sudo systemctl reload nginx
else
  echo -e "${RED}Nginx configuration is invalid. Please check manually.${NC}"
  exit 1
fi

# Check if DNS is properly configured by checking if the domain resolves to the server IP
SERVER_IP=$(curl -s http://checkip.amazonaws.com)
echo -e "${YELLOW}Checking DNS configuration for $CUSTOM_DOMAIN...${NC}"
echo -e "${YELLOW}Server IP: $SERVER_IP${NC}"

# Try to resolve the domain with dig, host, or nslookup (whatever is available)
if command -v dig &> /dev/null; then
  DOMAIN_IP=$(dig +short $CUSTOM_DOMAIN | head -n 1)
elif command -v host &> /dev/null; then
  DOMAIN_IP=$(host $CUSTOM_DOMAIN | grep "has address" | head -n 1 | awk '{print $NF}')
elif command -v nslookup &> /dev/null; then
  DOMAIN_IP=$(nslookup $CUSTOM_DOMAIN | grep -A1 "Name:" | grep "Address:" | head -n 1 | awk '{print $2}')
else
  echo -e "${YELLOW}No DNS lookup tools available. Installing dnsutils...${NC}"
  sudo apt-get update
  sudo apt-get install -y dnsutils
  DOMAIN_IP=$(dig +short $CUSTOM_DOMAIN | head -n 1)
fi

if [ -z "$DOMAIN_IP" ]; then
  echo -e "${RED}Warning: Could not resolve $CUSTOM_DOMAIN to an IP address.${NC}"
  echo -e "${RED}Please make sure your DNS is properly configured to point to $SERVER_IP${NC}"
  echo -e "${YELLOW}Let's Encrypt validation may fail if DNS is not properly configured.${NC}"
  
  read -p "Do you want to continue with Let's Encrypt setup anyway? (y/n): " CONTINUE
  if [[ ! "$CONTINUE" =~ ^[Yy]$ ]]; then
    echo -e "${YELLOW}Skipping Let's Encrypt setup. You can run this script again later.${NC}"
    exit 0
  fi
elif [ "$DOMAIN_IP" != "$SERVER_IP" ]; then
  echo -e "${RED}Warning: Domain $CUSTOM_DOMAIN resolves to $DOMAIN_IP but this server's IP is $SERVER_IP${NC}"
  echo -e "${RED}Let's Encrypt validation will likely fail. Please fix your DNS configuration.${NC}"
  
  read -p "Do you want to continue with Let's Encrypt setup anyway? (y/n): " CONTINUE
  if [[ ! "$CONTINUE" =~ ^[Yy]$ ]]; then
    echo -e "${YELLOW}Skipping Let's Encrypt setup. You can run this script again later.${NC}"
    exit 0
  fi
else
  echo -e "${GREEN}DNS configuration looks good. Domain $CUSTOM_DOMAIN correctly points to $SERVER_IP${NC}"
fi

# Obtain SSL certificate using Certbot
echo -e "${GREEN}Obtaining SSL certificate from Let's Encrypt...${NC}"
sudo certbot --nginx -d "$CUSTOM_DOMAIN" --non-interactive --agree-tos --email "$EMAIL" --redirect || {
  echo -e "${RED}Certbot failed to obtain SSL certificate.${NC}"
  echo -e "${YELLOW}This might be due to:${NC}"
  echo -e "${YELLOW}1. DNS not fully propagated yet${NC}"
  echo -e "${YELLOW}2. Rate limits with Let's Encrypt${NC}"
  echo -e "${YELLOW}3. Firewall issues${NC}"
  echo -e "${YELLOW}Continuing with HTTP only. You can run this script again later.${NC}"
  exit 1
}

echo -e "${GREEN}SSL certificate successfully obtained and Nginx configured for HTTPS!${NC}"
echo -e "${GREEN}Your site is now accessible at https://$CUSTOM_DOMAIN${NC}"

# Set up auto-renewal
echo -e "${GREEN}Setting up automatic renewal of SSL certificates...${NC}"
echo "0 0,12 * * * root python3 -c 'import random; import time; time.sleep(random.random() * 3600)' && certbot renew -q" | sudo tee -a /etc/crontab > /dev/null

echo -e "${GREEN}HTTPS setup complete!${NC}"
EOL
  
    # Make the script executable
    chmod +x "$APP_DIR/setup_https.sh"
  fi
  
  # Run the HTTPS setup script
  bash "$APP_DIR/setup_https.sh" "$CUSTOM_DOMAIN"
  
else
  # Regular Nginx setup without HTTPS
  echo -e "${YELLOW}Setting up Nginx with HTTP only...${NC}"
  
  # Check if nginx config exists in /tmp/config or was created during deployment
  if [ -f "/tmp/config/tgportal_nginx.conf" ]; then
    echo -e "${GREEN}Using Nginx configuration from deployment...${NC}"
    sudo cp "/tmp/config/tgportal_nginx.conf" /etc/nginx/sites-available/tgportal
  elif [ -f "$APP_DIR/tgportal_nginx.conf" ]; then
    echo -e "${GREEN}Copying Nginx configuration from app directory...${NC}"
    sudo cp "$APP_DIR/tgportal_nginx.conf" /etc/nginx/sites-available/tgportal
  else
    echo -e "${YELLOW}Creating Nginx configuration file...${NC}"
    sudo tee /etc/nginx/sites-available/tgportal > /dev/null << EOL
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
  fi

  # Create symbolic link if it doesn't exist
  sudo ln -sf /etc/nginx/sites-available/tgportal /etc/nginx/sites-enabled/

  # Validate and reload Nginx configuration
  if sudo nginx -t; then
    echo -e "${GREEN}Nginx configuration is valid.${NC}"
    sudo systemctl reload nginx
  else
    echo -e "${RED}WARNING: Nginx configuration is invalid. Please check manually.${NC}"
  fi
fi

# Run migrations if needed
echo -e "${GREEN}Running database migrations...${NC}"
export PYTHONPATH="$APP_DIR"
echo -e "${GREEN}Running migrations with Poetry in virtual environment...${NC}"
if [ -n "$VENV_PATH" ] && [ -f "$VENV_PATH/bin/alembic" ]; then
  "$VENV_PATH/bin/alembic" upgrade head
else
  echo -e "${YELLOW}Trying with Poetry run command...${NC}"
  poetry run alembic upgrade head || {
    echo -e "${YELLOW}WARNING: Poetry migration failed. Trying direct alembic command...${NC}"
    if command -v alembic &> /dev/null; then
      alembic upgrade head || echo -e "${YELLOW}WARNING: Alembic migrations failed. You may need to run them manually.${NC}"
    else
      echo -e "${YELLOW}WARNING: Alembic not found. You may need to run migrations manually.${NC}"
    fi
  }
fi



echo -e "${GREEN}===============================================${NC}"
echo -e "${GREEN}Setup completed successfully!${NC}"
echo -e "${GREEN}===============================================${NC}"
echo -e "${YELLOW}TG Portal backend is now running at:${NC} http://${EXTERNAL_IP}"
echo -e "${GREEN}===============================================${NC}"
