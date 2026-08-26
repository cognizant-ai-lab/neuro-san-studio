# Neuro-Donn

**Neuro-Donn** is a front man for starting work in Devin. Describe a task in plain language and it first looks for the
matching Devin playbook. Only a plainly one-off code change in a named repository goes directly to Devin without a
playbook lookup. It chooses the playbook and launches the work immediately, states any assumptions it made, and reports
the answer in chat. Every task it launches is tagged `neuro-donn`.

## What You Can Do

### Start a playbook-matched task

Use Neuro-Donn for recurring or procedural work, such as a report, an account or environment change, a release check,
or a routine repository chore. For example:

```text
Create a unileaf user in Auth0 for jane@example.com
```

Neuro-Donn searches the available Devin playbooks, reads the most plausible matches, and launches the most plausible
match immediately. The matched playbook may cover more ground than the request spelled out; Neuro-Donn tells you the
selected playbook's title, ID, and purpose, along with any assumptions it made.

### Send a plainly one-off code change directly to Devin

Only a plainly one-off code change in a named repository skips playbook lookup. For example:

```text
Fix the failing configuration test in my current repository
```

Neuro-Donn identifies this as a direct Devin task and launches a plain Devin session immediately. Investigations,
questions about a repository, and other requests that are not plainly one-off code changes go through playbook lookup
first. If it is unsure whether a request is recurring or one-off, it makes a reasonable assumption, states it, and
proceeds; you can correct it afterwards if it got the request or routing wrong.

### Get the answer back in this chat

After a launch Neuro-Donn tells you what it is running, then waits and reports the answer here, so you do not have to
ask. You can ask again at any time:

```text
How is that going, and what did it find?
```

For short tasks it waits up to a few minutes and then gives you the answer along with any pull request links. For
longer work it reports the current status and most recent message, and you can ask again later. Devin work frequently
outlives a single chat turn, so treat the waiting behavior as a convenience for quick tasks rather than a guarantee.

### Expect Donn's voice, not Donn

Neuro-Donn answers in the terse, decision-first style Donn uses in his pull requests and reviews: short replies, a
pointed question when something does not add up, and a plain statement when it is unsure or when something belongs in
follow-up work. It is a stand-in and says so; it never claims to be Donn.

## File

[neuro_donn.hocon](../../../registries/tools/neuro_donn.hocon)

## Prerequisites

This network ships disabled because it requires Devin credentials. Before using it, supply the credentials described
below and flip `"tools/neuro_donn.hocon"` to `true` in
[registries/tools/manifest.hocon](../../../registries/tools/manifest.hocon).

Devin authentication is required. Configure access to the Devin MCP server at
`https://mcp.devin.ai/mcp` using one of these two paths:

- A client can provide `sly_data.http_headers` for the MCP URL.
- The server can use a HOCON file named by the `MCP_SERVERS_INFO_FILE` environment variable.

Both paths must provide these headers:

- `Authorization: Bearer <Devin PAT>`
- `X-Org-Id: <org id>`

For example, an `MCP_SERVERS_INFO_FILE` can contain:

```hocon
{
    "https://mcp.devin.ai/mcp": {
        "http_headers": {
            "Authorization": "Bearer <Devin PAT>",
            "X-Org-Id": "<org id>",
        },
    },
}
```

The server URL in this file must match the URL in the agent network configuration. Never put a real PAT in source
control or documentation.

When a client supplies headers through `sly_data`, the equivalent shape is:

```json
{
    "http_headers": {
        "https://mcp.devin.ai/mcp": {
            "Authorization": "Bearer <Devin PAT>",
            "X-Org-Id": "<org id>"
        }
    }
}
```

Sessions are attributed to the owner of the PAT configured on the server, not to the user who requested the work.

## Architecture Overview

Neuro-Donn has four agents:

- **Front man: `neuro_donn`** — checks for a playbook by default, uses direct Devin only for plainly one-off code
  changes in a named repository, launches the work without confirmation, and states any assumptions it made.
- **Playbook finder: `playbook_finder`** — calls Devin's `devin_playbook_manage` MCP tool to list available
  playbooks, inspect plausible candidates, and return the best match.
- **Task launcher: `task_launcher`** — calls Devin's `devin_session_create` MCP tool with the request, optional
  playbook ID, and the `neuro-donn` tag.
- **Result fetcher: `result_fetcher`** — calls Devin's `devin_session_gather` MCP tool to wait for a session to settle
  and `devin_session_interact` to read its status and messages, then returns the session's latest answer.

Devin's MCP server exposes many tools, so each downstream agent receives a filtered MCP tool list. The playbook finder
can only call `devin_playbook_manage`; it structurally cannot create sessions. The task launcher can only call
`devin_session_create`. The result fetcher is read-only by instruction and never messages or terminates a session.
Keeping these responsibilities separate makes routing more reliable and limits accidental tool use.

## Debugging Hints

- **Authentication errors or missing tools:** Check that the Devin PAT is valid, both required headers are present,
  and the MCP URL in `MCP_SERVERS_INFO_FILE` exactly matches `https://mcp.devin.ai/mcp`. If both the client and server
  provide headers, client `sly_data` takes precedence.
- **No playbook matches:** Neuro-Donn should say that no playbook matches, launch a plain Devin task immediately, and
  state any assumptions it made. Correct the request afterwards if its interpretation was wrong.
- **An unwanted task launched:** Neuro-Donn launches without asking for confirmation. If it misunderstood a request or
  chose the wrong playbook, correct the assumption in chat and stop the unwanted work in the Devin UI.
- **Result never arrives in chat:** Long-running work may not finish within a chat turn. Ask again in chat; the work
  remains visible in the Devin UI to whoever owns the configured PAT. `devin_session_gather` waits at most 590 seconds
  per call.
