#!/bin/bash
# Azure NeuroSan Deployment Monitoring Script

set -euo pipefail

RESOURCE_GROUP="rg-neurosan"
CONTAINER_APP="neurosan-app-app-production"

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}NeuroSan Azure Deployment Monitor${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Get deployment URL
echo -e "${YELLOW}1. Getting Deployment URL...${NC}"
DEPLOYMENT_URL=$(az containerapp show \
  -g "$RESOURCE_GROUP" \
  -n "$CONTAINER_APP" \
  --query "properties.configuration.ingress.fqdn" -o tsv)
FULL_URL="https://${DEPLOYMENT_URL}"

echo -e "${GREEN}✓ Deployment URL: ${FULL_URL}${NC}"
echo ""

# Check container status
echo -e "${YELLOW}2. Checking Container Status...${NC}"
az containerapp replica list \
  -g "$RESOURCE_GROUP" \
  -n "$CONTAINER_APP" \
  --output table
echo ""

# Test health endpoint
echo -e "${YELLOW}3. Testing Health Check...${NC}"
if curl -sf "${FULL_URL}/health" > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Health check passed${NC}"
else
    echo -e "${YELLOW}⚠ Health check failed - container may still be starting${NC}"
fi
echo ""

# Show deployment info
echo -e "${YELLOW}4. Deployment Information:${NC}"
echo "Resource Group: $RESOURCE_GROUP"
echo "Container App: $CONTAINER_APP"
echo "Public URL: $FULL_URL"
echo ""

# Usage examples
echo -e "${YELLOW}5. Usage Examples:${NC}"
echo ""
echo -e "${BLUE}Test with curl:${NC}"
echo "  # Health check"
echo "  curl $FULL_URL/health"
echo ""
echo "  # With OpenAI key"
echo "  curl -H 'X-OpenAI-Api-Key: sk-...' $FULL_URL/agents"
echo ""
echo "  # With Anthropic key"
echo "  curl -H 'X-Anthropic-Api-Key: sk-ant-...' $FULL_URL/agents"
echo ""

# View logs options
echo -e "${BLUE}View real-time logs:${NC}"
echo "  # NeuroSan server logs"
echo "  az containerapp logs show -g $RESOURCE_GROUP -n $CONTAINER_APP --container neuro-san --follow"
echo ""
echo "  # API Gateway logs"
echo "  az containerapp logs show -g $RESOURCE_GROUP -n $CONTAINER_APP --container api-gateway --follow"
echo ""

# Scale options
echo -e "${BLUE}Scale replicas:${NC}"
echo "  # Increase to 2-5 replicas"
echo "  az containerapp update -g $RESOURCE_GROUP -n $CONTAINER_APP --min-replicas 2 --max-replicas 5"
echo ""

echo -e "${GREEN}Setup complete! You can now use the deployment.${NC}"
