---
name: agent-network-cli
description: Run, chat with, lint, or validate a neuro-san-studio network via the `ns` CLI. Use when asked to
  run/serve a network, check it lints, validate HOCON, or import/export a network.
---

# Running, linting, validating

```bash
ns run                          # server (localhost:8080) + nsflow UI (localhost:4173)
ns chat folder_name/my_network  # chat directly, no server, use the folder-prefixed name
ns chat --list                  # list networks
ns check-llm-keys               # validate provider keys
ns check-config                 # validate config/llm_config.hocon
ns validate my_network.hocon    # validate HOCON structure — no LLM calls, no API keys needed
```

`ns <command> --help` for flags. Logs under `logs/` (`server.log`, `nsflow.log`, `thinking_dir/`); verbose coded-
tool logging via `export AGENT_SERVICE_LOG_JSON=logging.hocon`.

`ns validate` ([docs/cli/validate.md](../../../docs/cli/validate.md)) wraps neuro-san's own
[HOCON validator CLI](https://github.com/cognizant-ai-lab/neuro-san/blob/main/docs/hocon_validator_cli.md) — prefer
it over calling that CLI directly, it stays in sync with this repo's setup.

Before finishing, everything must lint and pass (line length **119** for Python; markdown is **120** per
`.pymarkdownlint.yaml` — see
[dev_guide.md → Note on Markdown Linting](../../../docs/dev_guide.md#note-on-markdown-linting)):

```bash
make lint    # ruff format + ruff check + pylint (source and tests), plus pymarkdown over docs/
```

**Import/export:** `ns import` pulls example networks (by group/name, or from a file/`.zip`); `ns export
my_network` bundles a network + all dependencies into one shareable file.
Docs: [import](../../../docs/cli/import.md), [export](../../../docs/cli/export.md).
