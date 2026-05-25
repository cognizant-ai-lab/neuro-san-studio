# add

Adds agent networks to an existing neuro-san-studio project. This command discovers available agent networks from the neuro-san-studio installation, analyzes their dependencies (coded tools, middleware, sub-networks, HOCON includes), and installs them into your project with all required files.

## Usage

### Interactive mode (recommended)

```bash
# Launch interactive checkbox UI to select networks
ns add
```

The interactive mode presents a checkbox interface where you can:
1. Select entire groups (basic, industry, experimental, tools, root)
2. Choose "Custom Selection" to pick individual networks
3. Choose "All" to install everything

### Non-interactive mode

```bash
# Install specific networks by name
ns add coffee_finder_advanced
ns add agent_network_designer

# Install entire groups
ns add basic
ns add industry,experimental

# Install all networks from all groups
ns add all

# Install root-level networks (agent_network_designer, etc.)
ns add root

# Combine groups and specific networks
ns add basic,agent_network_designer
ns add coffee_finder,music_nerd_pro,industry
```

## Network groups

Agent networks are organized into groups:

| Group | Description | Count |
|---|---|---|
| **basic** | Simple examples and tutorials | 17 networks |
| **industry** | Domain-specific use cases (retail, insurance, banking, etc.) | 22 networks |
| **experimental** | Research and advanced features (CRUSE, conscious agents, etc.) | 9 networks |
| **tools** | Tool integrations (RAG, search, code execution, etc.) | 28 networks |
| **root** | Meta-networks (agent_network_designer, editor, etc.) | 6 networks |

## Dependency resolution

The `add` command automatically resolves and installs all dependencies:

- **HOCON includes** - Configuration files referenced via `include` directives
- **Coded tools** - Python classes referenced via `class` fields
- **Middleware** - Middleware components from `middleware` arrays
- **Sub-networks** - Other agent networks referenced via `/network_name` syntax
- **Transitive dependencies** - Dependencies of sub-networks are also installed

For example, installing `agent_network_designer` will automatically install:
- The main `agent_network_designer.hocon` file
- Sub-networks: `agent_network_editor`, `agent_network_query_generator`, `agent_network_instructions_editor`
- Middleware: `agent_network_definition_middleware`, persistence layer, validation layer
- Coded tools: 10+ Python files for network manipulation

## Idempotency

The command is safe to run multiple times:
- Files that already exist are skipped (not overwritten)
- The manifest is updated to include newly installed networks
- Running `ns add --networks X` twice will skip all files on the second run

## Manifest updates

The command automatically updates `registries/manifest.hocon` to register newly installed networks. The manifest follows this format:

```hocon
{
    "basic/music_nerd.hocon": true,
    "basic/coffee_finder_advanced.hocon": true,
    "agent_network_designer.hocon": true
}
```

Networks are added in alphabetical order. The server will auto-reload the manifest within 5 seconds if it's already running.

## Output

The command provides progress updates and a summary:

```
🔍 Discovering available agent networks...

📦 Installing 3 network(s)...

   Analyzing basic/coffee_finder_advanced.hocon...
   Installing basic/coffee_finder_advanced.hocon...
   Analyzing agent_network_designer.hocon...
   Installing agent_network_designer.hocon...

   Updating manifest...

📊 Summary:
   ✅ Copied: 42 files
   ⏭️  Skipped: 5 files (already exist)

✅ Installation complete!

💡 Next steps:
   - Run 'ns run' to start the server
   - The manifest will auto-reload within 5 seconds
```

## Examples

### Starting a new project

```bash
# Initialize project with basic setup
ns init --providers openai

# Add industry-specific networks
ns add industry

# Add specific advanced networks
ns add agent_network_designer,cruse_agent
```

### Exploring available networks

```bash
# Use interactive mode to browse all available networks
ns add
# Use arrow keys and space to select, then Enter to install
```

### Installing everything

```bash
# Install all 82+ agent networks
ns add all,root
```

## Network naming

Networks can be specified in multiple formats:

| Format | Example | Notes |
|---|---|---|
| Just name | `music_nerd` | Searches all groups |
| Group/name | `basic/music_nerd` | Explicit group path |
| With extension | `basic/music_nerd.hocon` | Also supported |
| Root networks | `agent_network_designer` | No group prefix |

## Requirements

- Must run from an initialized neuro-san-studio project (after `ns init`)
- If run from uninitialized directory, will show error and suggest running `ns init` first
- Requires neuro-san-studio to be installed (via pip or in development mode)

## Exit codes

| Code | Meaning |
|---|---|
| 0 | Success - all networks installed |
| 1 | Error - project not initialized or installation failed |
