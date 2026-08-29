---
name: agent-network-designer
description: Generate or iterate on a neuro-san-studio agent network baseline from a plain-English use case via
  the Agent Network Designer one-shot CLI flow. Use when asked to build, scaffold, or design a network.
---

# Agent Network Designer

Write the use case (or the change you want) to a file, then run one-shot:

```bash
echo "Build a network for a coffee shop's order-status and loyalty-points lookup" > /tmp/prompt.txt
ns chat agent_network_designer --one-shot --first_prompt_file /tmp/prompt.txt
```

Produces agents, links, instructions, toolbox/mcp wiring, and sample_queries; registers the manifest entry;
saves under `registries/generated/`. To iterate on an existing generated network, pass it via `--sly_data`:

```bash
ns chat agent_network_designer --one-shot --first_prompt_file /tmp/prompt.txt \
  --sly_data '{"agent_network_hocon_file": "registries/generated/coffee_shop.hocon"}'
```

The Designer gives a baseline only — refining the `.hocon` yourself (see the `agent-network-hocon-reference` skill) is
expected.
Docs: [agent_network_designer.md](../../../docs/examples/agent_network_designer.md).
