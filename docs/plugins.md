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
  - [Logging](#logging)
    - [Log Bridge](#log-bridge)
  - [Observability](#observability)
    - [Arize Phoenix](#arize-phoenix)
    - [Langfuse](#langfuse)
    - [LangSmith](#langsmith)

<!-- TOC -->

## Creating Custom Plugins

All plugins extend the `BasePlugin` class in `neuro_san_studio/plugins/base_plugin.py` and are registered in
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

**Runner process** (`neuro_san_studio/commands/run.py`) -- manages subprocesses:

1. `update_args_dict()` -- inject default config values
2. `update_parser_args()` -- register CLI arguments
3. Plugin instantiated with final args
4. `pre_server_start_action()` -- before subprocesses start
5. `post_server_start_action()` -- after subprocesses start
6. `cleanup()` -- on shutdown (Ctrl+C / SIGTERM)

**Server process** (`neuro_san_studio/runner/neuro_san_server_wrapper.py`) -- in-process server:

1. Plugin instantiated
2. `initialize()` -- called before the server main loop
3. `cleanup()` -- called when the server exits

### Example Plugin

See [`BasePlugin`](../neuro_san_studio/interfaces/base_plugin.py) for the full interface and
[`PhoenixPlugin`](../neuro_san_studio/plugins/phoenix/phoenix_plugin.py) for a real-world implementation.

## Authorization

Authorization plugins allow user-by-user access control to Agent Networks.
This is not to be confused with _authentication_, which is the process of verifying a user's identity.

### Open FGA

[Open FGA](../neuro_san_studio/plugins/openfga/README.md) is a plugin that extends the authorization capabilities
of a Neuro SAN server using a free and open source Open FGA server to do Relation-Based Access Control (ReBAC)
authorization.

## Logging

Logging plugins enhance the console and file logging experience for Neuro SAN Studio,
providing structured, human-readable output from server and client subprocesses.

### Log Bridge

The [Log Bridge plugin](../neuro_san_studio/plugins/log_bridge/README.md) provides Rich-based structured logging for
Neuro SAN Studio, replacing raw subprocess output with colored, pretty-printed, and severity-aware
console logs. It is enabled by default.

## Observability

Observability plugins provide insights into the behavior and performance of Agent Networks,
allowing developers to monitor and analyze their networks in real-time.

### Arize Phoenix

The [Arize Phoenix plugin](../neuro_san_studio/plugins/phoenix/README.md) integrates
[Arize Phoenix](https://phoenix.arize.com/) for AI observability in Neuro SAN Studio,
providing comprehensive monitoring and analysis of LLM interactions.

### Langfuse

The [Langfuse plugin](../neuro_san_studio/plugins/langfuse/README.md) integrates [Langfuse](https://langfuse.com/) for AI
observability in Neuro SAN Studio, providing trace collection, cost tracking, and performance metrics
for LLM interactions. It supports both cloud and self-hosted Langfuse instances.

### LangSmith

[LangSmith](../neuro_san_studio/plugins/langsmith/README.md) is LangChain's built-in observability platform.
Since Neuro SAN uses LangChain internally, LangSmith tracing works out of the box with no plugin required — just set
`LANGSMITH_TRACING=true` and `LANGSMITH_API_KEY` in your `.env` file.
