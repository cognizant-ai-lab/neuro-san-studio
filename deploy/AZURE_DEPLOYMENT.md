# NeuroSan Azure Deployment Guide

This guide provides comprehensive instructions for containerizing and deploying NeuroSan on Azure Container Apps with support for user-provided LLM API keys at runtime.

## Table of Contents

- [Architecture](#architecture)
- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Configuration](#configuration)
- [Deployment Options](#deployment-options)
- [Using the API](#using-the-api)
- [API Key Management](#api-key-management)
- [Monitoring and Troubleshooting](#monitoring-and-troubleshooting)
- [Production Best Practices](#production-best-practices)

## Architecture

The deployment consists of two main components running in Azure Container Apps:

### 1. NeuroSan Server
- **Port**: 8080 (HTTP)
- **Purpose**: Core agent engine running NeuroSan agent networks
- **Environment Variables**: Accepts LLM provider credentials and configuration

### 2. API Gateway (FastAPI)
- **Port**: 9000 (HTTP, fronted by Azure's HTTPS ingress)
- **Purpose**: Per-request API key injection middleware
- **Features**:
  - Extracts API keys from HTTP headers
  - Injects keys as environment variables for the NeuroSan server
  - Routes requests without storing or logging user credentials
  - Supports multiple LLM providers (OpenAI, Anthropic, Azure OpenAI, Google, etc.)

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                        End User                             │
│    (Provides API Key via HTTP Header)                       │
└─────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│            Azure Container Apps (HTTPS)                     │
│         Public FQDN with Auto-managed TLS                   │
└─────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│              API Gateway (FastAPI)                          │
│         • Extracts API keys from headers                    │
│         • Validates and injects credentials                 │
│         • Routes to NeuroSan server                         │
└─────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│              NeuroSan Server                                │
│         • Runs agent networks                              │
│         • Uses injected API keys                           │
│         • Manages agent sessions                           │
└─────────────────────────────────────────────────────────────┘
```

## Prerequisites

### Local Development
- Docker 20.10+
- Docker Compose (optional)
- Python 3.12+
- Git

### Azure Deployment
- Azure Account with active subscription
- Azure CLI 2.50+
- Resource Group created or permissions to create one
- Azure Container Registry (ACR) instance
- Service Principal with appropriate RBAC roles (Contributor or custom)

### GitHub Actions Deployment
- GitHub repository with secrets configured (see [CI/CD Setup](#cicd-setup))

## Quick Start

### Option 1: Local Development with Docker

```bash
# Build the Docker image locally
./deploy/build.sh

# Run the container with your API keys
docker run -it \
  -e OPENAI_API_KEY="sk-..." \
  -e ANTHROPIC_API_KEY="sk-ant-..." \
  -p 8080:8080 \
  -p 9000:9000 \
  neuro-san/neuro-san-studio:0.0.1

# Test the deployment
curl http://localhost:9000/health
curl -H "X-OpenAI-Api-Key: sk-..." \
     http://localhost:9000/agents
```

### Option 2: Azure Deployment with CLI

```bash
# 1. Set up your environment
export AZURE_SUBSCRIPTION_ID="<subscription-id>"
export RESOURCE_GROUP="neuro-san-rg"
export ACR_NAME="neurosanadministration"

# 2. Make the deployment script executable
chmod +x deploy/azure/deploy.sh

# 3. Run the deployment (will prompt for API keys)
./deploy/azure/deploy.sh "$RESOURCE_GROUP" "$ACR_NAME"

# 3b. Alternative: Provide API keys via environment variables
export OPENAI_API_KEY="sk-..."
export ANTHROPIC_API_KEY="sk-ant-..."
./deploy/azure/deploy.sh "$RESOURCE_GROUP" "$ACR_NAME"
```

### Option 3: Azure Deployment with GitHub Actions

```bash
# 1. Configure GitHub Secrets (see section below)
# 2. Push to main branch, deployment triggers automatically
git push origin main
```

## Configuration

### Environment Variables

#### NeuroSan Server (port 8080)

| Variable | Default | Description |
|----------|---------|-------------|
| `NEURO_SAN_SERVER_HOST` | `localhost` | Server bind address |
| `NEURO_SAN_SERVER_HTTP_PORT` | `8080` | HTTP port |
| `LOG_LEVEL` | `INFO` | Logging level (DEBUG, INFO, WARNING, ERROR) |
| `AGENT_HTTP_SERVER_INSTANCES` | `1` | Number of worker processes |
| `AGENT_MAX_CONCURRENT_REQUESTS` | `50` | Max concurrent requests |
| `AGENT_MCP_ENABLE` | `true` | Enable MCP protocol |

#### API Gateway (port 9000)

| Variable | Default | Description |
|----------|---------|-------------|
| `NEURO_SAN_HOST` | `localhost` | NeuroSan server address |
| `NEURO_SAN_PORT` | `8080` | NeuroSan server port |
| `API_GATEWAY_HOST` | `0.0.0.0` | Gateway bind address |
| `API_GATEWAY_PORT` | `9000` | Gateway HTTP port |
| `REQUEST_TIMEOUT` | `300` | Request timeout in seconds |
| `LOG_LEVEL` | `INFO` | Logging level |

#### LLM Provider Credentials

These can be:
1. **Set in container environment** (not recommended for production)
2. **Injected per-request via HTTP headers** (recommended)
3. **Stored in Azure Key Vault** (production best practice)

Supported headers:
- `X-OpenAI-Api-Key`: OpenAI API key
- `X-Anthropic-Api-Key`: Anthropic API key
- `X-Azure-OpenAI-Api-Key`: Azure OpenAI API key
- `X-Azure-OpenAI-Endpoint`: Azure OpenAI endpoint URL
- `X-Google-Api-Key`: Google Gemini API key
- `X-AWS-Access-Key`: AWS access key ID
- `X-AWS-Secret-Key`: AWS secret access key
- `X-Nvidia-Api-Key`: NVIDIA API key
- `Authorization: Bearer <key>`: Generic bearer token (defaults to OpenAI)

## Deployment Options

### Option A: Azure CLI Deployment

```bash
# Prerequisites: Log in to Azure
az login

# Variables
RESOURCE_GROUP="neuro-san-rg"
LOCATION="eastus"
ACR_NAME="neurosanadministration"

# 1. Create or verify resource group
az group create \
  --name "$RESOURCE_GROUP" \
  --location "$LOCATION"

# 2. Get ACR credentials
ACR_URL=$(az acr show \
  --resource-group "$RESOURCE_GROUP" \
  --name "$ACR_NAME" \
  --query loginServer -o tsv)

ACR_USERNAME=$(az acr credential show \
  --resource-group "$RESOURCE_GROUP" \
  --name "$ACR_NAME" \
  --query "username" -o tsv)

ACR_PASSWORD=$(az acr credential show \
  --resource-group "$RESOURCE_GROUP" \
  --name "$ACR_NAME" \
  --query "passwords[0].value" -o tsv)

# 3. Deploy using Bicep
az deployment group create \
  --name neuro-san-deployment-$(date +%s) \
  --resource-group "$RESOURCE_GROUP" \
  --template-file "deploy/azure/main.bicep" \
  --parameters \
    location="$LOCATION" \
    environmentName="production" \
    projectName="neuro-san" \
    containerImage="${ACR_URL}/neuro-san:latest" \
    containerRegistryUrl="$ACR_URL" \
    containerRegistryUserName="$ACR_USERNAME" \
    containerRegistryPassword="$ACR_PASSWORD" \
    openaiApiKey="${OPENAI_API_KEY:-}" \
    anthropicApiKey="${ANTHROPIC_API_KEY:-}" \
    azureOpenaiApiKey="${AZURE_OPENAI_API_KEY:-}"

# 4. Get the deployment URL
APP_URL=$(az containerapp show \
  --resource-group "$RESOURCE_GROUP" \
  --name "neuro-san-app-production" \
  --query "properties.configuration.ingress.fqdn" -o tsv)

echo "Deployment URL: https://${APP_URL}"
```

### Option B: GitHub Actions CI/CD

#### Step 1: Configure GitHub Secrets

Go to **Settings > Secrets and variables > Actions** and add:

```
AZURE_CLIENT_ID              # Service Principal Client ID
AZURE_TENANT_ID              # Azure Tenant ID
AZURE_SUBSCRIPTION_ID        # Azure Subscription ID
ACR_USERNAME                 # Azure Container Registry username
ACR_PASSWORD                 # Azure Container Registry password
OPENAI_API_KEY              # (Optional) Default OpenAI key
ANTHROPIC_API_KEY           # (Optional) Default Anthropic key
AZURE_OPENAI_API_KEY        # (Optional) Default Azure OpenAI key
AZURE_OPENAI_ENDPOINT       # (Optional) Azure OpenAI endpoint
```

#### Step 2: Authentication Setup

Create an Azure Service Principal for GitHub Actions:

```bash
# Create service principal
az ad sp create-for-rbac \
  --name "github-neuro-san-deployer" \
  --role "Contributor" \
  --scopes "/subscriptions/<subscription-id>"

# Output will show:
# {
#   "clientId": "...",
#   "clientSecret": "...",
#   "subscriptionId": "...",
#   "tenantId": "..."
# }

# Add to GitHub Secrets as:
# AZURE_CLIENT_ID = clientId
# AZURE_TENANT_ID = tenantId
# AZURE_SUBSCRIPTION_ID = subscriptionId
```

#### Step 3: Trigger Deployment

```bash
# Push to main branch
git add .
git commit -m "Deploy NeuroSan to Azure"
git push origin main

# Monitor deployment
# GitHub Actions will build, scan, and deploy automatically
# Check Actions tab for progress
```

## Using the API

### Health Check

```bash
curl https://<deployment-url>/health

# Response:
# {
#   "status": "healthy",
#   "service": "NeuroSan API Gateway",
#   "version": "1.0.0"
# }
```

### Get Version Info

```bash
curl https://<deployment-url>/version

# Response:
# {
#   "version": "1.0.0",
#   "neuro_san_endpoint": "http://localhost:8080"
# }
```

### Make an Agent Request with OpenAI

```bash
curl -X POST \
  -H "Content-Type: application/json" \
  -H "X-OpenAI-Api-Key: sk-..." \
  -d '{
    "agent": "your_agent_name",
    "prompt": "What is machine learning?"
  }' \
  https://<deployment-url>/agents
```

### Make an Agent Request with Anthropic

```bash
curl -X POST \
  -H "Content-Type: application/json" \
  -H "X-Anthropic-Api-Key: sk-ant-..." \
  -d '{
    "agent": "your_agent_name",
    "prompt": "What is machine learning?"
  }' \
  https://<deployment-url>/agents
```

### Make an Agent Request with Azure OpenAI

```bash
curl -X POST \
  -H "Content-Type: application/json" \
  -H "X-Azure-OpenAI-Api-Key: your-key" \
  -H "X-Azure-OpenAI-Endpoint: https://your-resource.openai.azure.com/" \
  -d '{
    "agent": "your_agent_name",
    "prompt": "What is machine learning?"
  }' \
  https://<deployment-url>/agents
```

### Using Authorization Header

```bash
curl -X POST \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer sk-..." \
  -d '{
    "agent": "your_agent_name",
    "prompt": "What is machine learning?"
  }' \
  https://<deployment-url>/agents
```

## API Key Management

### Security Best Practices

1. **Never commit API keys to version control**
   - Use environment variables and secrets management
   - Use `.gitignore` for `.env` files

2. **Use per-request API key injection**
   - Send keys in request headers, not in request body
   - Keys are never logged or persisted
   - Different users can use different API keys

3. **Implement request authentication**
   - Add JWT or API key authentication to the gateway
   - Rate limit by user/API key
   - Monitor usage per user

4. **Use Azure Key Vault**
   ```bash
   # Store secrets in Key Vault
   az keyvault secret set \
     --vault-name "neuro-san-vault" \
     --name "openai-api-key" \
     --value "sk-..."

   # Reference in deployment (requires managed identity)
   ```

5. **Enable audit logging**
   - Log all requests (without keys)
   - Monitor for unusual patterns
   - Set up alerts for failures

### Rotating API Keys

```bash
# 1. Update the secret in your management system
# 2. For Azure Key Vault:
az keyvault secret set \
  --vault-name "neuro-san-vault" \
  --name "openai-api-key" \
  --value "sk-new-key"

# 3. Container App will pick up the change on next restart/rollout
# 4. For seamless rotation, users should pass keys per-request
```

## Monitoring and Troubleshooting

### View Container Logs

```bash
# View real-time logs
az containerapp logs show \
  --name "neuro-san-app-production" \
  --resource-group "neuro-san-rg" \
  --follow

# View API Gateway logs
az containerapp logs show \
  --name "neuro-san-app-production" \
  --resource-group "neuro-san-rg" \
  --container "api-gateway" \
  --follow
```

### Common Issues

#### 502 Bad Gateway

**Cause**: API Gateway can't reach NeuroSan server

**Solution**:
```bash
# Check container logs
az containerapp logs show \
  --name "neuro-san-app-production" \
  --resource-group "neuro-san-rg"

# Verify service is running
curl http://localhost:8080/health  # From within container
```

#### 401 Unauthorized

**Cause**: Missing or invalid API key

**Solution**:
```bash
# Verify API key format and header name
curl -v \
  -H "X-OpenAI-Api-Key: sk-..." \
  https://<deployment-url>/health

# Check API key is valid with the provider
```

#### Container Won't Start

**Cause**: Missing environment variables or dependency issues

**Solution**:
```bash
# Check deployment parameters
az deployment group show \
  --resource-group "neuro-san-rg" \
  --name "neuro-san-deployment-<timestamp>"

# Verify Azure Container Registry image exists
az acr repository show \
  --resource-group "neuro-san-rg" \
  --name "neurosanadministration" \
  --repository "neuro-san"
```

### Performance Tuning

```bash
# Increase container resources and scale
az deployment group create \
  --resource-group "neuro-san-rg" \
  --template-file "deploy/azure/main.bicep" \
  --parameters \
    cpuCores="4" \
    memoryGb="8" \
    minReplicas="2" \
    maxReplicas="10"
```

## Production Best Practices

### 1. Infrastructure

- **Use Azure Container Apps** for managed container orchestration
- **Enable Application Insights** for monitoring
- **Use Azure Front Door** or **Application Gateway** for DDoS protection
- **Enable VNet integration** if data residency is critical

### 2. API Key Management

- Store keys in **Azure Key Vault**
- Use **Managed Identities** for authentication
- Implement **API key rotation** policies
- Log all API calls (without sensitive data)

### 3. Scaling

```bash
# Configure auto-scaling based on CPU and memory
az deployment group create \
  --resource-group "neuro-san-rg" \
  --template-file "deploy/azure/main.bicep" \
  --parameters \
    minReplicas="2" \
    maxReplicas="20"
```

### 4. Security

- Enable **Azure WAF** on Application Gateway
- Implement **request authentication** (JWT token validation)
- Use **TLS 1.3** for all connections
- Enable **Azure Policy** for compliance

### 5. Monitoring & Alerting

```bash
# Create action group for alerts
az monitor action-group create \
  --resource-group "neuro-san-rg" \
  --name "neuro-san-alerts"

# Create metric alert for CPU > 80%
az monitor metrics alert create \
  --resource-group "neuro-san-rg" \
  --name "high-cpu-alert" \
  --scopes "/subscriptions/<sub-id>/resourceGroups/neuro-san-rg/providers/Microsoft.App/containerApps/neuro-san-app-production" \
  --condition "avg Percentage CPU > 80" \
  --action "neuro-san-alerts"
```

### 6. Cost Optimization

- Use **Azure Reserved Instances** for predictable workloads
- Implement **scheduled scaling** for off-peak hours
- Monitor and optimize **container image size**
- Use **spot containers** for non-critical workloads

## Advanced Configuration

### Custom LLM Provider Support

To add support for additional providers, modify `middleware/api_gateway.py`:

```python
# In APIKeyInjector.HEADER_TO_ENV_MAP, add:
"x-custom-provider-key": "CUSTOM_PROVIDER_API_KEY"
```

### Multi-Tenant Setup

```bash
# Deploy with different agent manifests for different tenants
az deployment group create \
  --parameters \
    agentManifestFile="/path/to/tenant-specific/manifest.hocon"
```

### Custom Logging Format

Edit `deploy/logging.hocon` to customize log output format and destination.

## Support & Resources

- **NeuroSan Documentation**: https://github.com/cognizant-ai-lab/neuro-san
- **Azure Container Apps Docs**: https://learn.microsoft.com/en-us/azure/container-apps/
- **GitHub Actions Docs**: https://docs.github.com/en/actions
- **FastAPI Docs**: https://fastapi.tiangolo.com/

## License

Copyright © 2025 Cognizant Technology Solutions Corp
Licensed under the Apache License, Version 2.0
