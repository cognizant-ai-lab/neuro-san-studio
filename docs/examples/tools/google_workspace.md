# Google Workspace Assistant

The **Google Workspace Assistant** is a single-agent network that manages a user's Gmail, Calendar, Drive, Docs, and
Sheets through Google's hosted Workspace MCP servers. Because one agent carries all five services, a single request can
span them — for example, finding a report in Drive and emailing a link to it, or turning meeting notes from a Doc into
Calendar events.

Authentication is per user and per conversation: an OAuth-capable client (such as `nsflow`) connects each MCP server
with the user's Google account and passes the resulting bearer tokens through `sly_data` on every message. The server
needs no Google credentials, API keys, or extra packages.

---

## File

[google_workspace.hocon](../../../registries/tools/google_workspace.hocon)

---

## Prerequisites

- A Google account with access to Gmail, Calendar, Drive, Docs, and Sheets.
- An OAuth-capable client. With `nsflow`, open the MCP settings page and connect each of the five servers with your
  Google account. Chat with this network is gated until every server listed under
  `sly_data_schema.http_headers.required` is connected; until then nsflow redirects you to complete the OAuth flow.
- No server-side setup: no `credentials.json`, no environment variables, no additional `pip install`.

---

## Architecture Overview

### Frontman Agent: **google_workspace_assistant**

- The network's single agent: it talks to the client and owns all five MCP servers as tools.
- Combines services when a request spans them, and asks for confirmation before sending email or modifying content.

### Tools: Google's hosted Workspace MCP servers

| Service  | MCP server URL |
|----------|----------------|
| Gmail    | `https://gmailmcp.googleapis.com/mcp/v1` |
| Calendar | `https://calendarmcp.googleapis.com/mcp/v1` |
| Drive    | `https://drivemcp.googleapis.com/mcp/v1` |
| Docs     | `https://docsmcp.googleapis.com/mcp/v1` |
| Sheets   | `https://sheetsmcp.googleapis.com/mcp/v1` |

Each URL appears three times in the HOCON, and the three lists must stay in sync: in the agent's `tools` (making the
server's tools callable), under `sly_data_schema.http_headers.properties` (declaring the auth input a client must
supply), and in `sly_data_schema.http_headers.required` (gating chat until the server is connected).

---

## Authentication

The front man's `sly_data_schema` declares, for each server URL, an `Authorization` header of the form
`Bearer <token_value>`. Generic clients read this schema to learn what private inputs to pass outside the chat stream
as `sly_data["http_headers"][<server_url>]["Authorization"]`; nsflow does this automatically for connected servers,
refreshing tokens as needed — Google access tokens are short-lived, which is why the client OAuth flow is the
practical path rather than static headers in `MCP_SERVERS_INFO_FILE` (see
[user guide: authentication](../../user_guide.md#authentication)).

To use only a subset of the services, remove the unused URLs from all three lists in the HOCON. To stop nsflow from
forcing a connect (keeping opportunistic token injection for whatever is passed), set `http_headers.required` to `[]`.

---

## Debugging Hints

- **Chat is blocked / keeps redirecting to home**: some URL in `http_headers.required` is not connected in nsflow yet.
  Connect it, or trim the `required` list if you only use some of the services.
- **A service's tools are missing from the agent's repertoire**: that server's token was absent, expired, or revoked —
  its listing is dropped for the turn rather than failing the others. Reconnect the server in nsflow.
- **401/403 errors on tool calls**: the Google account that connected the server lacks access to the content being
  requested, or the OAuth grant was revoked in the Google account's security settings.
