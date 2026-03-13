# Quick Setup Guide for Your Azure Resources

Your resources are now configured:
- **Resource Group**: `rg-neurosan`
- **Azure Container Registry**: `ailabneurosan`
- **Location**: `eastus`
- **Image Name**: `neurosan-app`

## Resources That Will Be Created

When you deploy, the following **new resources** will be created in your RG:

| Resource | Name |
|----------|------|
| Container App Environment | `neurosan-app-env-production` |
| Container App | `neurosan-app-app-production` |
| Log Analytics Workspace | `neurosan-app-logs-production` |

Your **existing resources** (`rg-neurosan` RG and `ailabneurosan` ACR) will be used as-is.

---

## Deployment Options

### Option 1: Using the Deployment Script (Easiest)

```bash
# No parameters needed - uses your configured RG and ACR
./deploy/azure/deploy.sh

# Or if you want to specify them explicitly:
./deploy/azure/deploy.sh rg-neurosan ailabneurosan
```

The script will:
1. ✅ Verify your RG and ACR exist
2. ✅ Get ACR credentials
3. ✅ Prompt for API keys (interactive)
4. ✅ Build/push Docker image
5. ✅ Deploy to Azure using Bicep

### Option 2: Using Azure CLI Directly

```bash
# Get your ACR credentials
ACR_URL=$(az acr show \
  -g rg-neurosan \
  -n ailabneurosan \
  --query loginServer -o tsv)

ACR_USERNAME=$(az acr credential show \
  -g rg-neurosan \
  -n ailabneurosan \
  --query "username" -o tsv)

ACR_PASSWORD=$(az acr credential show \
  -g rg-neurosan \
  -n ailabneurosan \
  --query "passwords[0].value" -o tsv)

# Deploy
az deployment group create \
  --name neurosan-deployment-$(date +%s) \
  --resource-group rg-neurosan \
  --template-file deploy/azure/main.bicep \
  --parameters \
    location=eastus \
    environmentName=production \
    projectName=neurosan-app \
    containerImage="${ACR_URL}/neurosan-app:latest" \
    containerRegistryUrl="$ACR_URL" \
    containerRegistryUserName="$ACR_USERNAME" \
    containerRegistryPassword="$ACR_PASSWORD"
```

### Option 3: GitHub Actions (CI/CD)

```bash
# Your workflow is already configured for:
# - AZURE_REGISTRY_NAME: ailabneurosan
# - IMAGE_NAME: neurosan-app
# - RESOURCE_GROUP: rg-neurosan
# - LOCATION: eastus

# Just add these GitHub Secrets:
AZURE_CLIENT_ID           # Your service principal
AZURE_TENANT_ID           # Your tenant
AZURE_SUBSCRIPTION_ID     # Your subscription
ACR_USERNAME              # From your ACR
ACR_PASSWORD              # From your ACR
OPENAI_API_KEY           # (optional)
ANTHROPIC_API_KEY        # (optional)

# Then push to main
git push origin main
```

---

## First Steps

### Step 1: Build and Push Docker Image

```bash
# Log in to your ACR
az acr login -n ailabneurosan

# Build the Docker image
docker build -t ailabneurosan.azurecr.io/neurosan-app:latest -f deploy/Dockerfile .

# Push to ACR
docker push ailabneurosan.azurecr.io/neurosan-app:latest
```

### Step 2: Deploy to Azure

```bash
# Deploy using the script (simplest)
./deploy/azure/deploy.sh

# Or manually:
az deployment group create \
  --name neurosan-deployment-$(date +%s) \
  --resource-group rg-neurosan \
  --template-file deploy/azure/main.bicep \
  --parameters deploy/azure/main.bicepparam \
  --parameters containerRegistryPassword="<your-acr-password>"
```

### Step 3: Get Your Deployment URL

```bash
# After deployment succeeds
az containerapp show \
  -g rg-neurosan \
  -n neurosan-app-app-production \
  --query "properties.configuration.ingress.fqdn" -o tsv

# Result will be something like:
# neurosan-app-app-production-xyz.eastus.azurecontainerapps.io
```

### Step 4: Test Your Deployment

```bash
# Health check
curl https://neurosan-app-app-production-xyz.eastus.azurecontainerapps.io/health

# With OpenAI API Key
curl -X POST \
  -H "Content-Type: application/json" \
  -H "X-OpenAI-Api-Key: sk-..." \
  https://neurosan-app-app-production-xyz.eastus.azurecontainerapps.io/agents
```

---

## Useful Commands

```bash
# View logs
az containerapp logs show \
  -g rg-neurosan \
  -n neurosan-app-app-production \
  --follow

# List all container apps in your RG
az containerapp list -g rg-neurosan -o table

# Check deployment status
az deployment group list -g rg-neurosan -o table

# Scale replicas
az containerapp update \
  -g rg-neurosan \
  -n neurosan-app-app-production \
  --min-replicas 2 \
  --max-replicas 5

# View secrets
az containerapp secrets list \
  -g rg-neurosan \
  -n neurosan-app-app-production

# Delete deployment (if needed)
az deployment group delete \
  -g rg-neurosan \
  -n neurosan-deployment-<timestamp>
```

---

## Notes

- Your ACR credentials are already stored securely in Azure
- API keys are never persisted in the container app - users pass them per-request
- The Container App will auto-scale based on CPU/memory usage
- TLS is automatically managed by Azure
- All logs go to Log Analytics for monitoring

**Ready to deploy? Just run:**
```bash
./deploy/azure/deploy.sh
```

It will guide you through the entire process! 🚀
