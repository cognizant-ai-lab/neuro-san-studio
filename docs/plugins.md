# Plugins

Plugins are a way to extend the functionality of a Neuro SAN server largely for deployment-related use-cases.
Note that plugins are never required for Neuro SAN to function.

<!-- TOC -->

- [Plugins](#plugins)
  - [Authorization](#authorization)
    - [Open FGA](#open-fga)
  - [Diagnostics](#diagnostics)
    - [LLM Config Validator](#llm-config-validator)
  - [Logging](#logging)
    - [Log Bridge](#log-bridge)
  - [Observability](#observability)
    - [Arize Phoenix](#arize-phoenix)
    - [Langfuse](#langfuse)
    - [LangSmith](#langsmith)

<!-- TOC -->

## Authorization

Authorization plugins allow user-by-user access control to Agent Networks.
This is not to be confused with _authentication_, which is the process of verifying a user's identity.

### Open FGA

[Open FGA](../plugins/authorization/openfga/README.md) is a plugin that extends the authorization capabilities
of a Neuro SAN server using a free and open source Open FGA server to do Relation-Based Access Control (ReBAC)
authorization.

## Diagnostics

Diagnostic plugins help verify that your Neuro SAN Studio environment is correctly configured
before starting the server.

### LLM Config Validator

The LLM Config Validator checks that every LLM configuration in a HOCON file is reachable and
working by creating each LLM instance and invoking it with a trivial test prompt.
It can also check the `llm_config.hocon` for any issues.

It can be invoked via the `--check-llm-config` flag on `run.py`:

```bash
# Check the default registries/llm_config.hocon
python run.py --check-llm-config

# Check a specific agent network or llm_config HOCON file
python run.py --check-llm-config registries/music_nerd.hocon
```

Or run the script directly:

```bash
python plugins/llm_config_validator/check_llm_configs.py registries/llm_config.hocon
```

Both HOCON formats are supported:

- **Agent network** files (containing a `tools` list) — every agent's merged `llm_config` is tested.
- **Standalone studio `llm_config`** files — the single top-level `llm_config` is tested.

Duplicate configurations are deduplicated so each unique model is called only once.
The validator exits with a non-zero code if any configuration fails, blocking server startup
until the issue is resolved.

## Logging

Logging plugins enhance the console and file logging experience for Neuro SAN Studio,
providing structured, human-readable output from server and client subprocesses.

### Log Bridge

The [Log Bridge plugin](../plugins/log_bridge/README.md) provides Rich-based structured logging for
Neuro SAN Studio, replacing raw subprocess output with colored, pretty-printed, and severity-aware
console logs. It is enabled by default.

## Observability

Observability plugins provide insights into the behavior and performance of Agent Networks,
allowing developers to monitor and analyze their networks in real-time.

### Arize Phoenix

The [Arize Phoenix plugin](../plugins/phoenix/README.md) integrates [Arize Phoenix](https://phoenix.arize.com/) for AI
observability in Neuro SAN Studio, providing comprehensive monitoring and analysis of LLM interactions.

### Langfuse

The [Langfuse plugin](../plugins/langfuse/README.md) integrates [Langfuse](https://langfuse.com/) for AI
observability in Neuro SAN Studio, providing trace collection, cost tracking, and performance metrics
for LLM interactions. It supports both cloud and self-hosted Langfuse instances.

### LangSmith

[LangSmith](../plugins/langsmith/README.md) is LangChain's built-in observability platform. Since Neuro SAN uses LangChain
internally, LangSmith tracing works out of the box with no plugin required — just set
`LANGSMITH_TRACING=true` and `LANGSMITH_API_KEY` in your `.env` file.
