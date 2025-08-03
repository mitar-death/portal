#!/bin/bash
set -e  # Exit on any error

# Display progress
echo "==============================================="
echo "Starting TG Portal backend setup"
echo "==============================================="

# Define app directory explicitly to avoid empty path issues
APP_DIR=${APP_DIR:-"/home/$USER/tgportal"}
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
echo "[3/6] Setting up application directory..."
mkdir -p "$APP_DIR"

# Copy files from the cloned repository to the application directory
echo "Copying files from repository to $APP_DIR"
rsync -a . "$APP_DIR/" --exclude '.git' --exclude '__pycache__' --exclude '*.pyc'
cd "$APP_DIR"

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
VENV_PATH=$(poetry env info --path)
echo "Virtual environment created at: $VENV_PATH"

# Activate the virtual environment
echo "Activating virtual environment..."
source "$VENV_PATH/bin/activate" || {
  echo "Failed to activate virtual environment. Trying alternative approach..."
  if [ -f "$VENV_PATH/bin/activate" ]; then
    . "$VENV_PATH/bin/activate"
  else
    echo "ERROR: Could not activate virtual environment. Will continue with system Python."
  fi
}


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


# Update supervisor configuration to use the virtual environment
echo "Updating supervisor configuration to use Poetry virtual environment..."
# First, backup the original config
cp tgportal.conf tgportal.conf.bak

# Update the command in the supervisor config to use the virtual environment
sed -i "s|command=.*|command=$VENV_PATH/bin/poetry run app|" tgportal.conf
# Also update the environment to include the virtual environment's path
sed -i "s|environment=.*|environment=PYTHONPATH=\"$APP_DIR\",PATH=\"$VENV_PATH/bin:/home/$USER/.local/bin:/usr/local/bin:/usr/bin:/bin\",VIRTUAL_ENV=\"$VENV_PATH\"|" tgportal.conf

# Copy environment file
cp /tmp/config/.env.prod .env
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
echo "Running migrations with Poetry in virtual environment..."
if [ -n "$VENV_PATH" ] && [ -f "$VENV_PATH/bin/alembic" ]; then
  "$VENV_PATH/bin/alembic" upgrade head
else
  echo "Trying with Poetry run command..."
  poetry run alembic upgrade head || {
    echo "WARNING: Poetry migration failed. Trying direct alembic command..."
    if command -v alembic &> /dev/null; then
      alembic upgrade head || echo "WARNING: Alembic migrations failed. You may need to run them manually."
    else
      echo "WARNING: Alembic not found. You may need to run migrations manually."
    fi
  }
fi

echo "==============================================="
echo "Setup completed successfully!"
echo "==============================================="
