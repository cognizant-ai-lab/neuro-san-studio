# export

Bundles an agent network from the current project into the exact shape that
`ns import -f` consumes. The output format is auto-detected from the network's
dependencies: a self-contained `.hocon` if there are none, a `.zip` carrying the
network plus its deps otherwise.

Pairs round-trip with [`ns import -f`](./import.md#from-a-local-file--f). Build a
network in one project, run `ns export`, ship the file, run `ns import -f` on
the receiver.

## Usage

### Interactive

```bash
ns export
```

A single-select picker over the project's manifest. Networks are grouped by
directory prefix (e.g. `BASIC`, `INDUSTRY`); pick one with arrow keys + Enter.
Ctrl-C / Esc exits cleanly without writing anything.

### Non-interactive

```bash
ns export music_nerd                          # → music_nerd.{hocon|zip} in cwd
ns export basic/music_nerd                    # grouped network
ns export agent_network_designer -o /tmp/and.zip
ns export music_nerd -o /tmp/mn.hocon         # explicit single-HOCON output
```

`-o` / `--output` overrides the default file path.

## Output format

| Network shape | Default output | `-o` override |
|---|---|---|
| No deps (LLM-only `tools` array) | `<network>.hocon` in cwd | `*.hocon` only — `*.zip` is rejected |
| Any deps (sub-networks, coded tools, middleware, MCP URLs, shared includes) | `<network>.zip` in cwd | `*.zip` only — `*.hocon` is rejected |

Mismatches (e.g. `-o foo.hocon` on a network with deps) error out before any
file is written. The intent is that the bundle's shape is the contract: a
receiver always knows whether to expect a single file or an archive.

## What's in a zip

```
registries/<network>.hocon            # the network itself
registries/<sub_network>.hocon        # transitive sub-networks
registries/<shared_include>.hocon     # files referenced via `include "registries/..."`
coded_tools/<package>/...             # full package trees with __init__.py
middleware/<package>/...              # ditto
mcp/mcp_info.hocon                    # filtered to the URLs this network uses
```

`registries/manifest.hocon` is **never** included — the receiver's manifest is
merged additively at import time, not replaced.

## Export metadata

The exporter stamps three provenance keys into the network's top-level
`metadata` block (creating the block if the network has none). Existing metadata
keys are preserved and everything stays in one `metadata` block:

| Key | Example | Meaning |
|---|---|---|
| `export_user` | `alice` | System user who ran the export |
| `export_time` | `20260611-155014-IST` | Export timestamp, `YYYYMMDD-hhmmss-TZ`, system-local timezone |
| `export_neuro_san_studio_version` | `0.3.3` | Version of neuro-san-studio that produced the bundle |

These let a receiver trace which studio version a bundle was saved with. Only
the primary network file is stamped; sub-networks and shared includes are
bundled verbatim.

## MCP server filtering

If the network references any MCP URLs in its `tools` arrays, the exporter
filters the project's `<project>/mcp/mcp_info.hocon` (or the studio package's
bundled fallback if the project hasn't scaffolded one) down to just those URL
blocks and writes them as `mcp/mcp_info.hocon` in the zip. Inline comments and
`${ENV_VAR}` substitutions in the receiver's config are preserved verbatim
through the round-trip.

URLs referenced by the network but not present in any source `mcp_info.hocon`
surface as a warning rather than silently shipping an empty config.

## Network naming

| Format | Example |
|---|---|
| Bare name | `music_nerd` (resolved across every group) |
| Group/name | `basic/music_nerd` |
| With extension | `basic/music_nerd.hocon` |

## Requirements

Run from a project initialized with `ns init` (must contain
`registries/manifest.hocon`). The network must be reachable from the project's
`registries/` directory.

## Exit codes

| Code | Meaning |
|---|---|
| 0 | Success |
| 1 | Project not initialized, network not found, or export failed |
