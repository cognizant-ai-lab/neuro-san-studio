---
name: agent-network-apps
description: Wrap a neuro-san-studio network in a standalone app (Flask UI, Slack app, CRUSE dynamic UI). Use
  when asked to build an app on top of a network, integrate it into another program, or enable CRUSE.
---

# Building an app on a network

Wrap a network in your own app via the neuro-san **session client** — `DirectAgentSession` runs it in-process (no
server; async variants exist).
Docs: [clients.md](https://github.com/cognizant-ai-lab/neuro-san/blob/main/docs/clients.md),
[integration quick start](../../../docs/integration_quickstart.md).
Examples in `apps/`: `slack/` (Slack app), `conscious_assistant/` + `cruse/` (Flask UIs), and `wwaw/` — each with its
own `requirements.txt`. `log_analyzer/` is also there but has no separate `requirements.txt` of its own.

**CRUSE** (Context-React User Experience) is a built-in dynamic UI that adapts to the network (AI-generated themes,
form widgets, threads). Enable by importing the experimental `cruse_theme_agent` / `cruse_widget_agent`
(`ns import`), then open the Cruse page.
Docs: [cruse_interface.md](../../../docs/cruse_interface.md).
