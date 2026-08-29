---
name: agent-network-middleware
description: Attach middleware (skills, persistent memory, checklist) to a neuro-san-studio agent, or configure a
  server plugin (observability, logging, authorization). Use when adding cross-session memory, agent skills,
  progress tracking, tracing, or auth to a network or deployment.
---

# Middleware and plugins

## Middleware (skills, memory, checklist)

**Middleware** injects code at agent hook points (`abefore_agent`/`aafter_agent`, `abefore_model`/`aafter_model`,
`awrap_model_call`, `awrap_tool_call` — async preferred). Attach per agent via `middleware` (order matters);
class-based `AgentMiddleware` only.
Docs: [user_guide.md → Middleware](../../../docs/user_guide.md#middleware).

Three commonly used middlewares ship with the repo:

- **Skills** (`agent_skills_middleware.AgentSkillsMiddleware`, args `skill_sources`/`keep_skill_in_context`) — a
  skill is a folder with a `SKILL.md`; metadata loads first, content pulls in on demand (progressive disclosure).
  Example: [job_guessing_skill.hocon](../../../registries/basic/job_guessing_skill.hocon).
  Docs: [user_guide.md → Agent Skills](../../../docs/user_guide.md#agent-skills).
  **Security:** review any internet-sourced skill — it can reference untrusted tools/resources.
- **Persistent memory** (`persistent_memory.persistent_memory_middleware.PersistentMemoryMiddleware`) — memory
  across sessions (create/read/append/delete/search/list). Attach to **your own** agent, don't import the
  reference network. Backends: `json_file`/`markdown_file` (local, per `(network, agent)`, **not** per user) or
  `mem0` (cloud, per end user — for shared/production). Refs: `registries/tools/persistent_memory_local.hocon`,
  `persistent_memory_mem0.hocon`.
  Docs: [local](../../../docs/examples/tools/persistent_memory_local.md), [mem0](../../../docs/examples/tools/persistent_memory_mem0.md).
- **Checklist** (`agent_checklist_middleware.AgentChecklistMiddleware`, args `checklist_title`/
  `keep_checklist_in_context`/`progress_reporter`) — `pending`/`in_progress`/`done`/`skipped` tracking for
  multi-step tasks.
  Example: [coding_assistant.md](../../../docs/examples/basic/coding_assistant.md).

## Plugins (observability, logging, authorization)

**Plugins** extend the server for deployment use-cases, never required to run.
Docs (with links to each tool's own docs): [plugins.md](../../../docs/plugins.md).

- **Observability** — Langfuse and Arize Phoenix are `BasePlugin` (`neuro_san_studio/interfaces/base_plugin.py`)
  subclasses registered in `config/plugins.hocon`, toggled by env var (`LANGFUSE_ENABLED`, `PHOENIX_ENABLED`; off by
  default). LangSmith needs **no plugin at all** — LangChain's own tracing works out of the box, just set
  `LANGSMITH_TRACING=true` / `LANGSMITH_API_KEY`.
- **Logging** — Log Bridge is a `BasePlugin` in `config/plugins.hocon`, on by default (`LOGBRIDGE_ENABLED` to
  disable); gives Rich structured console logs.
- **Authorization** — Open FGA (ReBAC) is a separate integration (its own server + `authorize.py`), **not** a
  `BasePlugin` and **not** registered in `config/plugins.hocon` — set it up per its own README.
