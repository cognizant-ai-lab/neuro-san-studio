# validate

Validates the *structure* of an agent network HOCON file against neuro-san's agent network validation rules. Use it to
catch problems before starting a server, for example:

- Agents that are referenced but not defined (missing nodes)
- Unreachable agents and front-man problems
- Invalid tool names
- Invalid URL references
- Malformed `tools` fields and unrecognized keywords

When the structure is valid, it also loads every coded tool and middleware class the network names, the way the
server does. See "Class check" below.

Unlike [`check-config`](./check_config.md), `validate` does **not** call any LLM, so it needs no API keys.

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

# Also print the manifest discovery summary, an agent network summary when validation passes,
# and the full error for each class that cannot be loaded
ns validate registries/basic/music_nerd.hocon --verbose
```

The command exits with code `0` when the file is valid and `1` when it is invalid, names a class that cannot be
loaded, or cannot be found, parsed, or otherwise loaded.

## Options

<!-- pyml disable line-length -->

| Option | Description |
|---|---|
| `--verbose` | Print how many external agent names were taken from the manifest, an agent network summary (agents, their type, and sub-tools) when validation passes, and the full error for each class that cannot be loaded. |
| `--manifest` | Manifest HOCON whose served networks are accepted as external agents. Defaults to `AGENT_MANIFEST_FILE`, then `<registry-dir>/registries/manifest.hocon`. |
| `--external-agents` | Additional comma-separated external agent references to treat as valid, on top of those discovered from the manifest, e.g. `'/agent1,/agent2'`. |
| `--mcp-servers` | Comma-separated MCP server URLs to treat as valid. |
| `--registry-dir` | Base directory for resolving HOCON `include` directives and for locating `registries/manifest.hocon`. Defaults to the first manifest's project root (the directory containing its `registries` folder), else the current directory. |

<!-- pyml enable line-length -->

## External agent references

An agent network can call another network by listing it as a tool with a leading slash, for example
`"/agent_network_editor"` or `"/tools/internet_info_gatherer"`. The validator only accepts such a reference when it
knows the target exists, so `validate` builds that list from the manifest:

1. The manifest is located using `--manifest`, then the `AGENT_MANIFEST_FILE` environment variable (typically set in
   `.env`), then `<registry-dir>/registries/manifest.hocon`, where `--registry-dir` defaults to the current directory.
   A list of manifests separated by the platform path separator (`:` on macOS and Linux) is composed as the server
   composes it: later manifests override earlier ones entry by entry, so an overlay can disable a network with
   `false` or re-enable one with `true`. `registries/manifest_multiuser_overlay.hocon` is such an overlay, and
   `deploy/Dockerfile` lists it after the main manifest.
2. Only **served** entries count: a key set to `true`, or a dictionary with `"serve": true`. An entry that is `false`,
   has `"serve": false`, or omits `serve` is not accepted, so a reference to it is reported. The same reference would
   fail once the server is running, because that network is not served.
3. Names are derived as the server derives them: `"tools/internet_info_gatherer.hocon"` becomes
   `/tools/internet_info_gatherer`.
4. Anything passed with `--external-agents` is added to the discovered list, so references to networks served
   elsewhere can still be allowed.

`include` directives inside a manifest are resolved relative to `--registry-dir` when given, otherwise relative to
that manifest's project root, the directory containing its `registries` folder. A manifest that lives elsewhere is
parsed from the current directory, as the server does.

If a manifest cannot be found, parsed, or processed, the command prints a warning to stderr, skips it, and continues
with the remaining manifests and any explicitly provided `--external-agents`, so the structural checks still run.

`--mcp-servers` plays the same role for MCP tool servers that the network references by URL.

## Class check

The structure checks never import the network's code, so a `"class"` that points at a module that was moved or
renamed would only fail when the server first uses it. After the structure checks pass, `validate` therefore loads
each coded tool and middleware class the network names, the way the server does:

- A coded tool's `"class"` is looked up from `AGENT_TOOL_PATH` and the network's name with neuro-san's own lookup, and
  must be a `CodedTool`. With `AGENT_TOOL_PATH_ONLY=true`, a reference is only looked up under `AGENT_TOOL_PATH`, as on
  the server, so a fully-qualified reference fails.
- An LLM agent's `"middleware"`, when it is not empty, must be a list of dictionaries, and the `"class"` of each
  one must be an `AgentMiddleware`.

Classes are loaded but not created, so a constructor that needs arguments is not caught. Toolbox tools are not checked,
because their classes come from the toolbox file, not the network file. A middleware's `"checkpointer"` class and an
`"llm_config"` class are not checked either.

Loading a class imports its module and runs the module's top-level code, as the server does. Modules come from the
project, or from installed packages for a class such as `langchain.agents.middleware.PIIMiddleware`. The check only
runs where the server would load the network:

- From the project root, the folder that holds the first manifest's `registries` folder. `ns run` is started there
  and reads the project's `.env`, which can set `AGENT_TOOL_PATH` and `AGENT_TOOL_PATH_ONLY`. A manifest that is not
  in a `registries` folder has no project root, so its networks are not checked.
- For a file inside the folder of a manifest. The path under that folder is the network's name:
  `registries/basic/music_nerd.hocon` is `basic/music_nerd`. With several manifests, the first one whose folder holds
  the file gives the name.

Otherwise the command prints `Class check skipped: ...` with the reason, and the class check does not affect the exit
code.

The check runs with the process set up the way `ns run` sets up the server. The project root comes first on the Python
path, ahead of the copies installed with the package, and `AGENT_TOOL_PATH` defaults to the project's `coded_tools`
folder.

## Output

On success the command prints `Validation passed: No errors found.` (followed by the agent network summary when
`--verbose` is set), then `Class check passed: N class reference(s) loaded.` On failure it prints each validation error
on its own numbered line. When a class cannot be loaded it prints `Class check failed with N error(s):` and one
numbered line per problem, naming the agent, or saying why no coded tool could be looked up at all. With `--verbose`, a
coded tool that cannot be found shows the server's full error, hints included. A manifest that could not be read
produces a `Warning: ...` line on stderr before the validation result.
