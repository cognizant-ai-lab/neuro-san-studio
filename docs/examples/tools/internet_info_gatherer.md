# Internet Info Gatherer

The **Internet Info Gatherer** is a single-agent network that gathers information from the internet in two steps:
it searches the web through the you.com MCP server's free tier to find sources, then reads the pages it finds with
the `web_fetch` toolbox tool to ground its answers in actual page content, with cited URLs.

The two tools deliberately complement each other: the free you.com tier exposes only the `you-search` tool — search
result titles, URLs, and snippets, with no page content (the `you-contents` and `you-research` tools require the
authenticated tier; see the [you_search](../../search_tools.md) network for that). `web_fetch` fills the gap by
fetching the promising result URLs and returning their plain-text body, so the agent answers from what pages
actually say instead of from snippets.

---

## File

[internet_info_gatherer.hocon](../../../registries/tools/internet_info_gatherer.hocon)

---

## Prerequisites

None — this network runs out of the box:

- The you.com MCP server's free tier (`?profile=free`) needs no API key and no OAuth.
- `web_fetch`'s packages (`aiohttp`, `beautifulsoup4`, `pypdf`) ship in `requirements.txt`.
- `python -m neuro_san_studio run` automatically points `AGENT_TOOLBOX_INFO_FILE` at this repo's
  [toolbox_info.hocon](../../../neuro_san_studio/toolbox/toolbox_info.hocon), where `web_fetch` is defined. If you
  override that variable with your own toolbox file, keep a `web_fetch` entry in it.

---

## Architecture Overview

### Frontman Agent: **info_gatherer**

- The network's single LLM agent. Its instructions enforce the search-then-read loop: find sources, fetch the
  relevant ones, answer from page content, cite URLs.

### Tool: you.com MCP server (free tier)

- `https://api.you.com/mcp?profile=free`, connected as a remote MCP tool over streamable HTTP.
- Free tier exposes `you-search` only: web search results with titles, URLs, and snippets.

### Tool: `web_fetch` (toolbox)

- A shared toolbox coded tool (`neuro_san_studio.coded_tools.web_fetch.WebFetch`) that fetches one URL and returns
  its plain-text body plus metadata. Handles HTML pages and PDF documents.
- Content is truncated to `max_content_chars` (default 20000); optional `allowed_domains` / `blocked_domains`
  parameters restrict where it may go.
- Includes SSRF protections: private, loopback, and link-local destinations are refused.

---

## Debugging Hints

- **Search works but answers stay shallow**: the model answered from snippets. The instructions tell it to fetch
  before answering — if it still skips fetching, ask it explicitly to read the pages.
- **Search results are empty or rate-limited**: the free you.com tier has usage limits. The paid tier via the
  `you_search` network removes them.
- **web_fetch refuses a URL**: the target resolved to a private, loopback, or link-local address (SSRF protection),
  the URL exceeded 250 characters, or a domain filter excluded it.
- **A fetched page comes back nearly empty**: some sites render content with JavaScript or block non-browser
  clients; try another source from the search results.
