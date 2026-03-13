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

# Azure deployment script for NeuroSan Container Apps
# Usage: ./deploy.sh [resource-group] [acr-name]

set -euo pipefail

# Configuration
RESOURCE_GROUP="${1:-rg-neurosan}"
ACR_NAME="${2:-ailabneurosan}"
LOCATION="${LOCATION:-eastus}"
ENVIRONMENT="${ENVIRONMENT:-production}"
PROJECT_NAME="neurosan-app"
DEPLOYMENT_NAME="${PROJECT_NAME}-deployment-$(date +%s)"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}NeuroSan Azure Container Apps Deployment${NC}"
echo "================================================"
echo "Resource Group: $RESOURCE_GROUP"
echo "ACR Name: $ACR_NAME"
echo "Location: $LOCATION"
echo "Deployment Name: $DEPLOYMENT_NAME"
echo ""

# Function to check if Azure CLI is installed
check_azure_cli() {
    if ! command -v az &> /dev/null; then
        echo -e "${RED}Azure CLI is not installed. Please install it first.${NC}"
        exit 1
    fi
    echo -e "${GREEN}✓ Azure CLI found${NC}"
}

# Function to check if user is logged in to Azure
check_azure_login() {
    if ! az account show &> /dev/null; then
        echo -e "${YELLOW}Not logged in to Azure. Running 'az login'...${NC}"
        az login
    fi
    echo -e "${GREEN}✓ Logged in to Azure${NC}"
}

# Function to create resource group if it doesn't exist
create_resource_group() {
    if az group exists --name "$RESOURCE_GROUP" | grep -q "true"; then
        echo -e "${GREEN}✓ Resource group '$RESOURCE_GROUP' already exists${NC}"
    else
        echo "Creating resource group '$RESOURCE_GROUP'..."
        az group create \
            --name "$RESOURCE_GROUP" \
            --location "$LOCATION"
        echo -e "${GREEN}✓ Resource group created${NC}"
    fi
}

# Function to get ACR credentials
get_acr_credentials() {
    echo "Retrieving ACR credentials..."

    ACR_URL=$(az acr show \
        --resource-group "$RESOURCE_GROUP" \
        --name "$ACR_NAME" \
        --query loginServer \
        --output tsv)

    ACR_USERNAME=$(az acr credential show \
        --resource-group "$RESOURCE_GROUP" \
        --name "$ACR_NAME" \
        --query "username" \
        --output tsv)

    ACR_PASSWORD=$(az acr credential show \
        --resource-group "$RESOURCE_GROUP" \
        --name "$ACR_NAME" \
        --query "passwords[0].value" \
        --output tsv)

    echo -e "${GREEN}✓ ACR credentials retrieved${NC}"
}

# Function to validate and get API keys from user
get_api_keys() {
    echo ""
    echo -e "${YELLOW}API Key Configuration${NC}"
    echo "======================================"
    echo "You can optionally provide API keys for various LLM providers."
    echo "Note: Users can also supply keys at request time via HTTP headers."
    echo ""

    # Check for environment variables
    OPENAI_KEY="${OPENAI_API_KEY:-}"
    ANTHROPIC_KEY="${ANTHROPIC_API_KEY:-}"
    AZURE_OPENAI_KEY="${AZURE_OPENAI_API_KEY:-}"
    AZURE_ENDPOINT="${AZURE_OPENAI_ENDPOINT:-}"

    if [ -z "$OPENAI_KEY" ]; then
        read -rsp "OpenAI API Key (leave blank to skip): " OPENAI_KEY
        echo ""
    else
        echo "OpenAI API Key: (from environment variable)"
    fi

    if [ -z "$ANTHROPIC_KEY" ]; then
        read -rsp "Anthropic API Key (leave blank to skip): " ANTHROPIC_KEY
        echo ""
    else
        echo "Anthropic API Key: (from environment variable)"
    fi

    if [ -z "$AZURE_OPENAI_KEY" ]; then
        read -rsp "Azure OpenAI API Key (leave blank to skip): " AZURE_OPENAI_KEY
        echo ""
    else
        echo "Azure OpenAI API Key: (from environment variable)"
    fi

    if [ -z "$AZURE_ENDPOINT" ]; then
        read -p "Azure OpenAI Endpoint (leave blank to skip): " AZURE_ENDPOINT
    else
        echo "Azure OpenAI Endpoint: $AZURE_ENDPOINT"
    fi
}

# Function to deploy using Bicep
deploy_bicep() {
    echo ""
    echo -e "${YELLOW}Deploying NeuroSan using Bicep...${NC}"

    CONTAINER_IMAGE="${ACR_URL}/neuro-san:latest"

    az deployment group create \
        --name "$DEPLOYMENT_NAME" \
        --resource-group "$RESOURCE_GROUP" \
        --template-file "./deploy/azure/main.bicep" \
        --parameters \
            location="$LOCATION" \
            environmentName="$ENVIRONMENT" \
            projectName="$PROJECT_NAME" \
            containerImage="$CONTAINER_IMAGE" \
            containerRegistryUrl="$ACR_URL" \
            containerRegistryUserName="$ACR_USERNAME" \
            containerRegistryPassword="$ACR_PASSWORD" \
            openaiApiKey="${OPENAI_KEY}" \
            anthropicApiKey="${ANTHROPIC_KEY}" \
            azureOpenaiApiKey="${AZURE_OPENAI_KEY}" \
            azureOpenaiEndpoint="${AZURE_ENDPOINT}"

    echo -e "${GREEN}✓ Deployment completed${NC}"
}

# Function to get container app details
show_deployment_info() {
    echo ""
    echo -e "${GREEN}================================================${NC}"
    echo -e "${GREEN}Deployment Information${NC}"
    echo -e "${GREEN}================================================${NC}"

    APP_NAME="${PROJECT_NAME}-app-${ENVIRONMENT}"

    FQDN=$(az containerapp show \
        --resource-group "$RESOURCE_GROUP" \
        --name "$APP_NAME" \
        --query "properties.configuration.ingress.fqdn" \
        --output tsv 2>/dev/null || echo "N/A")

    APP_URL="https://${FQDN}"

    echo -e "Container App URL: ${GREEN}${APP_URL}${NC}"
    echo -e "Resource Group: $RESOURCE_GROUP"
    echo -e "Container App Name: $APP_NAME"
    echo ""
    echo -e "${YELLOW}Next Steps:${NC}"
    echo "1. Test the deployment with: curl ${APP_URL}/health"
    echo "2. To make requests with your API keys, use the X-OpenAI-Api-Key header:"
    echo "   curl -H 'X-OpenAI-Api-Key: sk-...' ${APP_URL}/agents"
    echo ""
}

# Main execution
main() {
    check_azure_cli
    check_azure_login
    create_resource_group
    get_acr_credentials
    get_api_keys
    deploy_bicep
    show_deployment_info
}

main "$@"
