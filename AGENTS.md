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

## 2. Python style reviewers will flag

- **Everything lives in a class.** No standalone helper functions — not in tests either. `main()` is a static method
  on a class. No nested `def`s unless a comment explains why. Data-only classes stay data-only: no policy methods on
  them. One class per file, file name matching the class name.
- **`snake_case` for every identifier** (`fail_fast`, not `failfast`). If an external API forces `camelCase`,
  comment why.
- **Double quotes** for strings (`ruff format` enforces it). Imports one per line (`force-single-line`), only what is
  used, no star imports.
- **Dictionary access is always `.get()`**, never `dict[key]`.
- **Catch specific exceptions**, never bare `except Exception`. Only catch what you can handle at that level.
- **Logging**: lazy `%` formatting (`logger.info("Loaded %s", name)`), not f-strings. `WARNING` is reserved for
  something an operator can act on — otherwise `INFO` or `DEBUG`. Write messages devops can understand.
- **Use accessors, not internals.** Don't reach into another class's attributes; don't `isinstance` against concrete
  classes — check the interface, or add an interface method that answers the question.
- **Don't modify system env vars** and don't hardcode values that belong in one (`localhost`, ports, paths).
- **Every `.py` starts with the Apache copyright header** ending in `# END COPYRIGHT`; put module comments and
  docstrings *below* that block so the auto-updater does not clobber them.
- **Comment the non-obvious**: which `_method`s are overrides vs. ours, threading and lifecycle behavior, design
  decisions, and a breadcrumb pointing to related code or docs. Order lifecycle methods logically (`start()` before
  `stop()`).
- **Don't rename or remove public classes, interfaces, log lines or comments** without a compatibility layer or a
  reason in the PR.
- **Tests**: prefer real fixture files over heavy mocking; keep timeouts realistic; don't make required parameters
  optional just for test convenience.
- **Dependencies** float within a major/minor range — don't pin micro versions.

## 3. Things that bite

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

## 4. Opening the PR

The essentials are below; for more details go through [CONTRIBUTING.md](CONTRIBUTING.md).

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
