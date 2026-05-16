# check-config

Validates every LLM configuration in a HOCON file by creating each LLM instance
and invoking it with a trivial test prompt. It is useful for verifying that:

- Provider API keys are set and valid
- Model names are spelled correctly and reachable
- Per-agent `llm_config` overrides resolve to a working model

## Usage

```bash
# Validate the default config/llm_config.hocon
neuro-san-studio check-config

# Validate a specific HOCON file
neuro-san-studio check-config registries/music_nerd.hocon
neuro-san-studio check-config path/to/llm_config.hocon
```

The command exits with code `0` when every configuration succeeds and `1` when
any configuration fails.

## Supported HOCON formats

Both formats produced by `neuro-san-studio` are accepted:

| Format | Detected by | What gets tested |
|---|---|---|
| Agent network | Has a `tools` list | Each agent's merged `llm_config` (top-level defaults + per-agent overrides) |
| Standalone studio `llm_config` | No `tools` list | The single top-level `llm_config` |

`fallbacks` lists are expanded so every model in the list is tested
individually. Duplicate configurations are deduplicated so each unique model is
called only once.

## Output

The command prints, in order:

1. The parsed HOCON file and detected format
2. Each `(label, llm_config)` pair it discovered (with secrets redacted)
3. A per-model creation + invocation result
4. A `RESULTS SUMMARY` listing working and failing configurations

Sensitive keys (anything containing `key`, `token`, `secret`, `credential`, or
`password` at a word boundary) are redacted in the printed configs.
