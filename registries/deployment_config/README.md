# Deployment Configuration

This directory contains configuration files that are intended to be overridden
at deployment time via Docker volume mounts.

**Warning:** Do not place development-only or environment-specific configs here
unless they are meant to be replaced during deployment. Files in this directory
may be overridden by volume mounts in production environments.

## Files

- `llm_config.hocon` - Default LLM provider and model configuration. Override
  this file to change the LLM backend (e.g., switch from OpenAI to Bedrock)
  without rebuilding the Docker image.

## Volume Mount Example

```bash
docker run -v /path/to/your/llm_config.hocon:/usr/local/neuro-san/myapp/registries/deployment_config/llm_config.hocon <image>
```
