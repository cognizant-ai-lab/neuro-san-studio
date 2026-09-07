# Fraud Defense Autonomy Engine — Architecture Note

## Existing repository architecture

Neuro SAN Studio is a configuration-first wrapper around Neuro SAN:

- `neuro_san_studio.commands.cli` loads the project `.env`, resolves the project root, and dispatches `run`, `chat`, and `validate`.
- `ProjectEnvironment` exports `AGENT_MANIFEST_FILE`, `AGENT_TOOL_PATH`, `PYTHONPATH`, MCP, and toolbox paths so both the server and direct sessions resolve project-local assets.
- `NeuroSanRunner` starts the Neuro SAN HTTP server and nsflow client. `ChatCommand` uses `neuro_san.client.direct_agent_session_factory.DirectAgentSessionFactory` for in-process calls.
- `registries/manifest.hocon` and group manifests declare served agent-network HOCON files. A network is a HOCON object whose `tools` list contains a front-man node followed by downstream agents/functions.
- A node with `instructions` is an LLM agent; a node with a `class` is a coded tool. Coded tools implement `neuro_san.interfaces.coded_tool.CodedTool`, normally with `async_invoke(args, sly_data)`.
- HOCON `include` files provide shared LLM configuration. Per-node `tools` establish the directed agent topology. `sly_data` is the protected channel for request state and structured outputs that should not be placed in prompts.
- HOCON validation is delegated to Neuro SAN's `HoconValidatorCli`; existing tests use direct-session fixtures and `DynamicHoconUnitTests`.
- The repository already contains persistence, middleware, logging plugins, MCP support, and static Flask examples. The fraud application will use the existing registry/tool conventions and add a small local command-center server for a reliable no-key demo.

## Proposed architecture

The application is an isolated `coded_tools.fraud_defense` domain package plus an `apps.fraud_war_room` command center.

1. **Synthetic banking environment** — deterministic generator produces customers, accounts, devices, sessions, beneficiaries, merchants, transactions, alerts, cases, campaigns, investigator actions, policies, and controls. Every case has hidden ground truth and a scenario label. The flagship campaign is reproducible with a fixed seed.
2. **Deterministic workbench** — exact transaction signals, customer baselines, relationship traversal, connected components, centrality, timeline reconstruction, risk tiers, governance checks, simulation, and outcome learning live in Python tools. LLMs never calculate these values.
3. **Neuro SAN network** — `registries/industry/fraud_defense.hocon` is the visible orchestration backbone. Fraud Commander routes to specialized investigation, attacker, defender, simulator, challenger, governance, decision, and learning agents. The displayed topology uses an attacker → defender → simulator → challenger path plus a coded cycle gate and network step limit. The commander can re-enter a bounded round; the topology remains acyclic so NSFlow's graph renderer cannot recurse forever.
4. **Model router** — application reasoning requests are routed by risk tier to configured NVIDIA, Cerebras, Gemini, and optional Sarvam providers. Provider/model names are environment-configurable. Missing keys, timeouts, malformed outputs, and unavailable providers fall back to deterministic summaries; high-risk disagreement is never silently averaged.
5. **Decision Passport** — concise structured facts, evidence references, counter-evidence, hypotheses, model assessments, disagreement, defenses, simulation results, policy checks, approval, reason codes, and audit events are persisted as JSON. Chain-of-thought is not stored.
6. **Command center** — a local standard-library HTTP server serves a static enterprise dashboard and JSON endpoints for cases, graph/timeline data, agent activity, defenses, simulation comparisons, governance, approval, shadow lifecycle, and learning outcomes. It is an investigator interface rather than a chat-first UI. Optional Neuro SAN chat remains available through `ns chat`.
7. **Evaluation** — a reproducible benchmark compares deterministic baseline, agentic investigation, and full adversarial defense modes across 600 synthetic cases. Metrics are computed from hidden ground truth and written to a local artifact.

## Files to create

- `coded_tools/fraud_defense/` — domain models, generator, analytics/graph, risk, simulation, routing, orchestration, passport, learning, and Neuro SAN coded tools.
- `config/fraud_defense_llm_config.hocon` — Fraud War Room's Neuro SAN provider fallback configuration (Gemini first, NVIDIA second; credentials remain in the environment).
- `registries/industry/fraud_defense.hocon` — actual Neuro SAN HOCON agent network with specialized nodes and bounded adversarial cycle.
- `apps/fraud_war_room/` — local command-center server and static UI.
- `tests/fraud_defense/` — unit, HOCON structure, failure-mode, and end-to-end deterministic tests.
- `docs/demo-script.md`, `docs/evaluation.md`, `docs/model-routing.md`, `docs/security-and-license-notes.md` — operating and review documentation.

## Files to modify

- `registries/industry/manifest.hocon` — serve the Fraud War Room network.
- `registries/manifest.hocon` — add the flat `fraud_defense.hocon` alias used by NSFlow's local picker while retaining the grouped server network.
- `registries/industry/README.md` — not present; no framework README is replaced. The root README receives a link to the application README.
- `.env.example` — add fraud-specific placeholders without secrets.
- `requirements.txt` — keep the core dependency set lightweight; no graph/database dependency is required for the prototype.

## Dependency decisions

- Use Python standard library data structures for the synthetic environment, graph traversal, JSON persistence, HTTP demo server, and metrics. This keeps the demo runnable offline and avoids adding a heavyweight database/graph stack.
- Reuse `pyhocon`, `pytest`, and Neuro SAN already required by the repository.
- Do not add LangGraph, CrewAI, AutoGen, a second orchestration framework, or a paid data/API dependency.
- Provider calls use the existing Neuro SAN HOCON adapters for network agents and a small stdlib HTTP adapter for optional router probes; no provider SDK is required for the deterministic demo.
- External public datasets are documented as research inspiration only. The shipped dataset is generated locally, avoiding license, size, and offline reproducibility risk.

## Model routing strategy

- Low risk: deterministic analytics and local rule summary; optionally one configured fast provider.
- Medium risk: deterministic evidence first, then configured NVIDIA reasoning with fallback.
- High/critical: independent configured provider opinions (NVIDIA, Cerebras, Gemini when available), disagreement threshold, extra evidence, attacker/defender simulation, challenger, governance, and human approval.
- Neuro SAN uses verified package-supported Gemini/NVIDIA model aliases from `config/fraud_defense_llm_config.hocon`; credentials are read only from `GOOGLE_API_KEY` and `NVIDIA_API_KEY`. The independent application router keeps model IDs/endpoints environment-configurable for optional NVIDIA, Cerebras, Gemini, and Sarvam calls.

## Data strategy

All data is synthetic, seeded, and generated on demand. IDs are synthetic tokens; customer names, account numbers, locations, merchants, devices, sessions, and transactions do not represent Cognizant, bank, or client data. Hidden labels stay in the benchmark/workbench layer and are never sent to agents as evidence.

## Testing strategy

- Pure unit tests cover generation reproducibility, signals, graph paths/centrality, risk thresholds, simulations, defense ranking, routing/fallback, governance, passports, and learning.
- HOCON tests parse and validate network shape without requiring API keys. Live Neuro SAN integration tests are skipped when the optional `neuro_san` package or provider credentials are unavailable.
- Failure tests exercise unavailable providers, malformed responses, graph/simulation failures, missing evidence, and contradictory opinions.
- The E2E test runs alert → investigate → attack → defend → simulate → challenge → govern → approve → shadow → learn entirely against the deterministic synthetic environment.
