# AGENTS.md

Rules for coding agents in Neuro-san-studio.
Neuro SAN Studio is a multi-agent orchestration framework built on the
[neuro-san](https://github.com/cognizant-ai-lab/neuro-san) library.
Agent networks are defined declaratively in HOCON files under `registries/`.
Custom Python tools live in `coded_tools/`.

## 1. Contribution rules

- Check the toolbox before writing Python. [toolbox_info.hocon](neuro_san_studio/toolbox/toolbox_info.hocon)
  already provides web search, RAG, code execution, Gmail, Jira and more.
- Every network sets `max_steps` and `max_execution_seconds`; never leave them unbounded. Older networks that
  lack them are not precedent.
- No secrets in HOCON: use the environment or `.env`. Never log or print `sly_data`.
- Add optional dependencies in `coded_tools/<group>/<agent_network>/requirements.txt`, and keep the network disabled
  by default in the manifest.
- Review any internet-sourced agent skill before use; a `SKILL.md` can reference untrusted tools.
- Keep the diff focused: no unrequested refactors and no reformatting of untouched files. Review it before creating a
  PR and remove debug prints, commented-out code, stray `TODO`s and files touched by accident.
- Documentation ships in the same PR. A curated example (`basic/`, `industry/`, `tools/`) requires `metadata`,
  documentation as `docs/examples/<group>/<agent_network>.md`, a line and a TOC entry in
  [examples.md](docs/examples.md), and a registered fixture. A feature updates its own reference document
  instead: [toolbox.md](docs/toolbox.md), [plugins.md](docs/plugins.md),
  [search_tools.md](docs/search_tools.md), or [user_guide.md → Middleware](docs/user_guide.md#middleware).
  A network in `generated/` is git-ignored and personal.
  Verify every link in the documents you touch to check for broken links.
- Use US spelling for English words.

## 2. Coding style

- Clean Code Standards: follow Robert C. Martin’s (Uncle Bob) *Clean Code* and *The Clean Coder* recommendations
- Keep things simple, to the point, readable and maintainable.
- Line length: 119 characters, both for .py and .md files.

### 2.1 Python

- Use Python 3.12+ syntax.
- Use type hints on all parameters and return values, and annotate variable assignments when the type
  isn't obvious from the right-hand side.
- Imports: ES-style single-line imports, sorted by isort (`force-single-line = true`).
- Use `snake_case` for functions, methods, variables, parameters and attributes, `PascalCase` for classes, and
  `UPPER_CASE` for constants. Comment the reason if an external API forces `camelCase`.
- Linting: ruff (format + isort + pycodestyle + pyflakes) then pylint. Config in `pyproject.toml`.
- Everything lives in a class. No standalone helpers, including in tests. `main()` is a static method, and no
  nested `def`s without a comment stating why. Data-only classes carry no policy methods. One class per file,
  named after it.
- Use `async_invoke` in a `CodedTool`, since `invoke()` blocks the event loop, and wrap blocking I/O in
  `asyncio.to_thread()`.
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
- Docstrings required on functions, classes and modules.
- Use long-form flags (`--force`, not `-f`)
- Cover new behavior with a test: a unit test for a coded tool, an integration fixture for a network.

### 2.2 Markdown

- Markdown: linted with pymarkdown (config `.pymarkdownlint.yaml`). Scan covers `docs/` and `README.md`.

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

## 4. Build & test commands

- Main commands are in the Makefile. Run them from the repo root, with the venv activated:
```bash
make lint             # Format (ruff) then lint (ruff + pylint + pymarkdown)
make test             # Lint + run pytest (unit tests only, excludes integration)
python -m pytest tests/path/to/test_file.py -v  # Run a single test file
python -m pytest -s -m "integration_basic"      # Run integration tests for a specific marker
make test-integration # Run integration tests (needs API keys + server env vars)
python -m neuro_san_studio validate registries/path/to/agent_network.hocon  # Validate an agent network's HOCON file
python -m neuro_san_studio run  # Start the full app (server + UI)
```

Notes:
- `make lint` scans only `./docs` and `./README.md` for Markdown. Any other `.md`, this file included, needs
  `pymarkdown --config ./.pymarkdownlint.yaml scan <path>` run by hand.

## 5. Opening a PR

Details in [CONTRIBUTING.md](CONTRIBUTING.md).

- Branch as `feature/short-name`, `fix/short-name` or `docs/short-name`, and never commit to `main`.
- A commit is a one-line summary, prefixed with the issue number like
  '#123: Add retry handling to order lookup coded tool'.
