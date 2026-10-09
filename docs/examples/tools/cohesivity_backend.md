# Cohesivity Backend

[Cohesivity Backend](../../registries/tools/cohesivity_backend.hocon) is a single-agent system that
provisions managed backend infrastructure through the [Cohesivity](https://cohesivity.ai) MCP server.
It creates a temporary tenant and provisions PostgreSQL, Redis, object storage, vector databases,
hosting, and APIs on request. No account or API keys are required to start. Unclaimed tenants and
their resources expire after 72 hours.

The agent connects to `https://cohesivity.ai/mcp`, configured in
[mcp\_info.hocon](../../neuro_san_studio/mcp/mcp_info.hocon). It is enabled by default and needs no
credentials.

## Tools

| Tool | What it does |
| --- | --- |
| `get_cohesivity_documentation` | Reads resource catalog, pricing, onboarding, and API reference |
| `create_tenant` | Creates one temporary tenant with a 72-hour expiry |
| `provision_resource` | Provisions one or more resources on a tenant |
| `tenant_status` | Reports lifecycle, resource status, and connection details |
| `claim_tenant` | Returns an approval URL to make the tenant permanent |
| `give_feedback` | Reports a problem or suggestion |

## Example queries

```text
Create a temporary backend with PostgreSQL and object storage for my app.
Provision a Redis cache and check its status.
What backend resources does Cohesivity offer?
```

## See also

- [Resource catalog](https://cohesivity.ai/offerings?ref=gh-neuro-san-studio)
- [Cohesivity documentation](https://cohesivity.ai/docs?ref=gh-neuro-san-studio)
- [MCP server configuration](../../neuro_san_studio/mcp/mcp_info.hocon)
