// Copyright © 2025 Cognizant Technology Solutions Corp, www.cognizant.com.
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//     http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.
//
// END COPYRIGHT

// Main bicep template for NeuroSan deployment on Azure Container Apps

param location string = resourceGroup().location
param environmentName string = 'production'
param projectName string = 'neuro-san'
param containerImage string
param containerRegistryUrl string
param containerRegistryUserName string
@secure()
param containerRegistryPassword string

// Container App configuration
param containerPort int = 8080
param apiGatewayPort int = 9000
param cpuCores string = '2'
param memoryGb string = '4'
param minReplicas int = 1
param maxReplicas int = 3

// LLM API Keys (will be set at runtime, not stored in template)
@secure()
param openaiApiKey string = ''
@secure()
param anthropicApiKey string = ''
@secure()
param azureOpenaiApiKey string = ''
param azureOpenaiEndpoint string = ''

// Naming convention
var containerAppEnvName = '${projectName}-env-${environmentName}'
var containerAppName = '${projectName}-app-${environmentName}'
var logAnalyticsName = '${projectName}-logs-${environmentName}'

// Create Log Analytics Workspace
resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2022-10-01' = {
  name: logAnalyticsName
  location: location
  properties: {
    sku: {
      name: 'PerGB2018'
    }
    retentionInDays: 30
  }
}

// Create Container App Environment
resource containerAppEnv 'Microsoft.App/managedEnvironments@2023-11-02-preview' = {
  name: containerAppEnvName
  location: location
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logAnalytics.properties.customerId
        sharedKey: logAnalytics.listKeys().primarySharedKey
      }
    }
    zoneRedundant: false
  }
}

// Create the NeuroSan Container App
resource neuroSanApp 'Microsoft.App/containerApps@2023-11-02-preview' = {
  name: containerAppName
  location: location
  identity: {
    type: 'None'
  }
  properties: {
    managedEnvironmentId: containerAppEnv.id
    configuration: {
      ingress: {
        external: true
        targetPort: apiGatewayPort
        transport: 'auto'
        allowInsecure: false
        traffic: [
          {
            latestRevision: true
            weight: 100
          }
        ]
      }
      registries: [
        {
          server: containerRegistryUrl
          username: containerRegistryUserName
          passwordSecretRef: 'container-registry-password'
        }
      ]
      secrets: [
        {
          name: 'container-registry-password'
          value: containerRegistryPassword
        }
        {
          name: 'openai-api-key'
          value: openaiApiKey
        }
        {
          name: 'anthropic-api-key'
          value: anthropicApiKey
        }
        {
          name: 'azure-openai-api-key'
          value: azureOpenaiApiKey
        }
      ]
    }
    template: {
      containers: [
        {
          name: 'neuro-san'
          image: containerImage
          resources: {
            cpu: json(cpuCores)
            memory: '${memoryGb}Gi'
          }
          env: [
            {
              name: 'NEURO_SAN_SERVER_HOST'
              value: '0.0.0.0'
            }
            {
              name: 'NEURO_SAN_SERVER_HTTP_PORT'
              value: string(containerPort)
            }
            {
              name: 'LOG_LEVEL'
              value: 'INFO'
            }
            {
              name: 'AGENT_HTTP_SERVER_INSTANCES'
              value: '2'
            }
            {
              name: 'AGENT_MAX_CONCURRENT_REQUESTS'
              value: '100'
            }
            {
              name: 'AGENT_MCP_ENABLE'
              value: 'true'
            }
            {
              name: 'AZURE_OPENAI_ENDPOINT'
              value: azureOpenaiEndpoint
            }
            // Note: API keys can be injected via headers at request time
            // These are fallback values; per-request injection is preferred
            {
              name: 'OPENAI_API_KEY'
              secretRef: 'openai-api-key'
            }
            {
              name: 'ANTHROPIC_API_KEY'
              secretRef: 'anthropic-api-key'
            }
            {
              name: 'AZURE_OPENAI_API_KEY'
              secretRef: 'azure-openai-api-key'
            }
          ]
        }
        {
          name: 'api-gateway'
          image: containerImage
          resources: {
            cpu: json(cpuCores)
            memory: '${memoryGb}Gi'
          }
          env: [
            {
              name: 'NEURO_SAN_HOST'
              value: 'localhost'
            }
            {
              name: 'NEURO_SAN_PORT'
              value: string(containerPort)
            }
            {
              name: 'API_GATEWAY_HOST'
              value: '0.0.0.0'
            }
            {
              name: 'API_GATEWAY_PORT'
              value: string(apiGatewayPort)
            }
            {
              name: 'REQUEST_TIMEOUT'
              value: '300'
            }
            {
              name: 'LOG_LEVEL'
              value: 'INFO'
            }
          ]
          command: [
            'python'
            '-m'
            'uvicorn'
            'middleware.api_gateway:app'
          ]
        }
      ]
      scale: {
        minReplicas: minReplicas
        maxReplicas: maxReplicas
        rules: [
          {
            name: 'http-rule'
            http: {
              metadata: {
                concurrentRequests: string(50)
              }
            }
          }
        ]
      }
    }
  }
}

// Output values
output containerAppUrl string = 'https://${neuroSanApp.properties.configuration.ingress.fqdn}'
output containerAppFqdn string = neuroSanApp.properties.configuration.ingress.fqdn
output containerAppName string = neuroSanApp.name
output containerAppEnvName string = containerAppEnv.name
