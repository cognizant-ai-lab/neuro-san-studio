# Langfuse Plugin

Provides observability and tracing for AI/ML workloads using [Langfuse](https://langfuse.com/).

## Overview

The Langfuse plugin enables comprehensive monitoring and analysis of LLM interactions, including:
- Trace collection from OpenAI, Anthropic, and other LLM providers
- LangChain callback integration
- Cost tracking and performance metrics
- Custom trace attributes and metadata
- Support for both cloud and self-hosted Langfuse instances

## Installation

Install the Langfuse SDK:

```bash
pip install -r plugins/langfuse/requirements.txt
```

## Quick Start

### Using Langfuse Cloud

1. Create an account at [cloud.langfuse.com](https://cloud.langfuse.com)
2. Create a project and get your API keys
3. Configure your `.env` file:

```bash
LANGFUSE_ENABLED=true
LANGFUSE_USE_EXISTING=false
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_PUBLIC_KEY=pk-lf-...
```

### Using Existing Langfuse Instance

If you already have Langfuse running (cloud or self-hosted):

```bash
LANGFUSE_ENABLED=true
LANGFUSE_USE_EXISTING=true
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_HOST=https://your-langfuse-instance.com
```

## Configuration

All configuration is done via environment variables in your `.env` file.

### Required Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `LANGFUSE_ENABLED` | `false` | Enable/disable Langfuse observability |
| `LANGFUSE_USE_EXISTING` | `false` | Use existing Langfuse instance (skips local setup) |

### API Keys

| Variable | Required | Description |
|----------|----------|-------------|
| `LANGFUSE_SECRET_KEY` | Yes (if enabled) | Secret key from Langfuse dashboard |
| `LANGFUSE_PUBLIC_KEY` | Yes (if enabled) | Public key from Langfuse dashboard |

### Optional Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `LANGFUSE_HOST` | `https://cloud.langfuse.com` | Langfuse instance URL |
| `LANGFUSE_PROJECT_NAME` | `default` | Project name for organizing traces |
| `LANGFUSE_RELEASE` | `dev` | Release version tag |
| `LANGFUSE_DEBUG` | `false` | Enable debug logging |
| `LANGFUSE_SAMPLE_RATE` | `1.0` | Trace sampling rate (0.0-1.0) |


## Troubleshooting

### No traces appearing

1. Verify `LANGFUSE_ENABLED=true` is set
2. Check API keys are correct: `LANGFUSE_SECRET_KEY` and `LANGFUSE_PUBLIC_KEY`
3. Confirm `LANGFUSE_HOST` is accessible
4. Enable debug mode: `LANGFUSE_DEBUG=true`
5. Check console output for initialization errors

### Authentication errors

- Verify your API keys are correct and active
- Ensure keys have proper permissions in Langfuse dashboard
- Check that host URL matches your Langfuse instance

### Missing traces

- Call `plugin.flush()` before application exit
- Check `LANGFUSE_SAMPLE_RATE` (should be 1.0 for all traces)
- Verify instrumentation is working with debug mode

### Using with existing instance

When `LANGFUSE_USE_EXISTING=true`:
- Plugin skips local client initialization
- Only validates that API keys are set
- Assumes Langfuse SDK is configured elsewhere
- Useful for custom setups or framework integration
