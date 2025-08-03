#!/bin/bash
set -e  # Exit on any error

# Colors for terminal output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Get domain from environment variable or argument
CUSTOM_DOMAIN=${1:-$CUSTOM_DOMAIN}
EMAIL=${2:-"admin@$CUSTOM_DOMAIN"}

if [ -z "$CUSTOM_DOMAIN" ]; then
  echo -e "${RED}Error: No domain specified. Usage: $0 <domain> [email]${NC}"
  exit 1
fi

echo -e "${GREEN}Setting up HTTPS for domain: $CUSTOM_DOMAIN${NC}"
echo -e "${YELLOW}Using email: $EMAIL for Let's Encrypt notifications${NC}"

# Check if Nginx is installed
if ! command -v nginx &> /dev/null; then
  echo -e "${YELLOW}Installing Nginx...${NC}"
  sudo apt-get update
  sudo apt-get install -y nginx
fi

# Check if Certbot is installed
if ! command -v certbot &> /dev/null; then
  echo -e "${YELLOW}Installing Certbot and Nginx plugin...${NC}"
  sudo apt-get update
  sudo apt-get install -y certbot python3-certbot-nginx
fi

# Configure Nginx for the domain
echo -e "${GREEN}Configuring Nginx for domain: $CUSTOM_DOMAIN${NC}"
sudo tee /etc/nginx/sites-available/tgportal > /dev/null << EOL
server {
    listen 80;
    server_name $CUSTOM_DOMAIN;

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
