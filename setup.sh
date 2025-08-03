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
cp -r . "$APP_DIR/" && find "$APP_DIR" -name "__pycache__" -o -name "*.pyc" -o -name ".git" | xargs rm -rf 2>/dev/null || true
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
    HOST=127.0.0.1
    PORT=8000
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
    command=$PYTHON_PATH -m uvicorn server.app.main:app --host=127.0.0.1 --port=8030 --workers 4
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
  echo -e "${YELLOW}Setting up HTTPS with SSL certificate...${NC}"
  
  # Check if certificates already exist before running Certbot
  if [ -f "/etc/letsencrypt/live/$CUSTOM_DOMAIN/fullchain.pem" ] && [ -f "/etc/letsencrypt/live/$CUSTOM_DOMAIN/privkey.pem" ]; then
    echo -e "${GREEN}SSL certificates for $CUSTOM_DOMAIN already exist. Skipping certificate generation.${NC}"
  else
    # Check if the domain dns is set and can be reached by certbot
    echo -e "${YELLOW}Checking if the domain $CUSTOM_DOMAIN is reachable...${NC}"
    
    # Install dig if not available
    if ! command -v dig &> /dev/null; then
      echo -e "${YELLOW}Installing DNS utilities (dig)...${NC}"
      sudo apt-get update && sudo apt-get install -y dnsutils
    fi
    
    # Install netcat if not available
    if ! command -v nc &> /dev/null; then
      echo -e "${YELLOW}Installing network utilities (nc)...${NC}"
      sudo apt-get update && sudo apt-get install -y netcat
    fi
  
  echo -e "${YELLOW}Verifying domain connectivity before running Certbot...${NC}"
  CURRENT_IP=$(curl -s ifconfig.me)
  DOMAIN_IP=$(dig +short $CUSTOM_DOMAIN A)
  PORT_80_OPEN=$(nc -z -w5 -v $CUSTOM_DOMAIN 80 2>&1 | grep -c "succeeded" || echo "0")

  echo -e "Domain IP: $DOMAIN_IP"
  echo -e "Server IP: $CURRENT_IP"
  echo -e "Port 80 accessible: $PORT_80_OPEN"

  # Set default methods
  USE_DNS_VALIDATION=false
  SKIP_HTTPS=false
  USE_SELF_SIGNED=false

  if [[ "$DOMAIN_IP" != "$CURRENT_IP" ]] || [[ "$PORT_80_OPEN" == "0" ]]; then
    echo -e "${RED}Warning: Domain $CUSTOM_DOMAIN points to $DOMAIN_IP, but this server's IP is $CURRENT_IP${NC}"
    echo -e "${YELLOW}Let's Encrypt HTTP validation will likely fail.${NC}"
    echo -e "${YELLOW}Proceeding with DNS-01 challenge method...${NC}"
    USE_DNS_VALIDATION=true
  fi

  # Make sure ports are open for certification
  echo -e "${YELLOW}Ensuring firewall allows Let's Encrypt validation...${NC}"
  sudo ufw allow 80/tcp || true
  sudo ufw allow 443/tcp || true

  # Choose certificate method
  if [ "$USE_DNS_VALIDATION" = "true" ]; then
    echo -e "${GREEN}Using DNS challenge method for domain verification...${NC}"
    echo -e "${YELLOW}You will be prompted to add a TXT record to your DNS configuration.${NC}"
    echo -e "${YELLOW}Follow the instructions displayed, and press Enter when ready.${NC}"
    
    if ! sudo certbot certonly --manual --preferred-challenges dns -d $CUSTOM_DOMAIN --agree-tos --email admin@$CUSTOM_DOMAIN; then
      echo -e "${RED}Certbot DNS validation failed. Creating self-signed certificate as fallback...${NC}"
      USE_SELF_SIGNED=true
    fi
  else
    echo -e "${GREEN}Using HTTP challenge method for domain verification...${NC}"
    if ! sudo certbot --nginx -d $CUSTOM_DOMAIN --non-interactive --agree-tos --email admin@$CUSTOM_DOMAIN --redirect; then
      echo -e "${RED}Certbot HTTP validation failed. Trying DNS validation method...${NC}"
      
      echo -e "${YELLOW}You will be prompted to add a TXT record to your DNS configuration.${NC}"
      echo -e "${YELLOW}Follow the instructions displayed, and press Enter when ready.${NC}"
      
      if ! sudo certbot certonly --manual --preferred-challenges dns -d $CUSTOM_DOMAIN --agree-tos --email admin@$CUSTOM_DOMAIN; then
        echo -e "${RED}Certbot DNS validation also failed. Creating self-signed certificate as fallback...${NC}"
        USE_SELF_SIGNED=true
      fi
    fi
  fi
  
  # Create self-signed certificate if needed
  if [ "$USE_SELF_SIGNED" = "true" ]; then
    echo -e "${YELLOW}Creating self-signed certificate...${NC}"
    sudo mkdir -p /etc/ssl/private
    sudo mkdir -p /etc/ssl/certs
    sudo openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
      -keyout /etc/ssl/private/$CUSTOM_DOMAIN.key \
      -out /etc/ssl/certs/$CUSTOM_DOMAIN.crt \
      -subj "/CN=$CUSTOM_DOMAIN/O=TG Portal/C=US"
    
    # Update certificate paths
    CERT_PATH="/etc/ssl/certs/$CUSTOM_DOMAIN.crt"
    KEY_PATH="/etc/ssl/private/$CUSTOM_DOMAIN.key"
  fi
  
  # Close the 'else' part of the certificate existence check
  fi


  # Create nginx configuration for HTTPS
  echo -e "${YELLOW}Configuring Nginx for HTTPS...${NC}"

  # Determine certificate paths
  if [ "$USE_SELF_SIGNED" = "true" ]; then
    echo -e "${GREEN}Using self-signed certificates for HTTPS configuration...${NC}"
    CERT_PATH="/etc/ssl/certs/$CUSTOM_DOMAIN.crt"
    KEY_PATH="/etc/ssl/private/$CUSTOM_DOMAIN.key"
  else
    echo -e "${GREEN}Using Let's Encrypt certificates for HTTPS configuration...${NC}"
    CERT_PATH="/etc/letsencrypt/live/$CUSTOM_DOMAIN/fullchain.pem"
    KEY_PATH="/etc/letsencrypt/live/$CUSTOM_DOMAIN/privkey.pem"
  fi

  # If we got here, we have valid SSL certificates
  sudo tee /etc/nginx/sites-available/tgportal > /dev/null << EOL
  server {
      listen 80;
      server_name $CUSTOM_DOMAIN;
      
      # Redirect all HTTP requests to HTTPS
      location / {
          return 301 https://\$host\$request_uri;
      }
  }

  server {
      listen 443 ssl;
      server_name $CUSTOM_DOMAIN;

      # SSL certificate files
      ssl_certificate $CERT_PATH;
      ssl_certificate_key $KEY_PATH;

      # Enhanced SSL settings
      ssl_protocols TLSv1.2 TLSv1.3;
      ssl_prefer_server_ciphers on;
      ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384:ECDHE-ECDSA-CHACHA20-POLY1305:ECDHE-RSA-CHACHA20-POLY1305:DHE-RSA-AES128-GCM-SHA256:DHE-RSA-AES256-GCM-SHA384;
      ssl_session_timeout 1d;
      ssl_session_cache shared:SSL:10m;
      ssl_session_tickets off;

      # OCSP Stapling
      ssl_stapling on;
      ssl_stapling_verify on;
      resolver 8.8.8.8 8.8.4.4 valid=300s;
      resolver_timeout 5s;

      # Proxy settings
      location / {
          proxy_pass http://127.0.0.1:8030;
          proxy_http_version 1.1;
          proxy_set_header Upgrade \$http_upgrade;
          proxy_set_header Connection "upgrade";
          proxy_set_header Host \$host;
          proxy_set_header X-Real-IP \$remote_addr;
          proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
          proxy_set_header X-Forwarded-Proto \$scheme;
          proxy_read_timeout 90;
          proxy_buffer_size 4k;
          proxy_buffers 4 32k;
          proxy_busy_buffers_size 64k;
      }
  }
