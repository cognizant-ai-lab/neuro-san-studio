# Neuro SAN Studio project

Scaffolded by `ns init`.

## Quick start

```bash
cp .env.example .env        # fill in at least one LLM provider key
ns run                      # starts the server + nsflow client
```

Then open the nsflow UI (default: http://localhost:4173) and run the
`hello_world` agent network.

## Layout

- `config/plugins.hocon` — runtime plugins enabled at startup
- `config/llm_config.hocon` — shared LLM provider/model settings
- `registries/manifest.hocon` — agent networks served by this project
- `registries/hello_world.hocon` — starter agent network
- `coded_tools/` — Python coded tools loaded via `AGENT_TOOL_PATH`
- `toolbox/toolbox_info.hocon` — toolbox tools available to agents
- `mcp/mcp_info.hocon` — MCP server registrations

## References

- Project docs: https://github.com/cognizant-ai-lab/neuro-san-studio
- Manifest schema: https://github.com/cognizant-ai-lab/neuro-san/blob/main/docs/manifest_hocon_reference.md
- Agent network schema: https://github.com/cognizant-ai-lab/neuro-san/blob/main/docs/agent_hocon_reference.md
