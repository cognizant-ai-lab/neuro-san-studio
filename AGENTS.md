# AGENTS.md

Contribution guide for coding agents working in **neuro-san-studio**.

---

## 1. Rules

- **Every network you add or edit sets `max_steps` and `max_execution_seconds`.** Never unbounded. Older curated
  networks that lack them are not precedent.
- **No secrets in HOCON** — use environment or `.env`. Never log or print `sly_data`.
- **Keep the diff focused.** No unrequested refactors, no drive-by reformatting of untouched files.
- **Check the toolbox before writing Python.**
  [toolbox_info.hocon](neuro_san_studio/toolbox/toolbox_info.hocon) already has web search, RAG, code execution,
  Gmail, Jira and more.
- **Prefer `async_invoke`** in a `CodedTool`; `invoke()` blocks the event loop. Wrap blocking I/O in
  `asyncio.to_thread(...)`.
- **Use `logging`, never `print`.** Long-form flags (`--force`, not `-f`). Docstrings on functions, classes and modules.
- **Tests mirror the tree they cover**, named `test_<functionality>_<scenario>`, arrange-act-assert, with
  external calls and file I/O mocked.
- **A user-facing change ships its docs in the same PR.** A curated example (`basic/`, `industry/`, `tools/`)
  needs `metadata` in the HOCON, a doc under `docs/examples/<group>/` named after it, a line plus TOC entry in
  [examples.md](docs/examples.md), and a registered fixture. A feature rather than a network updates its own
  reference doc — [toolbox.md](docs/toolbox.md), [plugins.md](docs/plugins.md), [search_tools.md](docs/search_tools.md),
  or [user_guide.md → Middleware](docs/user_guide.md#middleware). A network in `generated/` needs none; it is
  git-ignored and personal.

## 2. Things that bite

- In a manifest, `serve` loads the network, `public` lists it in `/list`, `mcp` exposes it as an MCP tool. Paths
  resolve relative to `registries/`.
- A subfolder prefixes the runtime name: `"generated/my_network.hocon"` is addressed as `generated/my_network`.
  Use the prefixed name in `ns chat` and in test fixtures.
- Short-form `class` resolves via `AGENT_TOOL_PATH` (default `coded_tools/`) plus the network's path, so
  `basic/my_network.hocon` with `"class": "order_lookup.OrderLookup"` finds
  `coded_tools/basic/my_network/order_lookup.py`. Fully-qualify anything under `neuro_san_studio/coded_tools/`.
- The Front Man must be an LLM agent, never a coded or toolbox tool.
- Network-level `tools` (agent *definitions*) is not an agent's `tools` (down-chain agents it may *call*).
- `sly_data` does not reach external or other-network agents without an explicit `allow` policy; its schemas are
  Front-Man-only.
- Review any internet-sourced agent skill before wiring it in — a `SKILL.md` can reference untrusted tools.

## 3. Opening the PR

Branch as `feature/short-name`, `fix/short-name` or `docs/short-name` — never commit to `main`. Commits are a
one-line summary, prefixed with the issue number when there is one:

```text
#123: Add retry handling to the order lookup coded tool
```

All four gates must pass first. CI runs the same checks (`.github/workflows/tests.yml`, `integration.yml`).

```bash
ns validate registries/<group>/<name>.hocon   # HOCON structure; no LLM calls, no keys needed
make lint                                     # ruff format + ruff check + pylint + pymarkdown over docs/
make test                                     # runs make lint, then pytest with coverage (no integration)
make test-integration                         # sets AGENT_TOOL_PATH / AGENT_MANIFEST_FILE / PYTHONPATH for you
```

Notes that save a round trip:

- **Line length is 119** for Python (ruff and pylint enforce it), **120** for Markdown.
- **`make lint` only scans `./docs` and `./README.md` for Markdown.** A `.md` anywhere else — this file included
  — needs `pymarkdown --config ./.pymarkdownlint.yaml scan <path>` run by hand.
- `ns validate` reports external-agent refs (`/industry/macys`) as errors unless you pass
  `--external-agents "/industry/macys,…"`. Validator limitation, not a broken network.
- Narrow integration runs with markers: `pytest -s -m "integration_basic"`.

Then, before you push:

- [ ] **One concern per PR.** Split anything that needs the word "and" to describe.
- [ ] **Read your own diff** (`git diff main...HEAD`). Remove debug prints, commented-out code, stray `TODO`s, files you
      touched by accident.
- [ ] **Nothing unrelated committed** — no `.env`, no `logs/`, no editor or OS files, and nothing pasted from a
      terminal that carries a key or an internal URL.
- [ ] **New behavior has a test** — unit test for a coded tool, integration fixture for a network.
- [ ] **Links in any doc you touched still resolve.**
- [ ] **Backward compatible**, or the break is called out in the description with the migration path.
- [ ] **Rebased on current `main`**, conflicts resolved locally rather than merged from the GitHub UI.

Say what changed, why, and how you tested it — for a network, paste a real `ns chat` exchange.
