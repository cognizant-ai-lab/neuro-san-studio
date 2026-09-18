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
`python -m neuro_san.client.hocon_validator_cli`), so it stays in sync with the library's validation rules. On top of
that, it reads the project's manifest so that references to other agent networks are recognized. See "External agent
references" below.

## Usage

```bash
# Validate an agent network HOCON file
neuro-san-studio validate registries/basic/music_nerd.hocon

# Same command via the shorter alias
ns validate registries/basic/music_nerd.hocon

# A network that calls other networks validates with no extra flags:
# "/agent_network_editor" and friends are looked up in registries/manifest.hocon
ns validate registries/agent_network_designer.hocon

# Print the manifest discovery summary, and an agent network summary when validation passes
ns validate registries/basic/music_nerd.hocon --verbose
```

The command exits with code `0` when the file is valid and `1` when it is invalid or cannot be found, parsed, or
otherwise loaded.

## Options

<!-- pyml disable line-length -->

| Option | Description |
|---|---|
| `--verbose` | Print how many external agent names were taken from the manifest, and an agent network summary (agents, their type, and sub-tools) when validation passes. |
| `--manifest` | Manifest HOCON whose served networks are accepted as external agents. Defaults to `AGENT_MANIFEST_FILE`, then `<registry-dir>/registries/manifest.hocon`. |
| `--external-agents` | Additional comma-separated external agent references to treat as valid, on top of those discovered from the manifest, e.g. `'/agent1,/agent2'`. |
| `--mcp-servers` | Comma-separated MCP server URLs to treat as valid. |
| `--registry-dir` | Base directory for resolving HOCON `include` directives and for locating `registries/manifest.hocon`. Defaults to the current directory. |

<!-- pyml enable line-length -->

## External agent references

An agent network can call another network by listing it as a tool with a leading slash, for example
`"/agent_network_editor"` or `"/tools/internet_info_gatherer"`. The validator only accepts such a reference when it
knows the target exists, so `validate` builds that list from the manifest:

1. The manifest is located using `--manifest`, then the `AGENT_MANIFEST_FILE` environment variable (typically set in
   `.env`), then `<registry-dir>/registries/manifest.hocon`, where `--registry-dir` defaults to the current directory.
   A list of manifests separated by the platform path separator (`:` on macOS and Linux) is accepted, as it is for
   the server.
2. Only **served** entries count: a key set to `true`, or a dictionary with `"serve": true`. An entry that is `false`,
   has `"serve": false`, or omits `serve` is not accepted, so a reference to it is reported. The same reference would
   fail once the server is running, because that network is not served.
3. Names are derived as the server derives them: `"tools/internet_info_gatherer.hocon"` becomes
   `/tools/internet_info_gatherer`.
4. Anything passed with `--external-agents` is added to the discovered list, so references to networks served
   elsewhere can still be allowed.

`include` directives inside the manifest are resolved relative to `--registry-dir` when given, otherwise relative to
the manifest's grandparent directory, which is the project root in the standard `registries/manifest.hocon` layout.

If the manifest cannot be found or parsed, the command prints a warning to stderr and continues with only the
explicitly provided `--external-agents`, so the structural checks still run.

`--mcp-servers` plays the same role for MCP tool servers that the network references by URL.

## Output

On success the command prints `Validation passed: No errors found.` (followed by the agent network summary when
`--verbose` is set). On failure it prints each validation error on its own numbered line. A manifest that could not be
read produces a `Warning: ...` line on stderr before the validation result.
