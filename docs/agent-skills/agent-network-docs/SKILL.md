---
name: agent-network-docs
description: Decide what documentation to write (if any) for a neuro-san-studio network, feature, or reorg. Use
  when asked to document a network, contribute an example, or write up a new feature.
---

# Documentation conventions

**Documentation is opt-in — ask first, don't write by default.** When asked:

- Network in `generated/`: it's git-ignored and personal — no committed doc is needed unless the user wants to
  contribute it permanently. To do that, move it into a curated folder first (`basic/`, `industry/`, `tools/`; see
  AGENTS.md's reorg checklist), then follow the curated-example bullet next.
- Curated example (`basic/`, `industry/`, `tools/`): heavier. `dev_guide.md` has no dedicated checklist for a *new*
  example (its [`#checklist`](../../../docs/dev_guide.md#checklist) section is for *reorganizing* an existing one) —
  instead do all of: add `metadata` (`description`/`tags`/`sample_queries`), write a short per-network doc under
  `docs/examples/<group>/`, add a line + TOC entry to [examples.md](../../../docs/examples.md), and register a test fixture
  (see the `antegen-testing` skill).
- A feature, not a network (toolbox tool, plugin, middleware): update the matching reference doc
  ([toolbox.md](../../../docs/toolbox.md),
  [plugins.md](../../../docs/plugins.md),
  [search_tools.md](../../../docs/search_tools.md),
  [user_guide.md → Middleware](../../../docs/user_guide.md#middleware)).