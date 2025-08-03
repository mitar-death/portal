#!/bin/bash
set -euo pipefail

# ---------- Logging helpers ----------
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

info() { echo -e "${GREEN}[INFO]${NC} $*"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*"; }

# ---------- Bootstrap ----------
info "==============================================="
info "Starting TG Portal backend setup"
info "==============================================="

# Determine real user (handles sudo)
REAL_USER=${SUDO_USER:-$USER}

# Load environment file early if exists (non-destructive)
if [ -f ".env" ]; then
  # shellcheck disable=SC1091
  set -a
  # load without exporting error if variables have spaces
  # shellcheck disable=SC1090
  source .env || true
  set +a
  info "Loaded existing .env into environment."
fi

# Define app directory explicitly to avoid empty path issues
APP_DIR=${APP_DIR:-"/home/${REAL_USER}/tgportal"}
if [ -z "$APP_DIR" ]; then
  error "APP_DIR is not set"
  exit 1
fi

# Helper to get public/external IP (tries a few fallbacks)
get_public_ip() {
  local ip
  ip="$(curl -fsSL http://checkip.amazonaws.com || true)"
  if [[ -n "$ip" ]]; then
    echo "$ip"
    return
  fi
  # Fallback to metadata (GCE)
  ip="$(curl -fsSL http://169.254.169.254/latest/meta-data/public-ipv4 || true)"
  if [[ -n "$ip" ]]; then
    echo "$ip"
    return
  fi
  # Last resort: local IP
  ip=$(hostname -I | awk '{print $1}')
  echo "$ip"
}

EXTERNAL_IP=${EXTERNAL_IP:-$(get_public_ip)}
CLOUD_SQL_CONNECTION_NAME=${CLOUD_SQL_CONNECTION_NAME:-""}
DB_HOST=${DB_HOST:-"localhost"}
DB_USERNAME=${DB_USERNAME:-"tgportal"}
DB_PASSWORD=${DB_PASSWORD:-"tgportal_password"}
DB_DATABASE=${DB_DATABASE:-"tgportal"}

CUSTOM_DOMAIN=${CUSTOM_DOMAIN:-""}
USE_HTTPS=${USE_HTTPS:-"false"}

# ---------- Database setup ----------
if [[ -n "$CLOUD_SQL_CONNECTION_NAME" ]]; then
  info "[1/6] Using Cloud SQL PostgreSQL database"
  info "Connection name: $CLOUD_SQL_CONNECTION_NAME"
  info "Database host: $DB_HOST"

  info "Testing database connection..."
  if command -v pg_isready &>/dev/null; then
    if pg_isready -h "$DB_HOST" -p 5432 -U "$DB_USERNAME"; then
      info "Database connection successful!"
    else
      warn "Failed to connect to Cloud SQL. Continuing, but the app may fail if DB is unreachable."
      warn "Possible causes: firewall, credentials, or service down."
    fi
  else
    warn "pg_isready not installed; skipping connection health check."
  fi

  info "No local PostgreSQL setup needed."
else
  info "[1/6] Cloud SQL not configured; ensuring local PostgreSQL database exists."
  if ! sudo -u postgres psql -lqt | cut -d \| -f1 | grep -qw "$DB_DATABASE"; then
    info "Creating PostgreSQL database and user..."
    sudo -u postgres psql -c "CREATE DATABASE ${DB_DATABASE};"
    sudo -u postgres psql -c "CREATE USER ${DB_USERNAME} WITH PASSWORD '${DB_PASSWORD}';"
    sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE ${DB_DATABASE} TO ${DB_USERNAME};"
    info "Local PostgreSQL database and user created."
  else
    info "Database ${DB_DATABASE} already exists. Ensuring privileges..."
    sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE ${DB_DATABASE} TO ${DB_USERNAME};" || true
  fi
fi

# ---------- Application directory & files ----------
info "[2/6] Setting up application directory..."
mkdir -p "$APP_DIR"
info "Application directory ensured at $APP_DIR"

info "Creating necessary subdirectories..."
mkdir -p "$APP_DIR/storage/logs" "$APP_DIR/storage/sessions" "$APP_DIR/server/messages"

info "Copying application source into $APP_DIR (cleaning caches)..."
cp -r . "$APP_DIR/" && find "$APP_DIR" -name "__pycache__" -o -name "*.pyc" -o -name ".git" | xargs rm -rf 2>/dev/null || true
cd "$APP_DIR"

# ---------- System directories ----------
info "Setting up system directories..."
sudo mkdir -p /etc/supervisor/conf.d
sudo mkdir -p /etc/nginx/sites-available /etc/nginx/sites-enabled

# ---------- Python environment ----------
info "[3/6] Setting up Python environment and dependencies..."
# Ensure Poetry is installed (per-user)
POETRY_BIN="${HOME}/.local/bin/poetry"
if ! command -v poetry &>/dev/null; then
  info "Installing Poetry..."
  curl -sSL https://install.python-poetry.org | python3 -
fi

# Ensure Poetry in PATH for current session
export PATH="${HOME}/.local/bin:${PATH}"
if ! grep -q 'export PATH=".*/.local/bin' "${HOME}/.bashrc" 2>/dev/null; then
  echo 'export PATH="$HOME/.local/bin:$PATH"' >> "${HOME}/.bashrc"
  echo 'export PATH="$HOME/.local/bin:$PATH"' >> "${HOME}/.profile"
fi

if ! command -v poetry &>/dev/null; then
  warn "Poetry still not available; falling back to pip for dependencies."
fi

# Poetry configuration
if command -v poetry &>/dev/null; then
  poetry config virtualenvs.create true
  poetry config virtualenvs.in-project true

  info "Creating/using Poetry virtual environment..."
  poetry env use python3 || true
  VENV_PATH=$(poetry env info --path 2>/dev/null || echo "")
  if [[ -z "$VENV_PATH" ]]; then
    warn "Could not get Poetry virtualenv path; creating manual venv."
    python3 -m venv "$APP_DIR/.venv"
    VENV_PATH="$APP_DIR/.venv"
  fi
else
  VENV_PATH="$APP_DIR/.venv"
  if [[ ! -d "$VENV_PATH" ]]; then
    info "Creating fallback virtual environment..."
    python3 -m venv "$VENV_PATH"
  fi
fi

info "Virtual environment path: $VENV_PATH"

# Activate if possible (non-fatal if it fails)
if [[ -f "$VENV_PATH/bin/activate" ]]; then
  # shellcheck disable=SC1091
  source "$VENV_PATH/bin/activate" || warn "Failed to source virtualenv activation script."
else
  warn "Virtualenv activate script not found at $VENV_PATH/bin/activate"
fi

# Install dependencies
if command -v poetry &>/dev/null; then
  info "Installing dependencies with Poetry..."
  if ! poetry install --no-interaction; then
    warn "Poetry install failed; attempting fallbacks."
    if [[ -f "pyproject.toml" ]]; then
      pip3 install .
    elif [[ -f "requirements.txt" ]]; then
      pip3 install -r requirements.txt
    elif [[ -f "pyproject.toml" ]]; then
      poetry export -f requirements.txt --output requirements.txt --without-hashes
      pip3 install -r requirements.txt
    else
      warn "No dependency definition found (pyproject.toml or requirements.txt)."
    fi
  fi
else
  if [[ -f "requirements.txt" ]]; then
    info "Installing dependencies from requirements.txt..."
    pip3 install -r requirements.txt
  else
    warn "No requirements.txt to install from."
  fi
fi

# ---------- Environment file fallback ----------
if [ -f "/tmp/config/.env.prod" ]; then
  cp /tmp/config/.env.prod .env
  info "Copied production .env from /tmp/config/.env.prod"
elif [ -f ".env.prod" ]; then
  cp .env.prod .env
  info "Copied production .env from local .env.prod"
else
  warn "No production env file found. Generating default .env"
  cat > .env <<EOF
# Telegram API credentials
TELEGRAM_API_ID=${TELEGRAM_API_ID:-"your_telegram_api_id"}
TELEGRAM_API_HASH=${TELEGRAM_API_HASH:-"your_telegram_api_hash"}

ENV=production
# Database settings
DB_TYPE=postgres
DB_PORT=5432
DB_USERNAME=${DB_USERNAME}
DB_PASSWORD=${DB_PASSWORD}
DB_HOST=${DB_HOST}
DB_DATABASE=${DB_DATABASE}

# FastAPI settings
DEBUG=false
HOST=127.0.0.1
PORT=8000
SERVER_PORT=8000

# Backend URL for the frontend
BACKEND_URL=http://${EXTERNAL_IP}

# Firebase settings
FIREBASE_PROJECT_ID=${FIREBASE_PROJECT_ID:-"your_firebase_project_id"}
FIREBASE_PROJECT_NUMBER=${FIREBASE_PROJECT_NUMBER:-"your_firebase_project_number"}

# AI model settings
GOOGLE_STUDIO_API_KEY=${GOOGLE_STUDIO_API_KEY:-"your_google_studio_api_key"}
EOF
fi

# ---------- Supervisor setup ----------
info "[4/6] Setting up Supervisor..."
sudo mkdir -p /var/log/tgportal
sudo chown "${REAL_USER}:${REAL_USER}" /var/log/tgportal

if [ -f "/tmp/config/tgportal.conf" ]; then
  info "Using supervisor configuration from deployment."
  sudo cp "/tmp/config/tgportal.conf" /etc/supervisor/conf.d/
elif [ -f "$APP_DIR/tgportal.conf" ]; then
  info "Copying supervisor config from app directory."
  sudo cp "$APP_DIR/tgportal.conf" /etc/supervisor/conf.d/
else
  info "Generating supervisor configuration."
  PYTHON_PATH=$(which python3 || echo "/usr/bin/python3")
  sudo tee /etc/supervisor/conf.d/tgportal.conf > /dev/null <<EOF
[program:tgportal]
command=$PYTHON_PATH -m uvicorn server.app.main:app --host=127.0.0.1 --port=8000 --workers 4
directory=$APP_DIR
user=$REAL_USER
autostart=true
autorestart=true
stopasgroup=true
killasgroup=true
stderr_logfile=/var/log/tgportal/tgportal.err.log
stdout_logfile=/var/log/tgportal/tgportal.out.log
environment=PYTHONPATH="$APP_DIR",PORT="8000"
EOF
fi

info "Reloading Supervisor configuration..."
sudo supervisorctl reread || true
sudo supervisorctl update || true

# Start or restart service
if sudo supervisorctl status tgportal | grep -q RUNNING; then
  info "Restarting existing tgportal service..."
  sudo supervisorctl restart tgportal || true
else
  info "Starting tgportal service..."
  sudo supervisorctl start tgportal || true
fi

sleep 5
info "Supervisor status:"
sudo supervisorctl status tgportal || true

# ---------- Nginx & SSL setup ----------
info "[5/6] Setting up Nginx and SSL..."

# Ensure necessary packages for DNS/network checks are present (install once)
need_pkg=()
if ! command -v dig &>/dev/null; then
  need_pkg+=("dnsutils")
fi
if ! command -v nc &>/dev/null; then
  need_pkg+=("netcat")
fi
if [ "${#need_pkg[@]}" -gt 0 ]; then
  info "Installing required network utilities: ${need_pkg[*]}"
  sudo apt-get update
  sudo apt-get install -y "${need_pkg[@]}"
fi

# Helper to check if port is open from remote perspective (simple TCP connect to self)
check_port() {
  local host=$1 port=$2
  if nc -z -w5 "$host" "$port" &>/dev/null; then
    echo "1"
  else
    echo "0"
  fi
}

CERT_PATH=""
KEY_PATH=""
USE_SELF_SIGNED=false

generate_self_signed() {
  local dom=$1
  info "Generating self-signed certificate for $dom"
  sudo mkdir -p /etc/ssl/private /etc/ssl/certs
  sudo openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
    -keyout /etc/ssl/private/"${dom}".key \
    -out /etc/ssl/certs/"${dom}".crt \
    -subj "/CN=${dom}/O=TG Portal/C=US"
  CERT_PATH="/etc/ssl/certs/${dom}.crt"
  KEY_PATH="/etc/ssl/private/${dom}.key"
  USE_SELF_SIGNED=true
}

obtain_lets_encrypt_cert() {
  local dom=$1
  local email=${2:-"admin@${dom}"}
  local http_ok=0

  # Resolve domain IP(s)
  DOMAIN_IPS=$(dig +short A "$dom" | tr '\n' ' ')
  SERVER_IP=$(get_public_ip)

  if [[ -z "$DOMAIN_IPS" ]]; then
    warn "Could not resolve $dom; HTTPS validation will likely fail."
  else
    for ip in $DOMAIN_IPS; do
      if [[ "$ip" == "$SERVER_IP" ]]; then
        # check if port 80 is reachable locally (assume Nginx can bind)
        if [[ $(check_port "$dom" 80) -eq 1 ]]; then
          http_ok=1
          break
        fi
      fi
    done
  fi

  if [[ $http_ok -eq 1 ]]; then
    info "Attempting Let’s Encrypt HTTP challenge for $dom"
    if sudo certbot --nginx -d "$dom" --non-interactive --agree-tos --email "$email" --redirect; then
      CERT_PATH="/etc/letsencrypt/live/${dom}/fullchain.pem"
      KEY_PATH="/etc/letsencrypt/live/${dom}/privkey.pem"
      return 0
    else
      warn "HTTP challenge failed; will attempt DNS challenge."
    fi
  else
    warn "Skipping HTTP validation (domain doesn't resolve cleanly to this IP or port 80 not open)."
  fi

  info "Attempting Let’s Encrypt DNS challenge for $dom"
  if sudo certbot certonly --manual --preferred-challenges dns -d "$dom" --agree-tos --email "$email"; then
    CERT_PATH="/etc/letsencrypt/live/${dom}/fullchain.pem"
    KEY_PATH="/etc/letsencrypt/live/${dom}/privkey.pem"
    return 0
  else
    warn "Let’s Encrypt DNS challenge also failed."
    return 1
  fi
}

# Prepare nginx config depending on domain/HTTPS
render_nginx_config() {
  local target_conf="/etc/nginx/sites-available/tgportal"

  if [[ -n "$CUSTOM_DOMAIN" ]] && [[ "$USE_HTTPS" == "true" ]]; then
    info "Custom domain detected: $CUSTOM_DOMAIN; setting up HTTPS."
    # Attempt to acquire certificate if not already present
    if [[ -f "/etc/letsencrypt/live/${CUSTOM_DOMAIN}/fullchain.pem" ]] && [[ -f "/etc/letsencrypt/live/${CUSTOM_DOMAIN}/privkey.pem" ]]; then
      info "Existing Let's Encrypt certificates found; using them."
      CERT_PATH="/etc/letsencrypt/live/${CUSTOM_DOMAIN}/fullchain.pem"
      KEY_PATH="/etc/letsencrypt/live/${CUSTOM_DOMAIN}/privkey.pem"
    else
      if ! obtain_lets_encrypt_cert "$CUSTOM_DOMAIN"; then
        warn "Let’s Encrypt failed; falling back to self-signed certificate."
        generate_self_signed "$CUSTOM_DOMAIN"
      fi
    fi

    # Render HTTPS-capable config
    sudo tee "$target_conf" > /dev/null <<EOF
server {
    listen 80;
    server_name ${CUSTOM_DOMAIN};
    location / {
        return 301 https://${CUSTOM_DOMAIN}\$request_uri;
    }
}

server {
    listen 443 ssl;
    server_name ${CUSTOM_DOMAIN};

    ssl_certificate ${CERT_PATH};
    ssl_certificate_key ${KEY_PATH};

    location / {
        proxy_pass http://0.0.0.0:8000;
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
EOF

  else
    info "No valid custom domain with HTTPS; falling back to HTTP on IP."
    sudo tee "/etc/nginx/sites-available/tgportal" > /dev/null <<EOF
server {
    listen 80;
    server_name ${EXTERNAL_IP};

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
EOF
  fi

  # Deployment override config
  if [ -f "/tmp/config/tgportal_nginx.conf" ]; then
    info "Overriding Nginx config from deployment-provided file."
    sudo cp "/tmp/config/tgportal_nginx.conf" /etc/nginx/sites-available/tgportal
  elif [ -f "$APP_DIR/tgportal_nginx.conf" ]; then
    info "Overriding Nginx config from app directory."
    sudo cp "$APP_DIR/tgportal_nginx.conf" /etc/nginx/sites-available/tgportal
  fi

  sudo ln -sf /etc/nginx/sites-available/tgportal /etc/nginx/sites-enabled/
  if [ -f /etc/nginx/sites-enabled/default ]; then
    sudo rm -f /etc/nginx/sites-enabled/default
  fi

  # Validate & reload
  if sudo nginx -t; then
    info "Nginx config valid; reloading."
    sudo systemctl reload nginx || sudo service nginx reload || true
  else
    warn "Nginx config test failed; falling back to minimal HTTP on domain/IP."
    sudo tee /etc/nginx/sites-available/tgportal > /dev/null <<EOF
server {
    listen 80;
    server_name ${CUSTOM_DOMAIN:-${EXTERNAL_IP}};

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
EOF
    sudo systemctl reload nginx || sudo service nginx reload || true
  fi

  if [[ -n "$CUSTOM_DOMAIN" ]] && [[ "$USE_HTTPS" == "true" ]]; then
    info "HTTPS setup finished for ${CUSTOM_DOMAIN}"
  else
    info "HTTP setup finished on ${EXTERNAL_IP}"
  fi
}

render_nginx_config

# ---------- Migrations ----------
export PYTHONPATH="$APP_DIR"
info "[6/6] Running database migrations..."
if [[ -n "${VENV_PATH:-}" ]] && [[ -x "${VENV_PATH}/bin/alembic" ]]; then
  "${VENV_PATH}/bin/alembic" upgrade head || warn "Alembic upgrade failed."
else
  info "Trying via Poetry run..."
  if ! poetry run alembic upgrade head 2>/dev/null; then
    if command -v alembic &>/dev/null; then
      alembic upgrade head || warn "Alembic migrations failed; you may need to run them manually."
    else
      warn "Alembic binary not found; skipping migrations."
    fi
  fi
fi

# ---------- Final status ----------
info "==============================================="
info "Setup completed successfully!"
info "==============================================="
if [[ -n "$CUSTOM_DOMAIN" ]] && [[ "$USE_HTTPS" == "true" ]]; then
  info "TG Portal backend is now running at: https://${CUSTOM_DOMAIN}"
else
  info "TG Portal backend is now running at: http://${EXTERNAL_IP}"
fi
info "==============================================="
