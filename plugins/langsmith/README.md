# LangSmith Observability

[LangSmith](https://smith.langchain.com/) is LangChain's built-in observability platform for tracing, monitoring, and debugging LLM applications.

Since Neuro SAN uses LangChain internally, LangSmith tracing works out of the box with no plugin required — just set environment variables.

## Quick Start

1. [Create an account and get your API key](https://docs.langchain.com/langsmith/create-account-api-key)
2. Create a project
3. Configure your `.env` file:

```bash
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=lsv2_pt_...
# Optional: defaults to "default"
LANGCHAIN_PROJECT=my-project
```

That's it. All LangChain `Runnable.invoke()` / `.ainvoke()` calls (including those inside Neuro SAN's `RunContextRunnable`) are automatically traced.

## Configuration

All configuration is done via environment variables in your `.env` file.

### Required Settings

| Variable | Description |
|----------|-------------|
| `LANGCHAIN_TRACING_V2` | Set to `true` to enable tracing |
| `LANGCHAIN_API_KEY` | API key from LangSmith dashboard |

### Optional Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `LANGCHAIN_PROJECT` | `default` | Project name for organizing traces |
| `LANGCHAIN_ENDPOINT` | `https://api.smith.langchain.com` | LangSmith API endpoint |

## How It Works

LangSmith tracing is built into LangChain's callback system. When `LANGCHAIN_TRACING_V2=true` is set, LangChain automatically adds a `LangChainTracer` callback to every invocation. This captures all LLM calls, tool usage, and chain execution across all providers (OpenAI, Anthropic, Google, etc.).

No code changes or plugins are needed — the environment variables are all that's required.

## Troubleshooting

### No traces appearing

1. Verify `LANGCHAIN_TRACING_V2=true` is set
2. Check that `LANGCHAIN_API_KEY` is correct
3. Confirm `LANGCHAIN_ENDPOINT` is accessible (if using a custom endpoint)

### Authentication errors

- Verify your API key is correct and active at [smith.langchain.com](https://smith.langchain.com/)
- Ensure the key has proper permissions
