# Configuration

This directory holds deployment-specific configuration files that
are expected to vary between environments (e.g. which LLM provider
to use, model selection, API parameters).

By keeping these files in a single top-level directory, the entire
`config/` folder can be overridden at runtime via a Docker volume
mount, making it straightforward to swap configurations without
rebuilding the image.

## Volume Mount Example

```bash
APP_SOURCE=/usr/local/neuro-san/myapp
docker run -v /path/to/your/config:${APP_SOURCE}/config ...
```

## Important

Files in this directory may be overridden by Docker volume mounts
in production. Do not place files here unless they are intended to
be replaceable per deployment.
