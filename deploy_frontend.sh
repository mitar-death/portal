#!/bin/bash
# filepath: /Users/mazibuckler/apps/tgportal/deploy_frontend.sh

set -e  # Exit on any error

# Colors for terminal output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Load environment variables from .env file if it exists
if [ -f ".env.production" ]; then
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

export NODE_ENV="production"


echo -e "${GREEN}Building and deploying TG Portal frontend${NC}"

# Navigate to the client directory which is the root directory
cd "$(dirname "$0")"

# Check node version
if ! command -v node &> /dev/null; then
  echo "Node.js version:"
  node -v
  echo -e "${YELLOW}Node.js is not installed. Please install Node.js and try again.${NC}"
  exit 1
fi

# Install dependencies if needed
if [ ! -d "node_modules" ]; then
  echo -e "${YELLOW}Installing frontend dependencies...${NC}"
  yarn install
fi

# Check if Vue CLI is installed and install if needed
if ! yarn global list | grep -q @vue/cli; then
  echo -e "${YELLOW}Installing Vue CLI globally...${NC}"
  yarn global add @vue/cli
fi

# Build the production version of the frontend
echo -e "${YELLOW}Building Vue.js application...${NC}"
yarn build

# Check if the build directory exists
if [ ! -d "dist" ]; then
  echo -e "${YELLOW}Build failed or output directory is not 'dist'. Please check your Vue configuration.${NC}"
  exit 1
fi

# Check if Firebase CLI is installed
if ! command -v firebase &> /dev/null; then
  echo -e "${YELLOW}Installing Firebase CLI...${NC}"
  yarn global add firebase-tools
fi

# Initialize Firebase if not already set up
if [ ! -f "firebase.json" ]; then
  echo -e "${YELLOW}Initializing Firebase...${NC}"
  firebase login
  
  # Interactive Firebase init
  echo -e "${YELLOW}Running Firebase init - select Hosting and follow the prompts${NC}"
  echo -e "${YELLOW}When asked for the public directory, enter 'dist'${NC}"
  echo -e "${YELLOW}Configure as a single-page app? Answer 'yes'${NC}"
  firebase init hosting
else
  # Update existing firebase.json to ensure it points to the correct build directory
  echo -e "${YELLOW}Updating Firebase configuration...${NC}"
  cat > firebase.json << EOL
{
  "hosting": {
    "public": "dist",
    "ignore": [
      "firebase.json",
      "**/.*",
      "**/node_modules/**"
    ],
    "rewrites": [
      {
        "source": "**",
        "destination": "/index.html"
      }
    ]
  }
}
EOL
fi

# Create .firebaserc if it doesn't exist
if [ ! -f ".firebaserc" ]; then
  echo -e "${YELLOW}Setting up Firebase project...${NC}"
  echo "What is your Firebase project ID?"
  read PROJECT_ID
  
  cat > .firebaserc << EOL
{
  "projects": {
    "default": "$FIREBASE_PROJECT_ID"
  }
}
EOL
fi

# Deploy to Firebase
echo -e "${YELLOW}Deploying to Firebase...${NC}"
firebase deploy --only hosting

echo -e "${GREEN}Deployment complete! Your app should be live.${NC}"
echo -e "${GREEN}If you need to set up API URLs, make sure to create a .env.production file with:${NC}"
echo -e "${YELLOW}VUE_APP_API_URL=$BACKEND_URL/api${NC}" #backend URL from .env
echo -e "${YELLOW}VUE_APP_FIREBASE_PROJECT_ID=$FIREBASE_PROJECT_ID${NC}" #firebase project ID from .env