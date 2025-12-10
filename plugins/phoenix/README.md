# Phoenix AI Observability Plugin

This plugin integrates [Arize Phoenix](https://phoenix.arize.com/) for AI observability in Neuro SAN Studio, providing comprehensive monitoring and analysis of LLM interactions.

## Features

- **Automatic instrumentation** for OpenAI, Anthropic, LangChain, LiteLLM, and MCP
- **OpenTelemetry integration** for distributed tracing with OTLP export
- **Web UI** for inspecting agent conversations and LLM calls at `http://localhost:6006`
- **Performance metrics** including latency, token usage, and cost estimates
- **Trace visualization** for understanding multi-agent interactions
- **Plugin-based architecture** for clean, non-invasive integration with Neuro SAN Studio
- **Dual initialization modes** with automatic fallback for maximum compatibility

## Installation

1. Install the Phoenix plugin dependencies:

```bash
pip install -r plugins/phoenix/requirements.txt
```

2. Enable Phoenix by setting environment variables in your `.env` file:

```bash
PHOENIX_ENABLED=true
PHOENIX_AUTOSTART=true
```

**Note:** Phoenix is now integrated as a plugin that initializes when the Neuro SAN server starts. The plugin handles all instrumentation automatically when enabled.

## Configuration

### Environment Variables

#### Required Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PHOENIX_ENABLED` | `false` | Enable/disable Phoenix observability |
| `PHOENIX_AUTOSTART` | `false` | Automatically start Phoenix server |

#### Optional Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PHOENIX_HOST` | `127.0.0.1` | Phoenix server host |
| `PHOENIX_PORT` | `6006` | Phoenix server port |
| `PHOENIX_PROJECT_NAME` | `default` | Project name for grouping traces |
| `PHOENIX_OTEL_REGISTER` | `true` | Use phoenix.otel.register() for initialization (fallback to manual if false) |
| `OTEL_SERVICE_NAME` | `neuro-san-demos` | Service name for OpenTelemetry |
| `OTEL_SERVICE_VERSION` | `dev` | Service version |
| `OTEL_EXPORTER_OTLP_TRACES_ENDPOINT` | `http://localhost:6006/v1/traces` | OTLP traces endpoint |

### Example `.env` Configuration

**Minimal (Required only):**
```bash
PHOENIX_ENABLED=true
PHOENIX_AUTOSTART=true
```

**With Optional Customization:**
```bash
PHOENIX_ENABLED=true
PHOENIX_AUTOSTART=true
PHOENIX_PROJECT_NAME=my-project
OTEL_SERVICE_NAME=neuro-san-studio
OTEL_SERVICE_VERSION=1.0.0
```

## Architecture

### Plugin-Based Design

Phoenix observability is implemented as a self-contained plugin following a refactoring in [PR #404](https://github.com/cognizant-ai-lab/neuro-san-studio/pull/404). The design prioritizes:

- **Non-invasive integration**: Phoenix initialization occurs only when the Neuro SAN server starts, not during pip operations or tests
- **Centralized logic**: All Phoenix-related code is consolidated in the `plugins/phoenix/` directory
- **Clean lifecycle management**: The `PhoenixPlugin` class encapsulates server startup, configuration, and shutdown

### Key Components

#### PhoenixPlugin Class

The `PhoenixPlugin` class (in `plugins/phoenix/phoenix_plugin.py`) manages:

- **Configuration**: Reads environment variables and provides defaults via `get_default_config()`
- **Initialization**: Sets up OpenTelemetry tracer provider and instruments LLM SDKs (OpenAI, Anthropic, LangChain, LiteLLM, MCP)
- **Server lifecycle**: Starts and stops the Phoenix server process based on `PHOENIX_AUTOSTART` setting
- **Idempotent initialization**: Safe to call `initialize()` multiple times; tracks state per process

#### Integration Methods

The plugin offers two initialization approaches:

1. **phoenix.otel.register()**: Preferred method that provides automatic setup with Phoenix's first-class support
2. **Manual setup**: Fallback that configures OpenTelemetry tracer provider and instruments SDKs directly

This dual approach ensures compatibility across different environments and Phoenix versions.

### Design Decisions

Key decisions from the refactoring:

- **Removed `sitecustomize.py`**: Previously, Phoenix auto-initialized in all Python processes (including pip and tests). This was too invasive and caused unintended side effects.
- **Plugin pattern**: Enables future extensibility for other observability tools without requiring core code changes
- **Lazy initialization**: Phoenix only initializes when explicitly enabled and the server starts, reducing overhead for users who don't need observability
- **Separate requirements**: Phoenix dependencies are isolated in `plugins/phoenix/requirements.txt`, making it easy to install only when needed

### Future Considerations

As noted in PR discussions:

- The plugin pattern may evolve into a more generic interface (e.g., `ObservabilityFactory`) as more plugins are added
- Process management could be consolidated across plugins (tracked in [issue #426](https://github.com/cognizant-ai-lab/neuro-san-studio/issues/426))
- The separate requirements file suggests potential extraction to an independent repository in the future

## Usage

Once installed and configured, Phoenix will automatically:

1. Start the Phoenix server (if `PHOENIX_AUTOSTART=true`)
2. Instrument LLM libraries (OpenAI, Anthropic, LangChain, LiteLLM, MCP)
3. Collect traces and send them to Phoenix via OpenTelemetry
4. Provide a web UI at `http://localhost:6006`

The plugin initializes when the Neuro SAN server starts, ensuring observability is available throughout your agent network's lifecycle.

### Viewing Traces

1. Start Neuro SAN Studio with Phoenix enabled
2. Open `http://localhost:6006` in your browser
3. Run your agents and see traces appear in real-time

### Manual Phoenix Server

To run Phoenix server separately:

```bash
python -m phoenix.server.main serve
```

Then set `PHOENIX_AUTOSTART=false` in your `.env` file.

## Disabling Phoenix

To disable Phoenix observability:

```bash
# In .env file
PHOENIX_ENABLED=false
```

Or simply remove the Phoenix environment variables.

## Troubleshooting

### Phoenix fails to start

- Check that dependencies are installed: `pip list | grep phoenix`
- Verify port 6006 is not in use: `netstat -an | grep 6006`
- Check logs at `logs/phoenix.log`

### No traces appearing

- Verify `PHOENIX_ENABLED=true` is set
- Check that the Phoenix server is running
- Ensure OTLP endpoint is correct
- Review initialization messages in console output

### Import errors

Make sure you've installed the plugin requirements:

```bash
pip install -r plugins/phoenix/requirements.txt
```

## Learn More

### Official Documentation

- [Phoenix Documentation](https://docs.arize.com/phoenix)
- [OpenTelemetry Tracing](https://opentelemetry.io/docs/concepts/signals/traces/)
- [Arize Phoenix GitHub](https://github.com/Arize-ai/phoenix)

### Related PRs and Issues

- [PR #404: Phoenix Plugin Refactoring](https://github.com/cognizant-ai-lab/neuro-san-studio/pull/404) - Major refactoring to plugin-based architecture
- [Issue #426: Consolidate process management across plugins](https://github.com/cognizant-ai-lab/neuro-san-studio/issues/426) - Future improvement for unified plugin lifecycle management
