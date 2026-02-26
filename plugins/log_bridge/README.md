# Log Bridge Plugin

This plugin provides a Rich-based structured logging bridge for Neuro SAN Studio, replacing raw subprocess output with colored, pretty-printed, and severity-aware console logs.

## Features

- **Rich console output** with colored, timezone-aware timestamps
- **Automatic severity inference** from JSON `message_type` fields or text-level tokens (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- **Pretty-printed JSON** with nested JSON expansion (JSON-inside-`"message"` is parsed and indented)
- **Traceback detection and highlighting** — Python tracebacks are normalized and syntax-highlighted via Rich
- **Multi-line JSON reassembly** using brace-balanced collection across lines
- **Per-process log file mirroring** — raw output is tee'd to individual log files for post-mortem analysis
- **Configurable themes and formatting** via the `log_cfg` dictionary (colors, timestamp style, file rotation)
- **Non-invasive integration** — falls back to basic streaming when disabled; no changes to core Neuro SAN code

## Installation

No additional installation is required. The Log Bridge depends on [Rich](https://rich.readthedocs.io/), which is already included in the project's `requirements.txt`.

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `LOGBRIDGE_ENABLED` | `true` | Enable or disable the Rich logging bridge |

### Example `.env` Configuration

**Enabled (default):**
```bash
LOGBRIDGE_ENABLED=true
```

**Disabled:**
```bash
LOGBRIDGE_ENABLED=false
```

### Advanced Configuration

The `log_cfg` dictionary at the top of `plugins/log_bridge/process_log_bridge.py` controls formatting details. You can customize it without code changes by passing an override `config` dict when constructing `ProcessLogBridge`.

#### Theme (colors and styles)

```python
"theme": {
    "logging.time": "bright_cyan",        # Timestamp color
    "logging.level.error": "bold red",    # Error level style
}
```

Rich supports named colors (`"cyan"`, `"bright_cyan"`, `"magenta"`), hex (`"#34d399"`), RGB (`"rgb(52,211,153)"`), and color index (`"color(118)"`).

#### Rich Handler Settings

```python
"rich": {
    "show_time": True,     # Show timestamps
    "show_path": False,    # Hide file paths in output
}
```

#### File Handler Settings

```python
"file": {
    "when": "midnight",       # Rotation interval
    "backupCount": 10,        # Number of rotated log files to keep
    "fmt": "%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d - %(message)s",
}
```

## Architecture

### Plugin-Based Design

The Log Bridge is a self-contained plugin in `plugins/log_bridge/`. When enabled, it intercepts subprocess stdout/stderr streams and processes each line through a parsing pipeline before emitting formatted output to the console. When disabled, `run.py` falls back to basic threaded log streaming.

### Key Components

#### ProcessLogBridge Class

The `ProcessLogBridge` class (in `plugins/log_bridge/process_log_bridge.py`) manages:

- **Initialization**: Configures a Rich console with themed `RichHandler`, optional `TimedRotatingFileHandler` for runner-wide log files, and reconfigures the root Python logger
- **Process attachment**: `attach_process_logger()` spawns daemon threads that drain subprocess stdout/stderr pipes
- **Line handling pipeline**: Each line is routed through a decision tree:
  1. Attempt single-line JSON parse
  2. Attempt multi-line JSON reassembly (brace-balanced)
  3. Fall back to plain text emission
- **Severity inference**: Log levels are inferred from JSON `message_type` fields or by scanning text for severity keywords
- **Traceback normalization**: Python tracebacks embedded in JSON `message` fields are detected, reformatted, and syntax-highlighted

#### TZFormatter Class

A `logging.Formatter` subclass that emits timezone-aware timestamps (`YYYY-MM-DD HH:MM:SS TZ`) in file log output.

#### Per-Stream State

Each attached subprocess stream (stdout, stderr) maintains independent state for:
- **Tee file handle** — mirrors raw lines to a per-process log file
- **JSON reassembly buffer** — collects lines when a multi-line JSON block is detected
- **Brace balance counter** — tracks `{`/`}` nesting to know when a JSON block is complete

### Integration with run.py

The runner (`run.py`) integrates the Log Bridge in two places:

1. **Initialization** — when `LOGBRIDGE_ENABLED` is truthy, a `ProcessLogBridge` instance is created with the configured log level and a runner-wide log file path (`logs/runner.log`)
2. **Process attachment** — each launched subprocess (server, web client, nsflow) is attached via `log_bridge.attach_process_logger(process, name, log_file)`, which spawns drain threads for both stdout and stderr

### Design Decisions

- **Daemon threads for pipe draining**: Ensures subprocess output is consumed without blocking the main runner, and threads exit automatically when the main process terminates
- **Tee pattern**: Raw lines are written to per-process log files before any parsing, preserving original output for debugging even if the pretty-printer encounters issues
- **Brace-balanced JSON reassembly**: Handles JSON payloads that span multiple lines (common in Neuro SAN's structured logging) without requiring a fixed line count or delimiter
- **Graceful error handling**: All I/O operations in the bridge are wrapped in broad exception handlers to ensure logging never crashes the application

## Usage

The Log Bridge is **enabled by default**. When you start Neuro SAN Studio:

```bash
python -m run
```

You will see Rich-formatted console output with:
- Colored timestamps in `[YYYY-MM-DD HH:MM:SS TZ]` format
- JSON logs pretty-printed with indentation
- Severity-appropriate color coding (errors in red, warnings in yellow, etc.)
- Python tracebacks syntax-highlighted

### Log Files

Per-process log files are written to the `logs/` directory:
- `logs/runner.log` — aggregated runner-level logs
- `logs/<process_name>.log` — raw output per subprocess (server, web client, etc.)

### Console Output Example

When a JSON log line like this arrives from the server:

```json
{"message_type": "info", "source": "HttpServer", "message": "Request received", "request_id": "abc-123"}
```

The Log Bridge renders it as a colored, indented block in the console with the appropriate INFO severity.

## Disabling the Log Bridge

To disable the Log Bridge and use basic log streaming:

```bash
# In .env file
LOGBRIDGE_ENABLED=false
```

When disabled, `run.py` falls back to simple threaded output streaming without Rich formatting, JSON parsing, or per-process log files.

## Troubleshooting

### Console output is not colored

- Verify your terminal supports ANSI colors
- Check that `LOGBRIDGE_ENABLED` is not set to `false`
- Ensure Rich is installed: `pip list | grep rich`

### JSON logs are not pretty-printed

- The bridge only pretty-prints lines that parse as valid JSON dictionaries
- Multi-line JSON blocks require balanced braces — if a block is malformed, it falls back to plain text

### Log files are not created

- Check that the `logs/` directory is writable
- Verify `LOGBRIDGE_ENABLED=true` is set (file logging is part of the bridge)

### Traceback highlighting is missing

- Tracebacks must contain standard Python markers (`Traceback (most recent call last):` or `File "...", line N`)
- The bridge detects these patterns and applies Rich syntax highlighting automatically

## Learn More

- [Rich Documentation](https://rich.readthedocs.io/en/latest/)
- [Rich Logging Handler](https://rich.readthedocs.io/en/latest/logging.html)
- [Rich Themes and Styles](https://rich.readthedocs.io/en/latest/style.html)
- [Python logging — TimedRotatingFileHandler](https://docs.python.org/3/library/logging.handlers.html#timedrotatingfilehandler)
