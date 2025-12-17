#!/bin/bash

# TransSRT Cloud Run Function Deployment Script
# This script handles the complete setup and deployment process

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}================================${NC}"
echo -e "${BLUE}TransSRT Deployment Script${NC}"
echo -e "${BLUE}================================${NC}"
echo ""

# Configuration
PROJECT_ID=${GCP_PROJECT_ID:-"transsrt"}
REGION="us-central1"
FUNCTION_NAME="translate-srt"

# Check if gcloud is installed
if ! command -v gcloud &> /dev/null; then
    echo -e "${RED}Error: gcloud CLI is not installed${NC}"
    echo "Install it from: https://cloud.google.com/sdk/docs/install"
    exit 1
fi

echo -e "${GREEN}✓${NC} gcloud CLI found"

# Authenticate
echo -e "\n${YELLOW}Step 1: Authentication${NC}"
echo "Make sure you're logged in to gcloud..."
gcloud auth list

read -p "Continue with current account? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Please run: gcloud auth login"
    exit 1
fi

# Create or select project
echo -e "\n${YELLOW}Step 2: Project Setup${NC}"
echo "Using project: $PROJECT_ID"

# Check if project exists
if gcloud projects describe $PROJECT_ID &> /dev/null; then
    echo -e "${GREEN}✓${NC} Project exists"
else
    echo -e "${YELLOW}Creating project...${NC}"
    gcloud projects create $PROJECT_ID --name="TransSRT"
fi

gcloud config set project $PROJECT_ID

# Enable required APIs
echo -e "\n${YELLOW}Step 3: Enable APIs${NC}"
echo "Enabling required APIs..."

gcloud services enable cloudfunctions.googleapis.com
gcloud services enable cloudbuild.googleapis.com
gcloud services enable secretmanager.googleapis.com
gcloud services enable generativelanguage.googleapis.com

echo -e "${GREEN}✓${NC} APIs enabled"

# Setup Gemini API key
echo -e "\n${YELLOW}Step 4: Gemini API Key Setup${NC}"

# Check if secret exists
if gcloud secrets describe gemini-api-key &> /dev/null; then
    echo -e "${GREEN}✓${NC} Gemini API key secret exists"
    read -p "Update existing API key? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        read -sp "Enter your Gemini API key: " GEMINI_KEY
        echo
        echo "$GEMINI_KEY" | gcloud secrets versions add gemini-api-key --data-file=-
        echo -e "${GREEN}✓${NC} API key updated"
    fi
else
    read -sp "Enter your Gemini API key: " GEMINI_KEY
    echo
    echo "$GEMINI_KEY" | gcloud secrets create gemini-api-key \
        --data-file=- \
        --replication-policy="automatic"
    echo -e "${GREEN}✓${NC} API key stored in Secret Manager"
fi

# Grant function access to secret
echo "Granting function access to secret..."
gcloud secrets add-iam-policy-binding gemini-api-key \
    --member="serviceAccount:$PROJECT_ID@appspot.gserviceaccount.com" \
    --role="roles/secretmanager.secretAccessor" || true

echo -e "${GREEN}✓${NC} Secret access configured"

# Deploy function
echo -e "\n${YELLOW}Step 5: Deploy Cloud Run Function${NC}"
echo "Deploying function to $REGION..."

cd "$(dirname "$0")/.."  # Go to project root

gcloud functions deploy $FUNCTION_NAME \
    --gen2 \
    --runtime python311 \
    --region $REGION \
    --source ./backend \
    --entry-point translate_srt \
    --trigger-http \
    --allow-unauthenticated \
    --memory 512Mi \
    --timeout 300s \
    --max-instances 10 \
    --set-env-vars GEMINI_MODEL=gemini-1.5-flash,CHUNK_SIZE=50,MAX_CONCURRENT_REQUESTS=10,MAX_FILE_SIZE_MB=10,CORS_ORIGINS=* \
    --set-secrets GEMINI_API_KEY=gemini-api-key:latest

echo -e "${GREEN}✓${NC} Function deployed"

# Get function URL
echo -e "\n${YELLOW}Step 6: Get Function URL${NC}"
FUNCTION_URL=$(gcloud functions describe $FUNCTION_NAME \
    --gen2 \
    --region $REGION \
    --format="value(serviceConfig.uri)")

echo -e "${GREEN}Function URL: $FUNCTION_URL${NC}"

# Summary
echo -e "\n${BLUE}================================${NC}"
echo -e "${GREEN}Deployment Complete!${NC}"
echo -e "${BLUE}================================${NC}"
echo ""
echo -e "📍 Region: $REGION (Iowa)"
echo -e "🔗 Function URL: $FUNCTION_URL"
echo -e "💾 Project ID: $PROJECT_ID"
echo ""
echo -e "${YELLOW}Next Steps:${NC}"
echo "1. Update frontend/app.js CONFIG.API_ENDPOINT with the function URL above"
echo "2. Test the function with: curl -X POST -F 'file=@test.srt' $FUNCTION_URL/translate"
echo "3. Deploy frontend to GitHub Pages"
echo ""
echo -e "${YELLOW}Monitor:${NC}"
echo "- Logs: gcloud functions logs read $FUNCTION_NAME --region=$REGION --gen2"
echo "- Metrics: https://console.cloud.google.com/functions/details/$REGION/$FUNCTION_NAME"
echo ""
