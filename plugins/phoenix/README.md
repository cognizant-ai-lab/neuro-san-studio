# Phoenix AI Observability Plugin

This plugin integrates [Arize Phoenix](https://phoenix.arize.com/) for AI observability in Neuro SAN Studio, providing comprehensive monitoring and analysis of LLM interactions.

## Features

- **Automatic instrumentation** for OpenAI, Anthropic, and LangChain
- **OpenTelemetry integration** for distributed tracing
- **Web UI** for inspecting agent conversations and LLM calls
- **Performance metrics** including latency, token usage, and cost estimates
- **Trace visualization** for understanding multi-agent interactions

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

**Note:** A `sitecustomize.py` file in the project root enables automatic instrumentation of subprocesses. This file is included in the repository and requires no additional setup.

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

## Usage

Once installed and configured, Phoenix will automatically:

1. Start the Phoenix server (if `PHOENIX_AUTOSTART=true`)
2. Instrument LLM libraries (OpenAI, Anthropic, LangChain)
3. Collect traces and send them to Phoenix
4. Provide a web UI at `http://localhost:6006`

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

- [Phoenix Documentation](https://docs.arize.com/phoenix)
- [OpenTelemetry Tracing](https://opentelemetry.io/docs/concepts/signals/traces/)
- [Arize Phoenix GitHub](https://github.com/Arize-ai/phoenix)
