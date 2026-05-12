# CLI

<!-- TOC -->

- [CLI](#cli)
  - [Installation](#installation)
  - [Commands](#commands)
    - [`ns init`](#ns-init)
      - [Options](#options)
      - [Generated layout](#generated-layout)
      - [`llm_config.hocon` generation](#llm_confighocon-generation)
    - [`ns run`](#ns-run)
    - [`ns validate`](#ns-validate)
      - [Common flags](#common-flags)
      - [Exit codes](#exit-codes)
  - [Typical workflow](#typical-workflow)
  - [Troubleshooting](#troubleshooting)

<!-- /TOC -->

Neuro SAN Studio ships with a single command-line entry point, `ns`, registered
as a console script when you install the `neuro-san-studio` package. Use it to
scaffold a new project and to start the server.

## Installation

```bash
pip install neuro-san-studio
```

This makes the `ns` command available on your `PATH`. Confirm with:

```bash
ns --help
```

## Commands

The CLI is a [Click](https://click.palletsprojects.com/) command group. Two
subcommands are available today: `init` and `run`. Add `-h` / `--help` to any
command for inline reference.

### `ns init`

Scaffolds a new Neuro SAN Studio project at the given path.

```bash
ns init my-project
```

The target directory is created if it does not already exist. By default,
existing files at the target path are left alone (and reported as `skip`); pass
`--force` to overwrite them.

#### Options

| Option | Default | Description |
| --- | --- | --- |
| `PATH` (positional) | — | Directory to scaffold into. Created if missing. |
| `--force` / `--no-force` | `--no-force` | Overwrite files that already exist at the target path. |
| `--minimal` / `--with-example` | `--with-example` | Skip the `hello_world` example when `--minimal` is set. |

#### Generated layout

After `ns init my-project`, the new directory contains:

```text
my-project/
├── .env.example                  # copy to .env and fill in API keys
├── .gitignore
├── README.md
├── config/
│   ├── llm_config.hocon          # generated — see next section
│   └── plugins.hocon
├── coded_tools/                  # Python coded tools (AGENT_TOOL_PATH)
├── logs/                         # created empty, ignored by git
├── mcp/
│   └── mcp_info.hocon            # MCP server registrations
├── registries/
│   ├── manifest.hocon            # which agent networks this project serves
│   └── hello_world.hocon         # omitted with --minimal
└── toolbox/
    └── toolbox_info.hocon
```

Files that ship as dotfiles (`.env.example`, `.gitignore`) are stored in the
package without the leading dot and renamed during copy — some Python packagers
otherwise drop them from the wheel.

#### `llm_config.hocon` generation

`ns init` inspects your shell environment at scaffold time and writes
`config/llm_config.hocon` based on which provider API keys are present:

- **Exactly one key set** (e.g. only `OPENAI_API_KEY`): emits a single-provider
  config pointing at that provider's default model.
- **Multiple keys set**: emits an `llm_config.fallbacks` list ordered the same
  way as the providers were detected — the first key found is the primary
  provider and the rest become fallbacks.
- **No keys set**: emits a fallback list covering OpenAI and Anthropic with a
  banner comment reminding you to export at least one key before `ns run`.

The detection is keyed off `os.environ`, **not** the project's `.env` file
(which does not exist yet at this point). If you later switch providers, edit
`config/llm_config.hocon` by hand or re-run `ns init --force` against the same
path with new env vars exported.

Supported providers and their default models are defined in
[neuro_san_studio/cli.py](../neuro_san_studio/cli.py); see the
[`llm_config` reference](https://github.com/cognizant-ai-lab/neuro-san/blob/main/docs/agent_hocon_reference.md#llm_config)
for the full schema.

### `ns run`

Starts the Neuro SAN server and the nsflow client.

```bash
ns run
```

Run this from the root of a scaffolded project (the directory containing
`config/` and `registries/`). Default ports and behavior match the legacy
`python -m neuro_san_studio.run` entry point.

`ns run` forwards every flag verbatim to the underlying argparse-based runner.
For example:

```bash
ns run --server-http-port 8081 --client-only
```

is equivalent to invoking the runner directly with those flags. Because the
flags are passed through unmodified, `ns run --help` is **not** intercepted by
Click — it is handed to the runner, which prints its own help. See the
[user guide](./user_guide.md) and the runner's `--help` for the full flag list.

### `ns validate`

Shortcut for `python -m neuro_san.client.hocon_validator_cli`. Validates a
HOCON agent network file against neuro-san's agent-network rules — useful when
a network does not show up in the nsflow UI or otherwise misbehaves.

```bash
ns validate registries/hello_world.hocon
ns validate registries/hello_world.hocon --verbose
ns validate /tmp/my_agent.hocon --registry-dir /path/to/project
```

Like `ns run`, every flag is forwarded verbatim to the underlying validator,
so `ns validate --help` prints the validator's argparse help (not Click's).

#### Common flags

- **`--verbose`** — Print an agent network summary on success (agents,
  sub-tools, metadata).
- **`--external-agents '/a,/b'`** — Comma-separated list of valid external
  agent refs. Required when the network includes paths like
  `/agent_network_designer`, otherwise validation fails.
- **`--mcp-servers 'url1,url2'`** — Comma-separated list of valid MCP server
  URLs.
- **`--registry-dir DIR`** — Directory used to resolve
  `include "registries/..."` statements. Defaults to the parent of
  `AGENT_MANIFEST_FILE`'s parent, or the current working directory if unset.
- **`--json-output`** — Emit validation results as JSON.

For the full reference (including the temp-file copy trick used to resolve
includes), see the upstream
[`hocon_validator_cli` doc](https://github.com/cognizant-ai-lab/neuro-san/blob/main/docs/hocon_validator_cli.md).

#### Exit codes

`ns validate` propagates the underlying validator's exit code so CI and shell
pipelines can branch on it:

| Code | Meaning |
| --- | --- |
| `0` | Validation passed. |
| `1` | Validation errors found (count and details printed to stdout). |
| `2` | Could not load the file (not found, parse error, bad `--registry-dir`). |

> **Note:** `ns validate` expects an **agent network** HOCON, not a manifest.
> Pointing it at `registries/manifest.hocon` will produce confusing errors
> from deep inside the validator — pass the per-network file instead (e.g.
> `registries/hello_world.hocon`).

## Typical workflow

```bash
# 1. Install
pip install neuro-san-studio

# 2. Set at least one provider key so init writes a single-provider llm_config
export OPENAI_API_KEY=sk-...

# 3. Scaffold a project
ns init my-project
cd my-project

# 4. Move the example env file into place and edit it
cp .env.example .env
# ...edit .env...

# 5. Start the server + nsflow client
ns run
```

Then open the nsflow UI (default: <http://localhost:4173>) and run the
`hello_world` agent network.

## Troubleshooting

- **`ns: command not found`** — the package is not installed in the active
  environment, or the environment's `bin/` is not on `PATH`. Confirm with
  `pip show neuro-san-studio` and `which ns`.
- **`ns init` reports `skip` for every file** — the target directory already
  contains a scaffolded project. Re-run with `--force` to overwrite, or pick a
  fresh path.
- **`config/llm_config.hocon` lists providers you don't use** — no provider env
  var was set when you ran `ns init`, so the fallback list was emitted. Export
  the key you want and either re-run `ns init --force` or edit the file by
  hand to remove the providers you do not need.
- **`ns run` exits immediately with an argparse error** — the flag was rejected
  by the underlying runner, not by Click. Check `ns run --help` for the
  accepted flag names.
