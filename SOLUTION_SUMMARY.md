# NeuroSan Azure Deployment Solution

## Solution Overview

This comprehensive solution enables NeuroSan to be deployed as a publicly accessible service on Azure Container Apps with per-request LLM API key injection.

## Files Created

### 1. **API Gateway** (`middleware/api_gateway.py`)
- **Purpose**: FastAPI middleware for per-request API key injection
- **Key Features**:
  - Extracts API keys from HTTP headers (X-OpenAI-Api-Key, X-Anthropic-Api-Key, etc.)
  - Routes requests to NeuroSan server
  - Never logs or persists user credentials
  - Supports multiple LLM providers (OpenAI, Anthropic, Azure OpenAI, Google, AWS, NVIDIA)
  - Async request handling with proper error handling

### 2. **Azure Infrastructure as Code**

#### `deploy/azure/main.bicep`
- Complete Azure Container Apps infrastructure definition
- Provisions:
  - Log Analytics workspace for monitoring
  - Container App environment
  - Two containers (NeuroSan server + API Gateway)
  - Automatic HTTPS with managed TLS
  - Auto-scaling configuration
  - Container registry authentication

#### `deploy/azure/main.bicepparam`
- Parameter file for Bicep template
- Configurable values for location, environment, container specs
- Excludes sensitive API keys (injected at deployment time)

### 3. **Deployment Scripts**

#### `deploy/azure/setup.sh`
- One-time setup wizard for Azure environment
- Creates resource group, ACR, service principal
- Builds and pushes Docker image
- Configures GitHub Actions secrets

#### `deploy/azure/deploy.sh`
- Production deployment script
- Validates Azure CLI and authentication
- Collects API keys securely (interactively or via env vars)
- Deploys using Bicep template
- Displays deployment URL and next steps

### 4. **CI/CD Pipeline** (`.github/workflows/azure-deploy.yml`)
- Triggers on push to main branch
- Multi-stage workflow:
  1. **Build**: Builds and pushes Docker image to ACR
  2. **Security**: Runs Trivy vulnerability scanner
  3. **Deploy**: Deploys to Azure using Bicep
  4. **Verify**: Health checks deployment
- Azure Login with OIDC (no secrets needed)
- Automatic comments on PR deployments

### 5. **Documentation**

#### `deploy/AZURE_DEPLOYMENT.md` (Comprehensive Guide)
- 400+ line deployment guide covering:
  - Architecture overview and diagrams
  - Prerequisites and setup
  - Quick start options (local, CLI, GitHub Actions)
  - Configuration reference for all environment variables
  - API usage examples for each LLM provider
  - API key management best practices
  - Monitoring and troubleshooting
  - Production recommendations

#### `DEPLOYMENT_QUICK_REFERENCE.md`
- Quick reference guide with:
  - Common commands and tasks
  - API call examples
  - GitHub Actions secrets checklist
  - Environment variables reference
  - File structure overview
  - Troubleshooting tips
  - Links to resources

### 6. **Local Development** (`docker-compose.yml`)
- Complete local development environment
- Services:
  - NeuroSan server (port 8080)
  - API Gateway (port 9000)
  - Optional Nginx reverse proxy with HTTPS
- Environment variable configuration
- Health checks and resource limits
- Profile support for optional services

### 7. **Configuration Templates**

#### `.env.local.example`
- Template for local development
- Comprehensive comments explaining each variable
- Organized by category:
  - API Gateway settings
  - NeuroSan configuration
  - LLM provider keys
  - Agent configuration
  - Development settings

### 8. **Dependencies Update** (`requirements.txt`)
- Added FastAPI, Uvicorn, and httpx for API gateway
- Maintained all existing NeuroSan dependencies

## Architecture

```
User Request (with API Key in Header)
    ↓
Azure HTTPS (Public FQDN)
    ↓
API Gateway (FastAPI, Port 9000)
  - Extracts API key from header
  - Validates request
  - Injects key into environment
    ↓
NeuroSan Server (Port 8080)
  - Runs agent networks
  - Uses injected LLM credentials
  - Returns agent response
    ↓
API Gateway
  - Routes response back to user
  - No API key in response
    ↓
User Response (no credentials exposed)
```

