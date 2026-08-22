# validate

Validates the *structure* of an agent network HOCON file against neuro-san's agent network validation rules. Use it to
catch problems before starting a server, for example:

- Agents that are referenced but not defined (missing nodes)
- Unreachable agents and front-man problems
- Invalid tool names
- Invalid URL references
- Malformed `tools` fields and unrecognized keywords

Unlike [`check-config`](./check_config.md), `validate` does **not** call any LLM — it performs purely structural
validation, so it needs no API keys.

Under the hood this command delegates to neuro-san's `HoconValidatorCli` (the tool also available as
`python -m neuro_san.client.hocon_validator_cli`), so it stays in sync with the library's validation rules.

## Usage

```bash
# Validate an agent network HOCON file
neuro-san-studio validate registries/music_nerd.hocon

# Same command via the shorter alias
ns validate registries/music_nerd.hocon

# Print an agent network summary when validation passes
ns validate registries/music_nerd.hocon --verbose
```

The command exits with code `0` when the file is valid and `1` when it is invalid or cannot be found, parsed, or
otherwise loaded.

## Options

| Option | Description |
|---|---|
| `--verbose` | Print an agent network summary (agents, their type, and sub-tools) when validation passes. |
| `--external-agents` | Comma-separated external agent references to treat as valid, e.g. `'/agent1,/agent2'`. |
| `--mcp-servers` | Comma-separated MCP server URLs to treat as valid. |
| `--registry-dir` | Base directory for resolving HOCON `include` directives. Defaults to the current directory. |

`--external-agents` and `--mcp-servers` exist because an agent network may reference agents or tool servers that live
outside the file being validated. Listing them tells the validator they are legitimate so it does not report them as
missing.

## Output

On success the command prints `Validation passed: No errors found.` (followed by the agent network summary when
`--verbose` is set). On failure it prints each validation error on its own numbered line.
