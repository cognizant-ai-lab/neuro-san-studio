# Neuro-Donn

**Neuro-Donn** is a front man for starting work in Devin. Describe a task in plain language and it finds the matching
Devin playbook when there is one, or recognizes that the request is an ad-hoc task with no playbook. It restates the
request, asks for confirmation, launches a Devin session after you confirm, and hands back the session URL. It can
also report back on a launched session, so the answer arrives in this chat instead of only in the Devin session. Every
session it launches is tagged `neuro-donn`.

## What You Can Do

### Start a playbook-matched task

Use Neuro-Donn for recurring or procedural work, such as a report, an account or environment change, a release check,
or a routine repository chore. For example:

```text
Create a unileaf user in Auth0 for jane@example.com
```

Neuro-Donn searches the available Devin playbooks, reads the most plausible matches, and tells you the selected
playbook's title, ID, and purpose. It asks you to confirm the request and playbook before launching Devin.

### Send an ad-hoc task directly to Devin

One-off work does not need a playbook. Code changes, bug fixes, investigations, and questions about a repository can
go straight to Devin:

```text
Fix the failing configuration test in my current repository
```

Neuro-Donn identifies this as a direct Devin task, skips playbook lookup, asks you to confirm the request, and then
launches a plain Devin session. If it is unsure whether a request is recurring or one-off, it can look for a playbook
before asking for confirmation.

### Get the answer back in this chat

After a launch, ask for the result and Neuro-Donn reports it here:

```text
What is the result of the session you just launched?
```

For short tasks it waits for the session to settle, up to a few minutes, and then gives you the session's answer
along with any pull request links. For longer work it reports the current status and the session's most recent
message, and you can ask again later. Devin sessions frequently outlive a single chat turn, so treat the waiting
behavior as a convenience for quick tasks rather than a guarantee.

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

- **Front man: `neuro_donn`** — classifies the request, coordinates playbook selection when useful, requires
  confirmation, and launches the work.
- **Playbook finder: `playbook_finder`** — calls Devin's `devin_playbook_manage` MCP tool to list available
  playbooks, inspect plausible candidates, and return the best match.
- **Task launcher: `task_launcher`** — calls Devin's `devin_session_create` MCP tool with the confirmed request,
  optional playbook ID, and the `neuro-donn` tag.
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
- **No playbook matches:** Neuro-Donn should say that no playbook matches and offer a direct Devin task. Confirm the
  request to launch a plain session.
- **Nothing launches after describing a task:** Confirmation is intentional. No Devin session is created until you
  restate the request and answer the confirmation question affirmatively.
- **Result never arrives in chat:** Long sessions do not finish within a chat turn. Ask again later, or open the
  session URL. `devin_session_gather` waits at most 590 seconds per call.
