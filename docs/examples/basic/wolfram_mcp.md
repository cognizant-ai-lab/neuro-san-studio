# Wolfram MCP

The **Wolfram MCP** agent network is a small, single-agent network designed to demonstrate
how to connect an agent to a remote Model Context Protocol (MCP) server using streamable
HTTP. It wires a `knowledge_agent` to the Wolfram Cloud MCP server, which exposes
Wolfram|Alpha's computational knowledge engine and the Wolfram Language evaluator.

---

## File

[wolfram_mcp.hocon](../../../registries/basic/wolfram_mcp.hocon)

---

## Description

This agent network provides one of the simplest possible examples of an agent backed by an
external MCP server. The single `knowledge_agent` delegates queries to the Wolfram Cloud
MCP server at `https://agenttools.wolfram.com/mcp`, which exposes three tools:

- `WolframContext` — context retrieval for grounding the conversation.
- `WolframLanguageEvaluator` — evaluates Wolfram Language expressions for symbolic
  computation, plotting, and general programmatic queries.
- `WolframAlpha` — natural-language queries against Wolfram|Alpha's curated knowledgebase
  covering math, science, geography, demographics, and other factual domains.

Because the tools return computed (not generated) results, the agent is well suited for
queries that need accurate numbers, formulas, or factual lookups — rather than free-form
prose generation. The free tier of the Wolfram MCP server is anonymous and requires no
API key, making this a good starting point for experimenting with remote MCP tools.

---

## Prerequisites

This agent network requires the following setup:

### Python Dependencies

Nothing special.

### Environment Variables

Nothing special. The Wolfram Cloud MCP server's free tier does not require authentication.

---

## Example Conversation

### Human

```text
Compute the integral of sin(x)^2 from 0 to pi.
```

### AI

```text
The definite integral of sin(x)^2 from 0 to pi is pi/2 (approximately 1.5708).
```

Other sample queries that exercise different Wolfram capabilities:

- `Convert 150 km/h to miles per second`
- `What is the distance from Earth to Mars today?`
- `What is the population and GDP of Japan compared to Germany?`

Your mileage will vary — the agent may rephrase or add intermediate steps depending on the
underlying LLM's choices.

---

## Architecture Overview

### Frontman Agent: knowledge_agent

- Main entry point for user inquiry.

- Interprets natural language queries and forwards them to the Wolfram MCP server, refining
  the query if the first attempt is ambiguous or incomplete.

- Presents the computed result back to the user, including relevant intermediate steps,
  formulas, or units when they help understanding.

There are no other agents in this network. The focus is on the simplest possible wiring of
an agent to a remote MCP server.

### MCP Tool: https://agenttools.wolfram.com/mcp

The agent's `tools` field is a single MCP server URL. neuro-san connects to it via the
streamable HTTP transport. The URL is a canonical MCP server URI (it contains `mcp` as a
path segment), so it can be passed as a plain string. For non-canonical URLs, use the
dictionary form `{"url": "https://example.com"}` instead.

---

## Debugging Hints

When developing or debugging with this network, keep the following in mind:

- **MCP server reachability**: The agent makes outbound HTTPS calls to
  `agenttools.wolfram.com`. Make sure the host running the agent can reach it (no
  firewall, proxy, or DNS issues).

- **Streamable HTTP only**: neuro-san's hocon-only MCP wiring supports streamable HTTP(S)
  transport. For other transports (stdio, SSE), implement the connection inside a coded
  tool instead.

- **Rate limits**: The free tier of Wolfram Cloud MCP is subject to rate limits and may
  occasionally return errors under heavy use. Refine the query and retry.

### Common Issues

- **No matching tool / empty results**: Wolfram|Alpha may not understand free-form prose
  well. The agent instructions encourage rephrasing — if you still get poor results,
  reword the query to be closer to a computational or factual question.

- **LLM not invoking the tool**: If the agent answers from its own knowledge instead of
  calling Wolfram, the model may have decided the question didn't need a tool. Strengthen
  the agent instructions or use a clearer computational prompt.

---

## Resources

- [Agent Network Hocon specification](https://github.com/cognizant-ai-lab/neuro-san/blob/main/docs/agent_hocon_reference.md)

- [Wolfram Cloud MCP overview](https://www.wolfram.com/artificial-intelligence/mcp/cloud/)
  Background on what the Wolfram MCP server exposes and how it differs from a typical
  web-search-backed tool.

- [Model Context Protocol specification](https://modelcontextprotocol.io/specification/2025-11-25/basic/authorization#canonical-server-uri)
  Definition of canonical MCP server URIs (relevant to the form of the `tools` URL used
  in this example).