EOL

  # Create symbolic link if it doesn't exist
  sudo ln -sf /etc/nginx/sites-available/tgportal /etc/nginx/sites-enabled/
  
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

  # Remove default site if it exists
  if [ -f /etc/nginx/sites-enabled/default ]; then
    sudo rm /etc/nginx/sites-enabled/default
  fi

  # Validate and reload Nginx configuration
  if sudo nginx -t; then
    echo -e "${GREEN}Nginx configuration is valid.${NC}"
    sudo systemctl reload nginx || sudo service nginx reload
    echo -e "${GREEN}HTTPS setup completed successfully for $CUSTOM_DOMAIN${NC}"
  else
    echo -e "${RED}WARNING: Nginx configuration is invalid. Please check manually.${NC}"
    echo -e "${YELLOW}Will continue with HTTP only configuration...${NC}"
    
    # Fallback to HTTP-only configuration
    sudo tee /etc/nginx/sites-available/tgportal > /dev/null << EOL
    server {
        listen 80;
        server_name ${CUSTOM_DOMAIN};

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
    sudo systemctl reload nginx || sudo service nginx reload
  fi
fi

# Run migrations if needed
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

fi



echo -e "${GREEN}===============================================${NC}"
echo -e "${GREEN}Setup completed successfully!${NC}"
echo -e "${GREEN}===============================================${NC}"
if [ -n "$CUSTOM_DOMAIN" ] && [ "$USE_HTTPS" = "true" ]; then
  echo -e "${YELLOW}TG Portal backend is now running at:${NC} https://${CUSTOM_DOMAIN}"
else
  echo -e "${YELLOW}TG Portal backend is now running at:${NC} http://${EXTERNAL_IP}"
fi
echo -e "${GREEN}===============================================${NC}"
