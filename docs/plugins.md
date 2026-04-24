# Plugins

Plugins are a way to extend the functionality of a Neuro SAN server largely for deployment-related use-cases.
Note that plugins are never required for Neuro SAN to function.

<!-- TOC -->

- [Plugins](#plugins)
  - [Creating Custom Plugins](#creating-custom-plugins)
    - [BasePlugin Interface](#baseplugin-interface)
    - [Registering a Plugin](#registering-a-plugin)
    - [Plugin Lifecycle](#plugin-lifecycle)
    - [Example Plugin](#example-plugin)
  - [Authorization](#authorization)
    - [Open FGA](#open-fga)
  - [Diagnostics](#diagnostics)
    - [LLM Config Validator](#llm-config-validator)
    - [Env Validator](#env-validator)
  - [Logging](#logging)
    - [Log Bridge](#log-bridge)
  - [Observability](#observability)
    - [Arize Phoenix](#arize-phoenix)
    - [Langfuse](#langfuse)
    - [LangSmith](#langsmith)

<!-- TOC -->

## Creating Custom Plugins

All plugins extend the `BasePlugin` class in `plugins/base_plugin.py` and are registered in
`config/plugins.hocon`.

### BasePlugin Interface

| Method | Type | Description |
|---|---|---|
| `__init__(name, args)` | Instance | Constructor. Receives the full args dict from the runner. |
| `initialize()` | Instance | Called in the **server process** during startup. |
| `cleanup()` | Instance | Called on shutdown to release resources. |
| `pre_server_start_action()` | Instance | Called in **runner** before subprocesses start. |
| `post_server_start_action()` | Instance | Called in **runner** after subprocesses start. |
| `update_args_dict(args_dict)` | Static | Inject default config values into args before CLI parsing. |
| `update_parser_args(parser)` | Static | Register plugin-specific CLI arguments on the parser. |

### Registering a Plugin

Add an entry to `config/plugins.hocon`:

```hocon
plugins = [
    {
        class = plugins.my_plugin.my_plugin.MyPlugin
        enabled = true
    }
]
```

Each entry specifies the fully-qualified Python class path (module + class name).
The `enabled` flag controls whether the plugin is loaded. You can override it with
an environment variable using HOCON substitution:

```hocon
{
    class = plugins.my_plugin.my_plugin.MyPlugin
    enabled = false
    enabled = ${?MY_PLUGIN_ENABLED}
}
```

This sets the default to `false` but allows the `MY_PLUGIN_ENABLED` environment
variable to override it at runtime. If a plugin fails to import (e.g. missing
dependency), it is skipped with a warning rather than crashing the entire startup.

### Plugin Lifecycle

Plugins are loaded in two contexts with different lifecycle methods:

**Runner process** (`run.py`) -- manages subprocesses:

1. `update_args_dict()` -- inject default config values
2. `update_parser_args()` -- register CLI arguments
3. Plugin instantiated with final args
4. `pre_server_start_action()` -- before subprocesses start
5. `post_server_start_action()` -- after subprocesses start
6. `cleanup()` -- on shutdown (Ctrl+C / SIGTERM)

**Server process** (`neuro_san_server_wrapper.py`) -- in-process server:

1. Plugin instantiated
2. `initialize()` -- called before the server main loop
3. `cleanup()` -- called when the server exits

### Example Plugin

See [`BasePlugin`](../neuro_san_studio/interfaces/base_plugin.py) for the full interface and
[`PhoenixPlugin`](../plugins/phoenix/phoenix_plugin.py) for a real-world implementation.

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
# Check the default config/llm_config.hocon
python -m run --check-llm-config

# Check a specific agent network or llm_config HOCON file
python -m run --check-llm-config registries/basic/music_nerd.hocon
```

Or run the script directly:

```bash
python plugins/llm_config_validator/check_llm_configs.py config/llm_config.hocon
```

Both HOCON formats are supported:

- **Agent network** files (containing a `tools` list) — every agent's merged `llm_config` is tested.
- **Standalone studio `llm_config`** files — the single top-level `llm_config` is tested.

Duplicate configurations are deduplicated so each unique model is called only once.
The validator exits with a non-zero code if any configuration fails, blocking server startup
until the issue is resolved.

### Env Validator

The Env Validator checks that LLM API keys and other critical environment variables are configured
correctly before the server starts. It runs three progressively deeper tiers of validation:

| Tier | Name | What it checks |
|---|---|---|
| 1 | Placeholder detection | Variable is set and not a placeholder (`YOUR_`, `REPLACE`, `TODO`, `<`, `>`, etc.). |
| 2 | Format validation | Value matches the expected format for the key type (prefix, length, character set). |
| 3 | Live validation | Makes a lightweight API call to verify the key with the provider (OpenAI, Anthropic, Google). |

Each tier is cumulative — tier 2 includes tier 1, and tier 3 includes tiers 1 and 2.
Tiers 1 and 2 run entirely offline; tier 3 requires network access to reach the provider APIs.

**Keys validated:** `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GOOGLE_API_KEY`, `AWS_ACCESS_KEY_ID`,
`AWS_SECRET_ACCESS_KEY`, `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_ENDPOINT`.

**Usage:**

```bash
# Tier 1 only — placeholder detection (no format or network checks)
python -m run --validate-keys 1

# Tier 2 — placeholder + format checks (no network calls)
python -m run --validate-keys 2

# Tier 3 — all checks including live API calls (default when no value is given)
python -m run --validate-keys
python -m run --validate-keys 3
```

The validator prints a grouped results table (VALID / WARNING / ERROR) and logs a summary count.
Missing or placeholder keys produce warnings but do not block startup — only format or
authentication errors are flagged as errors.

**Registration** (`config/plugins.hocon`):

```hocon
{
    class = plugins.env_validator.env_validator.EnvValidatorPlugin
    enabled = false
}
```

The plugin is disabled by default. Enable it for a single run by passing `--validate-keys` on the
command line, or set `enabled = true` in `plugins.hocon` to run validation on every startup.

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
