# NeuroSan Azure Deployment Quick Reference

## Common Tasks

### Local Development

```bash
# Build Docker image locally
./deploy/build.sh

# Run with Docker Compose
docker-compose up -d

# Run with Docker directly
docker run -it -p 8080:8080 -p 9000:9000 \
  -e OPENAI_API_KEY="sk-..." \
  neuro-san/neuro-san-studio:0.0.1

# Test the gateway
curl http://localhost:9000/health
curl -H "X-OpenAI-Api-Key: sk-..." \
     http://localhost:9000/agents
```

### Azure Deployment

```bash
# Set up Azure environment (one-time setup)
./deploy/azure/setup.sh

# Deploy to Azure
./deploy/azure/deploy.sh

# Get deployment URL
az containerapp show \
  -g neuro-san-rg \
  -n neuro-san-app-production \
  --query "properties.configuration.ingress.fqdn" -o tsv
```

### Monitoring

```bash
# View real-time logs
az containerapp logs show \
  -g neuro-san-rg \
  -n neuro-san-app-production \
  --follow

# Check deployment status
az containerapp show \
  -g neuro-san-rg \
  -n neuro-san-app-production

# Get revision history
az containerapp revision list \
  -g neuro-san-rg \
  -n neuro-san-app-production
```

## API Examples

### Test Health
```bash
curl https://<url>/health
```

### Query Agents
```bash
curl -H "X-OpenAI-Api-Key: sk-..." \
  https://<url>/agents
```

### Call Agent with OpenAI
```bash
curl -X POST \
  -H "Content-Type: application/json" \
  -H "X-OpenAI-Api-Key: sk-..." \
  -d '{"agent": "my_agent", "prompt": "Hello"}' \
  https://<url>/agents
```

### Call Agent with Anthropic
```bash
curl -X POST \
  -H "Content-Type: application/json" \
  -H "X-Anthropic-Api-Key: sk-ant-..." \
  -d '{"agent": "my_agent", "prompt": "Hello"}' \
  https://<url>/agents
```

### Call Agent with Azure OpenAI
```bash
curl -X POST \
  -H "Content-Type: application/json" \
  -H "X-Azure-OpenAI-Api-Key: key" \
  -H "X-Azure-OpenAI-Endpoint: https://resource.openai.azure.com/" \
  -d '{"agent": "my_agent", "prompt": "Hello"}' \
  https://<url>/agents
```

## GitHub Actions Secrets to Configure

```
AZURE_CLIENT_ID              # Service Principal ID
AZURE_TENANT_ID              # Azure Tenant ID
AZURE_SUBSCRIPTION_ID        # Azure Subscription ID
ACR_USERNAME                 # Azure Container Registry username
ACR_PASSWORD                 # Azure Container Registry password
OPENAI_API_KEY              # (Optional)
ANTHROPIC_API_KEY           # (Optional)
AZURE_OPENAI_API_KEY        # (Optional)
AZURE_OPENAI_ENDPOINT       # (Optional)
```

## Environment Variables Reference

### Gateway
- API_GATEWAY_HOST: API Gateway bind address (default: 0.0.0.0)
- API_GATEWAY_PORT: Gateway port (default: 9000)
- NEURO_SAN_HOST: NeuroSan server address (default: localhost)
- NEURO_SAN_PORT: NeuroSan port (default: 8080)
- REQUEST_TIMEOUT: Request timeout in seconds (default: 300)

### NeuroSan Server
- NEURO_SAN_SERVER_HOST: Server bind address (default: localhost)
- NEURO_SAN_SERVER_HTTP_PORT: HTTP port (default: 8080)
- LOG_LEVEL: Logging level (default: INFO)
- AGENT_HTTP_SERVER_INSTANCES: Worker processes (default: 1)
- AGENT_MAX_CONCURRENT_REQUESTS: Max requests (default: 50)

### LLM Keys (via HTTP headers)
- X-OpenAI-Api-Key
- X-Anthropic-Api-Key
- X-Azure-OpenAI-Api-Key
- X-Azure-OpenAI-Endpoint
- X-Google-Api-Key
- X-AWS-Access-Key
- X-AWS-Secret-Key
- X-Nvidia-Api-Key

## File Structure

```
.
├── deploy/
│   ├── Dockerfile              # Production Docker image
│   ├── entrypoint.sh          # Container entry point
│   ├── AZURE_DEPLOYMENT.md    # Full deployment guide
│   ├── azure/
│   │   ├── setup.sh           # Azure setup script
│   │   ├── deploy.sh          # Deployment script
│   │   ├── main.bicep         # Bicep template
│   │   └── main.bicepparam    # Bicep parameters
│   └── logging.hocon          # Logging configuration
├── middleware/
│   └── api_gateway.py         # FastAPI gateway
├── .github/
│   └── workflows/
│       └── azure-deploy.yml   # CI/CD workflow
├── docker-compose.yml         # Local development
├── requirements.txt           # Python dependencies
└── .env.local.example         # Environment template
```

## Troubleshooting

### Container won't start
```bash
# Check logs
az containerapp logs show -g neuro-san-rg -n neuro-san-app-production

# Verify image exists
az acr repository show -n neurosanadministration --repository neuro-san
```

### Gateway can't reach NeuroSan
```bash
# SSH into container and test connectivity
# Verify service names in docker-compose or pod networking
```

### API key not working
```bash
# Verify header name matches (case-insensitive)
# Test with curl -v to see headers sent
# Check key validity with provider
```

### High latency
```bash
# Increase container resources
# Increase replica count
# Check REQUEST_TIMEOUT is sufficient
```

## Links

- [Azure Container Apps Docs](https://learn.microsoft.com/azure/container-apps)
- [NeuroSan Repository](https://github.com/cognizant-ai-lab/neuro-san)
- [FastAPI Docs](https://fastapi.tiangolo.com)
- [Docker Documentation](https://docs.docker.com)
- [GitHub Actions Docs](https://docs.github.com/actions)
