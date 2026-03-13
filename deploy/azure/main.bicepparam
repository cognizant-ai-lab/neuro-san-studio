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

// Parameters file for NeuroSan Container App deployment

param location = 'eastus'
param environmentName = 'production'
param projectName = 'neurosan-app'

// Container image - set these to your actual ACR values
param containerImage = 'ailabneurosan.azurecr.io/neurosan-app:latest'
param containerRegistryUrl = 'ailabneurosan.azurecr.io'
param containerRegistryUserName = 'ailabneurosan-admin'

// Container configuration
param containerPort = 8080
param apiGatewayPort = 9000
param cpuCores = '2'
param memoryGb = '4'
param minReplicas = 1
param maxReplicas = 3

// Azure OpenAI configuration (optional)
param azureOpenaiEndpoint = ''

// Note: API keys should NOT be set in this file
// Instead, pass them as parameters during deployment via Azure CLI or GitHub Actions
// Example: az deployment group create ... -p openaiApiKey="sk-..."
