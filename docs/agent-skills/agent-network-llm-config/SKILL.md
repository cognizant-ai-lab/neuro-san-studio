---
name: agent-network-llm-config
description: Configure or change which LLM provider/model a neuro-san-studio network uses. Use when asked to
  switch models, set up a new provider's API key, or wire per-request/BYOK model config.
---

# LLM configuration

All example/generated networks import a top-level `llm_config` file so model choice lives in one place. What it
resolves to (provider, model, fallback order) is in [config/llm_config.hocon](../../../config/llm_config.hocon), which in
turn points to [developer_llm_config.hocon](../../../config/developer_llm_config.hocon).

Compatible providers include `openai`, `anthropic`, `azure-openai`, `gemini`, `nvidia`, `ollama`, `bedrock`, or a
custom LangChain `class`. Keys go in `.env` (`OPENAI_API_KEY` / `ANTHROPIC_API_KEY` / `GOOGLE_API_KEY`), then
verify with `ns check-llm-keys && ns check-config`.

The built-in model catalog is
[default_llm_info.hocon](https://github.com/cognizant-ai-lab/neuro-san/blob/main/neuro_san/internals/run_context/langchain/llms/default_llm_info.hocon).

End-users can also pass their own keys at request time via `sly_data.llm_config` (BYOK) — see
[config/byok_llm_config.hocon](../../../config/byok_llm_config.hocon) for the pattern.

Docs: [llm_config](https://github.com/cognizant-ai-lab/neuro-san/blob/main/docs/agent_hocon_reference.md#llm_config).
