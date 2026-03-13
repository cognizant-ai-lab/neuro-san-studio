#!/bin/bash
# Copyright © 2025 Cognizant Technology Solutions Corp, www.cognizant.com.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# END COPYRIGHT

# Quick setup script for NeuroSan Azure deployment prerequisites
# This script helps set up all the necessary Azure resources

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
PROJECT_NAME="neurosan-app"
ENVIRONMENT="${ENVIRONMENT:-production}"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}NeuroSan Azure Setup${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Function to print section headers
print_section() {
    echo -e "${YELLOW}$1${NC}"
    echo "---"
}

# Function to check if command exists
command_exists() {
    command -v "$1" &> /dev/null
}

# Check prerequisites
print_section "1. Checking Prerequisites"

if ! command_exists az; then
    echo -e "${RED}✗ Azure CLI not found. Install from: https://learn.microsoft.com/en-us/cli/azure/install-azure-cli${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Azure CLI found${NC}"

if ! command_exists docker; then
    echo -e "${RED}✗ Docker not found. Install from: https://www.docker.com/products/docker-desktop${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Docker found${NC}"

# Check Azure login
print_section "2. Azure Authentication"

if ! az account show &> /dev/null; then
    echo "Logging in to Azure..."
    az login
fi

ACCOUNT=$(az account show --query "user.name" -o tsv)
SUBSCRIPTION=$(az account show --query "id" -o tsv)
SUBSCRIPTION_NAME=$(az account show --query "name" -o tsv)

echo -e "${GREEN}✓ Logged in as: $ACCOUNT${NC}"
echo -e "${GREEN}✓ Subscription: $SUBSCRIPTION_NAME ($SUBSCRIPTION)${NC}"

# Create resource group
print_section "3. Creating Resource Group"

RESOURCE_GROUP="rg-neurosan"
LOCATION="${LOCATION:-eastus}"

if az group exists -n "$RESOURCE_GROUP" | grep -q "true"; then
    echo -e "${GREEN}✓ Resource group '$RESOURCE_GROUP' already exists${NC}"
else
    echo "Resource group '$RESOURCE_GROUP' does not exist. Please create it first or run with your RG name."
    echo "You can create it with: az group create -n $RESOURCE_GROUP -l $LOCATION"
    exit 1
fi

# Create or verify Azure Container Registry
print_section "4. Setting up Azure Container Registry (ACR)"

ACR_NAME="ailabneurosan"

if az acr show --resource-group "$RESOURCE_GROUP" --name "$ACR_NAME" &> /dev/null; then
    echo -e "${GREEN}✓ ACR '$ACR_NAME' found in resource group '$RESOURCE_GROUP'${NC}"
else
    echo -e "${RED}✗ ACR '$ACR_NAME' not found in resource group '$RESOURCE_GROUP'${NC}"
    echo "Please verify your ACR name and resource group."
    exit 1
fi

ACR_LOGIN_SERVER=$(az acr show \
    --resource-group "$RESOURCE_GROUP" \
    --name "$ACR_NAME" \
    --query loginServer -o tsv)

echo -e "${GREEN}✓ ACR Login Server: $ACR_LOGIN_SERVER${NC}"

# Get ACR credentials
ACR_USERNAME=$(az acr credential show \
    --resource-group "$RESOURCE_GROUP" \
    --name "$ACR_NAME" \
    --query "username" -o tsv)

ACR_PASSWORD=$(az acr credential show \
    --resource-group "$RESOURCE_GROUP" \
    --name "$ACR_NAME" \
    --query "passwords[0].value" -o tsv)

# Set up service principal for GitHub Actions
print_section "5. Setting up Service Principal for CI/CD (optional)"

read -p "Create/update service principal for GitHub Actions? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    SP_NAME="github-${PROJECT_NAME}-deployer"

    # Check if SP exists
    if az ad sp list --display-name "$SP_NAME" --query "[0].appId" -o tsv &> /dev/null; then
        echo "Service principal '$SP_NAME' already exists"
        SP_ID=$(az ad sp list --display-name "$SP_NAME" --query "[0].appId" -o tsv)
    else
        echo "Creating service principal '$SP_NAME'..."
        SP_JSON=$(az ad sp create-for-rbac \
            --name "$SP_NAME" \
            --role "Contributor" \
            --scopes "/subscriptions/$SUBSCRIPTION" \
            --output json)
        SP_ID=$(echo "$SP_JSON" | jq -r '.appId')
        echo -e "${GREEN}✓ Service principal created${NC}"
    fi

    TENANT_ID=$(az account show --query "tenantId" -o tsv)

    echo ""
    echo -e "${YELLOW}Add the following secrets to GitHub Actions (Settings > Secrets):${NC}"
    echo "AZURE_CLIENT_ID: $SP_ID"
    echo "AZURE_TENANT_ID: $TENANT_ID"
    echo "AZURE_SUBSCRIPTION_ID: $SUBSCRIPTION"
    echo "ACR_USERNAME: $ACR_USERNAME"
    echo "ACR_PASSWORD: $ACR_PASSWORD"
fi

# Build and push Docker image
print_section "6. Building Docker Image"

read -p "Build and push Docker image to ACR now? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "Logging in to ACR..."
    az acr login --name "$ACR_NAME"

    echo "Building Docker image..."
    docker build -t "${ACR_LOGIN_SERVER}/${PROJECT_NAME}:latest" -f deploy/Dockerfile .
    echo -e "${GREEN}✓ Image built${NC}"

    echo "Pushing image to ACR..."
    docker push "${ACR_LOGIN_SERVER}/${PROJECT_NAME}:latest"
    echo -e "${GREEN}✓ Image pushed${NC}"
fi

# Deploy to Azure Container Apps
print_section "7. Deploying to Azure Container Apps"

read -p "Deploy to Azure Container Apps now? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    chmod +x deploy/azure/deploy.sh
    deploy/azure/deploy.sh "$RESOURCE_GROUP" "$ACR_NAME"
fi

# Print summary
print_section "Setup Complete!"

echo ""
echo -e "${GREEN}Summary:${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "Resource Group: ${BLUE}$RESOURCE_GROUP${NC}"
echo -e "Location: ${BLUE}$LOCATION${NC}"
echo -e "ACR: ${BLUE}$ACR_LOGIN_SERVER${NC}"
echo -e "Environment: ${BLUE}$ENVIRONMENT${NC}"
echo ""

echo -e "${YELLOW}Next Steps:${NC}"
echo "1. Configure GitHub Actions secrets (if using CI/CD):"
echo "   - Go to Settings > Secrets and Variables > Actions"
echo "   - Add AZURE_CLIENT_ID, AZURE_TENANT_ID, AZURE_SUBSCRIPTION_ID"
echo "   - Add ACR_USERNAME, ACR_PASSWORD"
echo "   - Add any LLM API keys (OPENAI_API_KEY, ANTHROPIC_API_KEY, etc.)"
echo ""
echo "2. Push code to trigger deployment:"
echo "   git add ."
echo "   git commit -m 'Deploy NeuroSan to Azure'"
echo "   git push origin main"
echo ""
echo "3. Or deploy manually:"
echo "   ./deploy/azure/deploy.sh"
echo ""
echo -e "${YELLOW}Useful Commands:${NC}"
echo "View logs: az containerapp logs show -g $RESOURCE_GROUP -n neuro-san-app-$ENVIRONMENT --follow"
echo "Get URL: az containerapp show -g $RESOURCE_GROUP -n neuro-san-app-$ENVIRONMENT --query 'properties.configuration.ingress.fqdn'"
echo ""
