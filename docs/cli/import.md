# import

Imports agent networks (and their dependencies) into the current project. Two
modes: discovery-driven (pull networks from the installed neuro-san-studio
package) and file-based (pass a path ending in `.hocon` or `.zip` to install a
single network or bundle from disk).

## Usage

### Interactive

```bash
ns import
```

Top menu (single-select, Enter to pick):

- One per group — `Basic (N)`, `Industry (N)`, etc. — imports the whole group
- `Custom selection` — drills into a two-step picker
- `All (N)` — imports every network

`Custom selection` flow:

1. Pick groups to narrow the network list (Space=select, Enter=continue, ←=back; Enter with none = all groups)
2. Pick networks within those groups (Space=toggle, A=toggle all, Enter=continue, ←=back)
3. Confirm the listed networks (y/N)

`←` at any sub-screen discards selections and backs up one level.

### Non-interactive

```bash
ns import basic                          # one group
ns import industry experimental          # multiple groups
ns import all                            # everything
ns import music_nerd                     # one network (any group)
ns import basic agent_network_designer   # mix
```

Arguments without a file extension are resolved against the installed package's
registry (groups, network names, or `all`).

### From a local file

A positional argument ending in `.hocon` or `.zip` is imported as a local file,
no flag required. Pass one or more, space-separated, to import them in one call:

```bash
ns import path/to/network.hocon            # self-contained single HOCON
ns import music_nerd.hocon                 # bare name resolved in the current directory
ns import path/to/bundle.zip               # network + dependencies
ns import a.hocon path/to/b.zip            # multiple files in one call
ns import path/to/bundle.zip --force       # overwrite existing files
```

The `.hocon` / `.zip` extension is what selects file mode; an extensionless
argument is always a registry lookup. Every token must be the same kind; mixing
file paths with registry names in one call is rejected. Pair with
[`ns export`](./export.md) to ship a network between projects.

#### Source shapes

| File | Contents |
|---|---|
| `*.hocon` | A single network with no dependencies. Lands at `registries/<basename>.hocon`. |
| `*.zip` | A self-contained bundle. Top-level entries must be under `registries/`, `coded_tools/`, `middleware/`, or `mcp/` — anything else is rejected. |

Zips are treated as **closed packages**: the importer does not walk
`DependencyAnalyzer` against zip contents and will not look outside the archive
for missing deps. Sub-networks, coded tools, and middleware referenced by the
bundled HOCON must already be inside the bundle.

#### Path preservation

Archive paths land verbatim under the project root:

| Archive entry | Lands at | Registered in manifest as |
|---|---|---|
| `registries/my_network.hocon` | `<project>/registries/my_network.hocon` | `my_network.hocon` |
| `registries/industry/my_network.hocon` | `<project>/registries/industry/my_network.hocon` | `industry/my_network.hocon` |
| `coded_tools/my_network/foo.py` | `<project>/coded_tools/my_network/foo.py` | (n/a) |
| `middleware/my_network/bar.py` | `<project>/middleware/my_network/bar.py` | (n/a) |
| `mcp/mcp_info.hocon` | merged additively into `<project>/mcp/mcp_info.hocon` | (n/a) |

Single-HOCON file imports have no enclosing directory, so they land at
`<project>/registries/` with their basename.

#### Zip safety

Every entry is checked before extraction:

1. **Zip-slip**: each destination must resolve under the project root.
2. **Top-level whitelist**: only `registries/`, `coded_tools/`, `middleware/`,
   `mcp/` prefixes are accepted; everything else (READMEs, `__pycache__`, OS
   metadata) is silently skipped.
3. **No symlinks**: entries with symlink mode bits are rejected.
4. **Soft caps**: total uncompressed size ≤ 100 MB, ≤ 100 entries.

### MCP servers

Imports never replace existing entries in `<project>/mcp/mcp_info.hocon` —
merging is always additive, **even with `--force`**:

| Receiver state | Outcome |
|---|---|
| URL not present | Block spliced in before the closing `}`. |
| URL already present | Bundled block is skipped; receiver's config (including any `${ENV}` substitutions) is preserved verbatim. |

Discovery-driven imports follow the same rule: when a chosen network references
an MCP URL, only the matching block from the studio's bundled
`mcp_info.hocon` is merged into the project file.

## Dependency resolution

Imported alongside each network:

- HOCON `include` files
- Coded tools (`class` fields)
- Middleware (`middleware` arrays)
- Sub-networks (`/network_name` references) — transitively
- MCP tool URLs (`http://` / `https://`) — referenced server config is merged into `<project>/mcp/mcp_info.hocon` (additive; existing URLs preserved)

Shared registry HOCONs (`aaosa.hocon`, `aaosa_basic.hocon`, `aaosa_basic_debug.hocon`) are scaffolded by `ns init`; the importer copies them as a safety net if missing.

## Manifest

`registries/manifest.hocon` is updated in JSON form, sorted, with new entries merged in:

```hocon
{
    "basic/music_nerd.hocon": true,
    "agent_network_designer.hocon": true
}
```

A running server auto-reloads within ~5s.

## Idempotency

Existing files are skipped, not overwritten. Re-running is safe. Pass `--force`
to overwrite existing files in the target — `<project>/mcp/mcp_info.hocon`
is exempt and always merged additively.

## Network naming

Registry lookups use extensionless names (an argument ending in `.hocon`/`.zip`
is treated as a local file instead; see the [From a local file](#from-a-local-file)
section).

| Format | Example |
|---|---|
| Bare name | `music_nerd` |
| Group/name | `basic/music_nerd` |
| Root network | `agent_network_designer` |

## Requirements

Run from a project initialized with `ns init` (must contain `registries/manifest.hocon`). neuro-san-studio must be importable.

## Exit codes

| Code | Meaning |
|---|---|
| 0 | Success |
| 1 | Project not initialized, or import failed |
