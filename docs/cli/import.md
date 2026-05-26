# import

Imports agent networks (and their dependencies) from the installed neuro-san-studio package into the current project.

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
ns import basic                       # one group
ns import industry,experimental       # multiple groups
ns import all                         # everything
ns import music_nerd                  # one network (any group)
ns import basic,agent_network_designer  # mix
```

## Dependency resolution

Imported alongside each network:

- HOCON `include` files
- Coded tools (`class` fields)
- Middleware (`middleware` arrays)
- Sub-networks (`/network_name` references) — transitively
- MCP tool URLs (`http://` / `https://`) — recorded for visibility but not copied (remote endpoints)

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

Existing files are skipped, not overwritten. Re-running is safe.

## Network naming

| Format | Example |
|---|---|
| Bare name | `music_nerd` |
| Group/name | `basic/music_nerd` |
| With extension | `basic/music_nerd.hocon` |
| Root network | `agent_network_designer` |

## Requirements

Run from a project initialized with `ns init` (must contain `registries/manifest.hocon`). neuro-san-studio must be importable.

## Exit codes

| Code | Meaning |
|---|---|
| 0 | Success |
| 1 | Project not initialized, or import failed |
