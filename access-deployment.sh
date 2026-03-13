#!/bin/bash
# Quick access to your NeuroSan deployment

set -euo pipefail

RG="rg-neurosan"
APP="neurosan-app-app-production"

echo "=========================================="
echo "NeuroSan Azure Deployment Access"
echo "=========================================="
echo ""

# Get URL
echo "🔍 Getting deployment URL..."
FQDN=$(az containerapp show -g "$RG" -n "$APP" --query "properties.configuration.ingress.fqdn" -o tsv 2>/dev/null || echo "not-deployed")

if [ "$FQDN" == "not-deployed" ]; then
  echo "❌ Container app not found. Deploy first!"
  echo ""
  echo "Deploy with:"
  echo "  git push fork feature/azure-deployment"
  exit 1
fi

URL="https://${FQDN}"

echo "✅ Public URL: $URL"
echo ""

# Test health
echo "🏥 Testing health endpoint..."
if curl -sf "$URL/health" > /dev/null 2>&1; then
  echo "✅ Service is healthy"
  curl "$URL/health" | jq .
else
  echo "⚠️  Service may still be starting..."
fi
echo ""

# Show usage
echo "=========================================="
echo "📋 Usage Examples"
echo "=========================================="
echo ""

echo "1️⃣  Health Check:"
echo "   curl $URL/health"
echo ""

echo "2️⃣  Get Version:"
echo "   curl $URL/version"
echo ""

echo "3️⃣  Call with OpenAI:"
echo "   curl -X POST -H 'X-OpenAI-Api-Key: sk-...' \\"
echo "     -H 'Content-Type: application/json' \\"
echo "     -d '{\"agent\": \"my_agent\", \"prompt\": \"hello\"}' \\"
echo "     $URL/agents"
echo ""

echo "4️⃣  Call with Anthropic:"
echo "   curl -X POST -H 'X-Anthropic-Api-Key: sk-ant-...' \\"
echo "     -H 'Content-Type: application/json' \\"
echo "     -d '{\"agent\": \"my_agent\", \"prompt\": \"hello\"}' \\"
echo "     $URL/agents"
echo ""

echo "5️⃣  View Real-time Logs:"
echo "   az containerapp logs show -g $RG -n $APP --container neuro-san --follow"
echo ""

echo "=========================================="
echo "🎯 Your deployment is ready!"
echo "=========================================="
