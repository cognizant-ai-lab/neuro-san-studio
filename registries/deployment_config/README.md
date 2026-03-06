# Deployment Configuration
 
This directory contains configuration files that control deployment-specific
behavior. These files are separated from agent network definitions so they
can be independently overridden if required at deployment time via Docker volume mounts.
 
## Why This Directory?
 
Agent network .hocon files in registries/ define agent behavior and are
typically the same across environments. The files in this directory, however,
are expected to vary for different agents (e.g., which LLM provider to use,
model selection, etc.).
 
## Important Note
 
Files in this directory may be overridden by Docker volume mounts in
production. Do not place files here unless they are intended to be
replaceable per deployment.
 
## Volume Mount Example

```bash
APP_SOURCE = /usr/local/neuro-san/myapp
docker run -v /path/to/your/llm_config.hocon:${APP_SOURCE}/registries/deployment_config/llm_config.hocon ...
```
