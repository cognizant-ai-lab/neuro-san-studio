# new

Scaffold a new agent network or coded tool inside the current project.

Run from the **project root** (the directory that contains `registries/` and `config/`).

## Subcommands

### `ns new network NAME`

Create a new agent network:

- `registries/<name>.hocon` — a minimal single-agent HOCON file ready to run.
- `registries/manifest.hocon` — the new network is registered automatically.
- `tests/fixtures/<name>/sample.hocon` — a starter integration-test fixture.

```bash
ns new network my_network
```

The generated HOCON includes the standard `llm_config` and `expertise_scoping_instructions` includes,
a named front-man agent, and an empty `tools` list. Edit the file to build out your agent network,
then start the server with `ns run` and chat with it using `ns chat my_network`.

### `ns new tool NAME`

Create a new `CodedTool` subclass:

- `coded_tools/<name>/<name>.py` — a `CodedTool` subclass with `async_invoke` stubbed out.
- `coded_tools/<name>/__init__.py` — package marker.
- `tests/neuro_san_studio/coded_tools/test_<name>.py` — a unit test stub.

```bash
ns new tool my_tool
```

After filling in `async_invoke`, reference the tool in a network's `tools` list with
`"class": "my_tool.my_tool.MyTool"` — the full dotted path relative to `coded_tools/`.

## Usage

```bash
ns new network NAME   # scaffold a network
ns new tool NAME      # scaffold a coded tool
ns new --help         # list subcommands
```

## Naming rules

Names must be **lowercase**, start with a letter, and contain only letters, digits, and underscores
(e.g. `weather_agent`, `fetch_data`). The command rejects anything else with an `[err]` message and
exits without creating any files.

## Idempotency

Re-running the same command is safe: existing files are left untouched and reported as `[skip]`.
The manifest entry is also skipped if the network is already listed.

## Options

| Option | Description |
|---|---|
| `NAME` | Snake-case name for the network or tool (positional, required). |
| `--help` | Show usage and exit. |
