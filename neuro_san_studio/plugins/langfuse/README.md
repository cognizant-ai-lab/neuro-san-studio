# Langfuse

Provides observability and tracing for AI/ML workloads using [Langfuse](https://langfuse.com/).

## Overview

Langfuse tracing is built into neuro-san itself — there is no plugin class to load.
Installing the optional dependency and setting the environment variables below enables
comprehensive monitoring and analysis of LLM interactions, including:

- Trace collection for all LLM providers via LangChain callback integration
- A root AGENT span per request with `sessionId`/`userId` metadata
- Cost tracking and performance metrics
- Support for both cloud and self-hosted Langfuse instances

## Installation

Langfuse is an optional dependency. Install it only in environments that are meant to
export traces:

```bash
pip install -r neuro_san_studio/plugins/langfuse/requirements.txt
```

or, when installing the package:

```bash
pip install "neuro-san-studio[langfuse]"
```

The deployment Docker image (`deploy/Dockerfile`) installs it by default.

## Quick Start

### Using Langfuse Cloud

1. Create an account at [cloud.langfuse.com](https://cloud.langfuse.com)
2. Create a project and get your API keys
3. Configure your `.env` file:

```bash
LANGFUSE_ENABLED=true
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_PUBLIC_KEY=pk-lf-...
# Optional: LANGFUSE_HOST defaults to https://cloud.langfuse.com
# But if you're in the US you might want to use this one instead:
LANGFUSE_HOST=https://us.cloud.langfuse.com
```

## Configuration

All configuration is done via environment variables in your `.env` file.

### Required Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `LANGFUSE_ENABLED` | `false` | Enable/disable Langfuse tracing |

### API Keys

| Variable | Required | Description |
|----------|----------|-------------|
| `LANGFUSE_SECRET_KEY` | Yes (if enabled) | Secret key from Langfuse dashboard |
| `LANGFUSE_PUBLIC_KEY` | Yes (if enabled) | Public key from Langfuse dashboard |

### Optional Settings

These are read directly by the Langfuse SDK:

| Variable | Default | Description |
|----------|---------|-------------|
| `LANGFUSE_HOST` | `https://cloud.langfuse.com` | Langfuse instance URL |
| `LANGFUSE_RELEASE` | `dev` | Release version tag |
| `LANGFUSE_DEBUG` | `false` | Enable debug logging |
| `LANGFUSE_SAMPLE_RATE` | `1.0` | Trace sampling rate (0.0-1.0) |

Note: when deploying with `deploy/run.sh`, only `LANGFUSE_ENABLED`, `LANGFUSE_SECRET_KEY`,
`LANGFUSE_PUBLIC_KEY`, and `LANGFUSE_HOST` are forwarded into the container.

## Troubleshooting

### No traces appearing

1. Verify `LANGFUSE_ENABLED=true` is set
2. Verify the `langfuse` package is installed (see [Installation](#installation))
3. Check API keys are correct: `LANGFUSE_SECRET_KEY` and `LANGFUSE_PUBLIC_KEY`
4. Confirm `LANGFUSE_HOST` is accessible
5. Enable debug mode: `LANGFUSE_DEBUG=true`
6. Check console output for initialization errors

### Duplicate traces

If every observation in a trace appears exactly twice, a second LangChain
`CallbackHandler` is registered in the server process on top of neuro-san's built-in
one (LangChain dedupes handlers by object identity only). Make sure no custom code
registers its own Langfuse handler via `register_configure_hook` — the old studio
`LangfusePlugin` did exactly this and was removed for that reason (see issue #1292).

### Authentication errors

- Verify your API keys are correct and active
- Ensure keys have proper permissions in Langfuse dashboard
- Check that host URL matches your Langfuse instance

### Missing traces

- Check `LANGFUSE_SAMPLE_RATE` (should be 1.0 for all traces)
- Verify instrumentation is working with debug mode
