---
name: antegen-testing
description: Generate and register HOCON test fixtures for a neuro-san-studio network using ANTeGen. Use when
  asked to add tests, generate test cases, or check a network's behavior.
---

# ANTeGen test fixtures

```bash
make test    # runs make lint, then pytest with coverage (excludes integration tests)
```

Fixtures are HOCON under `tests/fixtures/<group>/<network>/*.hocon`, run by
`tests/integration/test_integration_test_hocons.py`. A fixture names the `agent` and lists `interactions` (input
`text` → expected `response`, e.g. `keywords` or a `structure`).
Spec: [test_case_hocon_reference.md](https://github.com/cognizant-ai-lab/neuro-san/blob/main/docs/test_case_hocon_reference.md).

Run via `make test-integration`, which sets the required env vars (`AGENT_TOOL_PATH=coded_tools/`,
`AGENT_MANIFEST_FILE=registries/manifest.hocon`, `PYTHONPATH=$(pwd)`) for you — export those same values first if
you call pytest directly (`pytest -s -m "integration_basic"` narrows to one group). To narrow further (by
network, or to a single test case), see
[user_guide.md → Integration Test](../../../docs/user_guide.md#integration-test).

Generate with **ANTeGen**: `ns chat agent_network_test_generator`, ask e.g. *"Generate test cases for
basic/music_nerd_pro"*. Two follow-ups are on you: **review** the generated `keywords`/`gist`/`value`/`sly_data`
(LLM-generated, not always right), and **register** the fixture in `test_integration_test_hocons.py` for CI.
Docs: [agent_network_test_generator.md](../../../docs/agent_network_test_generator.md).