## Deployment Flows

### Option 1: GitHub Actions (Recommended Production)
```
git push → GitHub Actions
  ├─ Build Docker image
  ├─ Security scan (Trivy)
  ├─ Push to ACR
  └─ Deploy via Bicep → Azure Container Apps (HTTPS Public URL)
```

### Option 2: Azure CLI
```
./deploy/azure/setup.sh (one-time)
./deploy/azure/deploy.sh (each deployment)
```

### Option 3: Local Development
```
docker-compose up -d
```

## Key Features

✅ **Security**
- Per-request API key injection (users provide keys, never stored)
- API keys extracted from HTTP headers, not request body
- No logging of credentials
- HTTPS enforced by Azure
- Support for Azure Key Vault integration

✅ **Multi-Tenant**
- Each user can supply their own API keys
- No shared secrets required
- Scales to multiple concurrent users

✅ **LLM Agnostic**
- Supports OpenAI, Anthropic, Azure OpenAI, Google, AWS Bedrock, NVIDIA
- Easy to add new providers by modifying header mapping

✅ **Production Ready**
- Auto-scaling (1-3 replicas default, configurable)
- Health checks and monitoring
- Comprehensive logging
- Bicep Infrastructure as Code
- Security scanning in CI/CD

✅ **Developer Friendly**
- Docker Compose for local dev
- Setup wizards for Azure
- Comprehensive documentation
- Quick reference guide
- Clear deployment options

## API Key Injection Methods

### Method 1: HTTP Headers (Recommended)
```bash
curl -H "X-OpenAI-Api-Key: sk-..." \
     https://deployment-url/agents
```

### Method 2: Authorization Header
```bash
curl -H "Authorization: Bearer sk-..." \
     https://deployment-url/agents
```

### Method 3: Container Environment (Fallback)
- Configured during deployment
- Not recommended for multi-tenant scenarios
- Useful as organization-wide default

## Getting Started

1. **Local Development**
   ```bash
   cp .env.local.example .env.local
   docker-compose up -d
   curl http://localhost:9000/health
   ```

2. **Azure Deployment (Manual)**
   ```bash
   ./deploy/azure/setup.sh
   ./deploy/azure/deploy.sh
   ```

3. **Azure Deployment (CI/CD)**
   - Configure GitHub Secrets
   - Push to main branch
   - Deployment happens automatically

## Monitoring & Operations

```bash
# View logs
az containerapp logs show -g neuro-san-rg -n neuro-san-app-production --follow

# Get deployment URL
az containerapp show -g neuro-san-rg -n neuro-san-app-production \
  --query "properties.configuration.ingress.fqdn" -o tsv

# Scale replicas
az deployment group create -g neuro-san-rg \
  --template-file deploy/azure/main.bicep \
  --parameters minReplicas=2 maxReplicas=10
```

## Cost Optimization

- **Min Replicas**: 1 (default, scales based on demand)
- **Max Replicas**: 3 (default, easily increased)
- **Container Size**: 2 CPU, 4GB RAM (configurable)
- **Log Retention**: 30 days (configurable)
- Consider Azure Reserved Instances or Spot Containers for production

## Next Steps

1. ✅ Review `deploy/AZURE_DEPLOYMENT.md` for detailed guide
2. ✅ Run `./deploy/azure/setup.sh` for initial Azure setup
3. ✅ Configure GitHub Secrets for CI/CD
4. ✅ Push code to trigger deployment
5. ✅ Test with `curl https://<deployment-url>/health`
6. ✅ Monitor with Azure Portal or CLI

## Support Resources

- **NeuroSan Docs**: https://github.com/cognizant-ai-lab/neuro-san
- **Azure Container Apps**: https://learn.microsoft.com/azure/container-apps
- **FastAPI**: https://fastapi.tiangolo.com/
- **Bicep**: https://learn.microsoft.com/azure/azure-resource-manager/bicep/
- **GitHub Actions**: https://docs.github.com/actions

---

**Created**: March 13, 2025
**License**: Apache 2.0
**Maintainer**: Cognizant AI Lab
