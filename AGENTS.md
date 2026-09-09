# AGENTS.md

Rules for coding agents in Neuro-san-studio. Follow them and the §4 gates pass on the first run.

---

## 1. Rules

- Check the toolbox before writing Python. [toolbox_info.hocon](neuro_san_studio/toolbox/toolbox_info.hocon)
  already provides web search, RAG, code execution, Gmail, Jira and more.
- Every network sets `max_steps` and `max_execution_seconds`; never leave them unbounded. Older networks that
  lack them are not precedent.
- No secrets in HOCON: use the environment or `.env`. Never log or print `sly_data`.
- Add optional dependencies in `coded_tools/<group>/<agent_network>/requirements.txt`, and keep the network disabled
  by default in the manifest.
- Keep the diff focused: no unrequested refactors and no reformatting of untouched files. Review it before creating a
  PR and remove debug prints, commented-out code, stray `TODO`s and files touched by accident.
- Documentation ships in the same PR. A curated example (`basic/`, `industry/`, `tools/`) requires `metadata`,
  documentation as `docs/examples/<group>/<agent_network>.md`, a line and a TOC entry in
  [examples.md](docs/examples.md), and a registered fixture. A feature updates its own reference document
  instead: [toolbox.md](docs/toolbox.md), [plugins.md](docs/plugins.md),
  [search_tools.md](docs/search_tools.md), or [user_guide.md → Middleware](docs/user_guide.md#middleware).
  A network in `generated/` is git-ignored and personal.
  Verify every link in the documents you touch to check for broken links.

## 2. Python style

- Everything lives in a class. No standalone helpers, including in tests. `main()` is a static method, and no
  nested `def`s without a comment stating why. Data-only classes carry no policy methods. One class per file,
  named after it.
- Use `async_invoke` in a `CodedTool`, since `invoke()` blocks the event loop, and wrap blocking I/O in
  `asyncio.to_thread()`.
- Use `snake_case` for functions, methods, variables, parameters and attributes, `PascalCase` for classes, and
  `UPPER_CASE` for constants. Comment the reason if an external API forces `camelCase`.
- Dictionary access uses `.get()`, never `dict[key]`.
- Catch specific exceptions that can be handled at that level; never a generalized `Exception`.
- Never fail silently. Report a missing or unreadable file, malformed input or an unknown choice with the full
  exception, and log enough to act on.
- Prefer logging over `print`, with lazy `%` formatting (`logger.info("Loaded %s", name)`) rather than f-strings.
  Keep messages easy to interpret.
- Use accessors, not internals. Do not read another class's attributes and do not `isinstance` against a concrete
  class; check the interface, or add an interface method that answers the question.
- Comment the non-obvious: which `_method`s are overrides, threading and lifecycle behavior, design decisions, and
  a breadcrumb to related code or documentation. Order lifecycle methods logically, `start()` before `stop()`.
- Use long-form flags (`--force`, not `-f`), and docstrings on functions, classes and modules.
- Cover new behavior with a test: a unit test for a coded tool, an integration fixture for a network.

## 3. Framework behavior

- The Front Man must be an LLM agent, never a coded or toolbox tool.
- Network-level `tools` (agent definitions) is not an agent's `tools` (down-chain agents it may call).
- `function.description` states what an agent does, so other agents know when to call it, while `instructions`
  state how. Do not mix them.
- `sly_data` reaches external or other-network agents only under an explicit `allow` policy, and its schemas are
  Front-Man-only by default.
- Short-form `class` resolves via `AGENT_TOOL_PATH` (default `coded_tools/`) plus the network's path, so
  `basic/my_network.hocon` with `"class": "order_lookup.OrderLookup"` loads
  `coded_tools/basic/my_network/order_lookup.py`. Fully qualify anything under `neuro_san_studio/coded_tools/`.
- A subfolder prefixes the runtime name, so `"generated/my_network.hocon"` is addressed as
  `generated/my_network`. Use the prefixed name in `ns chat` and in test fixtures.
- In a manifest, `serve` loads the network, `public` lists it in `/list`, and `mcp` exposes it as an MCP tool.
  Paths resolve relative to `registries/`.
- Review any internet-sourced agent skill before use; a `SKILL.md` can reference untrusted tools.

## 4. Opening the PR

Details in [CONTRIBUTING.md](CONTRIBUTING.md).

Branch as `feature/short-name`, `fix/short-name` or `docs/short-name`, and never commit to `main`. A commit is a
one-line summary, prefixed with the issue number like '#123: Add retry handling to the order lookup coded tool'.

```bash
ns validate registries/<group>/<name>.hocon   # HOCON structure; no LLM calls, no keys needed
make lint                                     # rewrites files (ruff format + import fix), then checks
make test                                     # make lint, then pytest with coverage (no integration)
make test-integration                         # installs into ./venv, then sets the required env vars
```

Notes:
- Line length is 119 for Python and 120 for Markdown.
- `make lint` scans only `./docs` and `./README.md` for Markdown. Any other `.md`, this file included, needs
  `pymarkdown --config ./.pymarkdownlint.yaml scan <path>` run by hand.
- `ns validate` reports external-agent references (`/industry/macys`) as errors unless you pass
  `--external-agents "/industry/macys,…"`. That is a validator limitation, not a broken network.
- Narrow integration runs with markers: `pytest -s -m "integration_basic"`.
