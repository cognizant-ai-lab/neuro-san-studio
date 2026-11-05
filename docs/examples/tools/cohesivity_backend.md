# Cohesivity Backend

[Cohesivity Backend](../../../registries/tools/cohesivity_backend.hocon) is a single-agent system that
provisions managed backend infrastructure through the [Cohesivity](https://cohesivity.ai) MCP server.
It creates a temporary tenant and provisions PostgreSQL, Redis, object storage, vector databases,
hosting, and APIs on request. No account or API keys are required to start. Unclaimed tenants and
their resources expire after 72 hours.

The agent connects to `https://cohesivity.ai/mcp`, configured in
[mcp\_info.hocon](../../../neuro_san_studio/mcp/mcp_info.hocon). It is enabled by default and needs no
credentials. The agent asks before it creates a tenant, provisions a resource, or claims a tenant.

## LLM providers

| Provider | Result |
| --- | --- |
| OpenAI, Responses API (the default in neuro-san 0.7.12) | All six tools work |
| OpenAI, Chat Completions | The request fails because `provision_resource` has `oneOf` at the top level |
| Anthropic | langchain-anthropic drops `provision_resource`, so the agent can't provision |
| Gemini | The request fails because `confirmed` in `create_tenant` and `claim_tenant` is a boolean enum |

## Tools

| Tool | What it does |
| --- | --- |
| `get_cohesivity_documentation` | Reads resource catalog, pricing, onboarding, and API reference |
| `create_tenant` | Creates one temporary tenant with a 72-hour expiry |
| `provision_resource` | Provisions one or more resources on a tenant |
| `tenant_status` | Reports lifecycle, limits, resources, runtime state, and notifications |
| `claim_tenant` | Returns an approval URL to make the tenant permanent |
| `give_feedback` | Reports a problem or suggestion |

## Example queries

```text
Create a temporary backend with PostgreSQL and object storage for my app.
Provision a Redis cache and check its status.
What backend resources does Cohesivity offer?
```

## See also

- [Resource catalog](https://cohesivity.ai/offerings)
- [Cohesivity documentation](https://cohesivity.ai/docs)
- [MCP server configuration](../../../neuro_san_studio/mcp/mcp_info.hocon)
